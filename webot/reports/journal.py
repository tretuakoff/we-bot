from .base import *

# Отчёт по журналу событий iiko: опасные операции — блок «Кассовые операции» и блок «Работа с заказами».
BIG_WITHDRAW = MANUAL_ENTRY_ALERT      # изъятие из кассы от этой суммы — красным
PAY_DIFF = 100                         # допуск расхождения оплаты и пречека, ₸
BIG_ORDER = 30_000                     # удалённый/перенесённый заказ крупнее — внимание
LATE_CLOSE_HOUR = 3                    # смена закрыта после этого часа ночи — отмечаем

def _n(e, col):
    v = pd.to_numeric(e.get(col), errors='coerce'); return 0.0 if pd.isna(v) else float(v)

def _t(e): return e['dt'].strftime('%H:%M') if pd.notna(e.get('dt')) else ''

def _s(v, n=24):
    return short(v, n) if isinstance(v, str) and v.strip() else ''

def _tb(e):
    v = pd.to_numeric(e.get('tableNum'), errors='coerce'); return '' if pd.isna(v) else str(int(v))

def build(k, d):
    t0 = dt.datetime.combine(d, dt.time(5)); ev = k.events(t0, t0 + dt.timedelta(days=1), skip=False); head = header('Журнал событий: кассовые операции и работа с заказами', d)
    if not len(ev):
        return [head + '\n\nЖурнал событий iiko за этот день недоступен (хранится около двух месяцев) или пуст.'], []
    emp = k.employees(); acc = k.accounts(); name = lambda i: emp.get(i, i) if isinstance(i, str) else ''
    flags = []          # (риск, текст) для сводки
    cash, orders = [], []

    # ================= КАССОВЫЕ ОПЕРАЦИИ =================
    out = ev[ev.type == 'Изъятая сумма']
    if len(out):
        rows = []; tot = 0
        for _, e in out.sort_values('dt').iterrows():
            s = abs(_n(e, 'sum')); tot += s
            rows.append([_t(e), _s(e.get('who'), 14), _s(e.get('name') or acc.get(e.get('account')), 18), _s(e.get('comment'), 22) or '—', money(s)])
            if s >= BIG_WITHDRAW: flags.append((3, f'Изъятие из кассы {money(s)} ({_s(e.get("name") or e.get("comment"), 24)}, {_s(e.get("who"), 14)})'))
            elif not _s(e.get('comment')) and s >= 10000: flags.append((2, f'Изъятие {money(s)} без комментария ({_s(e.get("who"), 14)})'))
        cash.append(f'<b>Изъятия из кассы</b> · {len(out)} оп. · {money(tot)}\n' + pre(rows[:20], ['Время', 'Кассир', 'Статья', 'Комментарий', 'Сумма'])
                    + (f'\n… и ещё {len(rows) - 20}' if len(rows) > 20 else ''))
    inc = ev[ev.type == 'Снятая выручка']
    if len(inc):
        rows = [[_t(e), _s(e.get('who'), 14), _s(e.get('comment'), 14), money(abs(_n(e, 'sum')))] for _, e in inc.sort_values('dt').iterrows()]
        cash.append(f'<b>Инкассация (снятая выручка)</b> · {money(sum(abs(_n(e, "sum")) for _, e in inc.iterrows()))}\n' + pre(rows, ['Время', 'Кассир', 'Комментарий', 'Сумма']))
    pre_ = ev[ev.type == 'orderPrepaid']
    if len(pre_):
        rows = [[_t(e), _s(e.get('who'), 14), f'ст.{_tb(e)}', money(_n(e, 'prepaySum'))] for _, e in pre_.sort_values('dt').iterrows()]
        cash.append(f'<b>Предоплаты</b> · {len(pre_)} шт. · {money(sum(_n(e, "prepaySum") for _, e in pre_.iterrows()))}\n' + pre(rows[:12], ['Время', 'Кассир', 'Стол', 'Сумма']))
    paid = ev[ev.type == 'orderPaid']; fisc = ev[ev.type == 'fiscalChequePrinted']; prech = ev[ev.type == 'orderPrechequed']
    if len(paid):
        cash.append(f'<b>Чеки</b>: оплачено {len(paid)}, фискальных {len(fisc)}, пречеков {len(prech)}' + ('' if len(paid) == len(fisc) else ' ⚠ <i>число оплат и фискальных чеков не совпадает</i>'))
        if len(paid) != len(fisc): flags.append((3, f'Оплат {len(paid)}, фискальных чеков {len(fisc)} — расхождение'))
        rep = prech[pd.to_numeric(prech.get('repeated'), errors='coerce').fillna(0) > 0] if 'repeated' in prech else prech.iloc[0:0]
        if len(rep) >= 5: flags.append((1, f'Повторных пречеков: {len(rep)}'))
    ses = ev[ev.type.isin(['sessionOpened', 'cashierSessionClosed', 'sessionClosed', 'xReportPrinted', 'startAfterIncorrectShutdown'])]
    if len(ses):
        parts = []
        for t_, lbl in (('sessionOpened', 'открыта смена'), ('cashierSessionClosed', 'закрыта кассовая смена'), ('xReportPrinted', 'X-отчёт')):
            x = ses[ses.type == t_]
            if len(x): parts.append(f'{lbl}: ' + ', '.join(f'{_t(e)} {_s(e.get("who"), 12)}' for _, e in x.sort_values('dt').iterrows()))
        late = ses[(ses.type == 'cashierSessionClosed') & ses.dt.dt.hour.between(LATE_CLOSE_HOUR, 8)]
        if len(late): flags.append((1, 'Кассовая смена закрыта после ' + str(LATE_CLOSE_HOUR) + ':00: ' + ', '.join(f'{_t(e)} {_s(e.get("who"), 12)}' for _, e in late.iterrows())))
        n_ab = int((ses.type == 'startAfterIncorrectShutdown').sum())
        if n_ab >= 3: flags.append((1, f'Аварийных перезапусков кассы: {n_ab}'))
        cash.append('<b>Смена</b>\n' + '\n'.join(f'• {esc(p)}' for p in parts) + (f'\n• аварийных перезапусков кассы: {n_ab}' if n_ab else ''))
    pc = ev[(ev.type == 'permissionChecked') & (pd.to_numeric(ev.get('success'), errors='coerce').fillna(1) != 1)]
    if len(pc):
        g = pc.groupby(['who', 'permissionName']).size().reset_index(name='n').sort_values('n', ascending=False)
        cash.append(f'<b>Отказы в разрешениях</b> · {len(pc)}\n' + pre([[_s(r.who, 14), _s(r.permissionName, 34), r.n] for r in g.head(8).itertuples()], ['Кто', 'Что пытался', 'Раз']))
        if len(pc) >= 5: flags.append((1, f'Отказов в разрешениях: {len(pc)}'))

    # ================= РАБОТА С ЗАКАЗАМИ =================
    od = ev[ev.type == 'orderDeleted']
    if len(od):
        has_d = od['dishes'].fillna('').astype(str).str.strip().ne('') if 'dishes' in od else pd.Series(False, index=od.index)
        big = od[(pd.to_numeric(od.get('sum'), errors='coerce').fillna(0) > 0) | has_d]
        empty = len(od) - len(big)
        if len(big):
            rows = [[_t(e), _s(e.get('who'), 14), f'ст.{_tb(e)}', _s(name(e.get('waiter')), 12), _s(e.get('dishes'), 20) or '—', money(_n(e, 'sum'))] for _, e in big.sort_values('dt').iterrows()]
            orders.append(f'<b>Удалённые заказы</b> · {len(big)} · {money(sum(_n(e, "sum") for _, e in big.iterrows()))}' + (f' <i>(+ {empty} пустых)</i>' if empty else '') + '\n' + pre(rows[:12], ['Время', 'Кто', 'Стол', 'Официант', 'Блюда', 'Сумма']))
            for _, e in big.iterrows():
                if _n(e, 'sum') >= BIG_ORDER: flags.append((3, f'Удалён заказ {money(_n(e, "sum"))} ст.{_tb(e)} ({_s(e.get("who"), 14)})'))
        elif empty: orders.append(f'<b>Удалённые заказы</b>: {empty} пустых (без блюд) — {", ".join(f"{w} ×{c}" for w, c in od.groupby("who").size().sort_values(ascending=False).head(4).items())}')
    dn = ev[ev.type == 'deletedNewItems']
    if len(dn):
        g = dn.groupby('who').agg(n=('type', 'size')).sort_values('n', ascending=False); tot_s = sum(_n(e, 'sum') for _, e in dn.iterrows() if False)
        orders.append(f'<b>Удаление блюд до печати на кухню</b> · {len(dn)} раз (не нарушение: правка заказа)\n' + ', '.join(f'{esc(_s(w, 14))} ×{r.n}' for w, r in g.head(6).iterrows()))
        top = dn[dn.get('dishes').notna()].copy() if 'dishes' in dn else dn.iloc[0:0]
        if len(top):
            top['_s'] = top.apply(lambda e: _n(e, 'sum'), axis=1); top = top[top._s >= BIG_ORDER].sort_values('_s', ascending=False).head(5)
            if len(top): orders.append('Крупные заказы с удалением позиций:\n' + pre([[_t(e), _s(e.get('who'), 14), f'ст.{_tb(e)}', _s(e.get('dishes'), 24), money(_n(e, 'sum'))] for _, e in top.iterrows()], ['Время', 'Кто', 'Стол', 'Что удалено', 'Заказ']))
    ds = ev[ev.type == 'dishServedCancelled']
    if len(ds):
        g = ds.groupby('who').size().sort_values(ascending=False)
        orders.append(f'<b>Отмена статуса «подано»</b> · {len(ds)}\n' + ', '.join(f'{esc(_s(w, 14))} ×{c}' for w, c in g.head(6).items()))
        if len(ds) >= 40: flags.append((1, f'Много отмен «подано»: {len(ds)}'))
    dc = ev[ev.type == 'orderDiscounted']
    if len(dc):
        rows = []
        for _, e in dc.sort_values('dt').iterrows():
            pc_ = abs(_n(e, 'percent')); rows.append([_t(e), _s(e.get('who'), 14), f'ст.{_tb(e)}', f'{pc_:.0f}%' if pc_ else '—', money(_n(e, 'sum')), _s(name(e.get('auth')), 14) or '—'])
            if pc_ >= DISCOUNT_ALERT_PCT or _n(e, 'sum') * pc_ / 100 >= DISCOUNT_ALERT_SUM: flags.append((2, f'Скидка {pc_:.0f}% на заказ {money(_n(e, "sum"))} ст.{_tb(e)} ({_s(e.get("who"), 14)}, разрешил {_s(name(e.get("auth")), 14) or "—"})'))
        orders.append(f'<b>Скидки на заказ</b> · {len(dc)}\n' + pre(rows[:10], ['Время', 'Кто', 'Стол', '%', 'Заказ', 'Разрешил']))
    om = ev[(ev.type == 'orderMoved') & ev.get('newWaiter').notna() & ev.get('waiter').notna() & (ev.get('waiter') != ev.get('newWaiter'))] if 'newWaiter' in ev and 'waiter' in ev else ev.iloc[0:0]
    if len(om):
        rows = [[_t(e), _s(e.get('who'), 14), f'ст.{_tb(e)}', _s(name(e.get('waiter')), 11), _s(name(e.get('newWaiter')), 11), money(_n(e, 'orderSumAfterDiscount') or _n(e, 'sum'))] for _, e in om.sort_values('dt').iterrows()]
        orders.append(f'<b>Заказ передан другому официанту</b> · {len(om)}\n' + pre(rows[:10], ['Время', 'Кто', 'Стол', 'От', 'Кому', 'Сумма']))
        for _, e in om.iterrows():
            if (_n(e, 'orderSumAfterDiscount') or _n(e, 'sum')) >= BIG_ORDER * 2: flags.append((2, f'Передан крупный заказ {money(_n(e, "orderSumAfterDiscount") or _n(e, "sum"))} ст.{_tb(e)}: {_s(name(e.get("waiter")), 11)} → {_s(name(e.get("newWaiter")), 11)}'))
    mv = ev[ev.type == 'dishesMovedFrom']
    if len(mv):
        rows = [[_t(e), _s(e.get('who'), 14), f'ст.{_tb(e)}', _s(e.get('dishes'), 22), money(_n(e, 'sum'))] for _, e in mv.sort_values('dt').iterrows()]
        orders.append(f'<b>Перенос блюд между заказами</b> · {len(mv)}\n' + pre(rows[:10], ['Время', 'Кто', 'Стол', 'Блюда', 'Заказ']) + (f'\n… и ещё {len(rows) - 10}' if len(rows) > 10 else ''))
    sp = ev[ev.type == 'splitOrderItem']
    if len(sp): orders.append(f'<b>Разделение позиций заказа</b> · {len(sp)}: ' + ', '.join(f'{esc(_s(w, 14))} ×{c}' for w, c in sp.groupby('who').size().sort_values(ascending=False).head(5).items()))
    gc = ev[ev.type == 'changedOrderGuestCount']
    if len(gc):
        rows = [[_t(e), _s(e.get('who'), 14), f'ст.{_tb(e)}', _s(str(e.get('comment', '')).replace('Старое к-во гостей: ', 'было '), 10), f'→ {int(_n(e, "numGuests"))}', money(_n(e, 'orderSumAfterDiscount') or _n(e, 'sum'))] for _, e in gc.sort_values('dt').iterrows()]
        orders.append(f'<b>Изменено число гостей</b> · {len(gc)}\n' + pre(rows[:8], ['Время', 'Кто', 'Стол', 'Было', 'Стало', 'Заказ']))

    # ================= СВОДКА =================
    flags.sort(key=lambda x: -x[0]); R = {3: '🔴', 2: '🟠', 1: '🟡'}
    summary = head + f'\nСобытий в журнале: {len(ev)}. Это очередь на проверку, а не обвинения.'
    summary += ('\n\n<b>Главное:</b>\n' + '\n'.join(f'{R[r]} {esc(t)}' for r, t in flags[:12])) if flags else '\n\n✅ Критичных отклонений в журнале не найдено.'
    msgs = [summary]
    if cash: msgs += split_msg('💵 <b>КАССОВЫЕ ОПЕРАЦИИ</b>\n\n' + '\n\n'.join(cash))
    if orders: msgs += split_msg('🧾 <b>РАБОТА С ЗАКАЗАМИ</b>\n\n' + '\n\n'.join(orders))
    return msgs, []
