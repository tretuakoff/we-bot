from .base import *
from . import banquets, prices

RISK = {3: '🔴', 2: '🟠', 1: '🟡'}

def collect(k, d):
    """Список опасных операций за день: [(риск 1-3, категория, описание, сумма, что проверить)]."""
    items = []
    df = day_lines(k, d); ev = events_day(k, d) if True else pd.DataFrame()
    def add(r, cat, txt, amt=0, todo=''): items.append((r, cat, txt, amt, todo))
    if len(df):
        dl = df[df.deleted & (df.DishSumInt > 0)]
        for _, r in dl[dl.printed].iterrows():
            add(3 if r.DishSumInt >= 10000 else 2, 'Удаление после печати', f'{r.open} ст.{r.TableNum} {r.DishName} · офиц. {short(r.waiter, 14)}, кассир {short(r.cashier, 14)}', r.DishSumInt, 'Блюдо ушло на кухню — было ли оно выдано гостю и оплачено?')
        for key, g in dl.groupby('key'):
            s = g.DishSumInt.sum(); r = g.iloc[0]
            if s >= DEL_ORDER_ALERT: add(2, 'Крупное удаление', f'{r.open} ст.{r.TableNum} {short(r.waiter, 14)} · {short(", ".join(list(dict.fromkeys(g.DishName))[:2]), 40)}', s, 'Проверить, не создан ли заказ-двойник; причина не указана')
            if (g.DishName == VIP_DISH).any() and g[g.DishName == VIP_DISH].DishAmountInt.sum() >= 5:
                add(2, 'Аренда VIP: аномальное количество', f'{r.open} ст.{r.TableNum} {int(g[g.DishName == VIP_DISH].DishAmountInt.sum())} ед. удалено', g[g.DishName == VIP_DISH].DishSumInt.sum(), 'Ошибка ввода или бронь без оплаты?')
        live = df[~df.deleted]
        for key, g in live.groupby('key'):
            r = g.iloc[0]; s = g.DiscountSum.sum(); base = g.DishSumInt.sum()
            if s > 0 and (s / base * 100 >= DISCOUNT_ALERT_PCT or s >= DISCOUNT_ALERT_SUM):
                add(2 if s < 100000 else 3, 'Скидка', f'{r.open} ст.{r.TableNum} {pct(s / base * 100, 0)} «{r["OrderDiscount.Type"] or "ручная"}» · {short(r.waiter, 12)}/{short(r.cashier, 12)}', s, 'Основание и разрешивший скидку')
            if g.nopay.all() and base > 0: add(2 if base < 50000 else 3, 'Заказ без оплаты', f'{r.open} ст.{r.TableNum} {short(", ".join(list(dict.fromkeys(g.DishName))[:2]), 40)} · {short(r.waiter, 12)}', base, 'Комплимент по распоряжению? Кто разрешил')
        ret = pd.to_numeric(k.olap('SALES', ['Cashier'], ['DishReturnSum'], d, d + dt.timedelta(days=1)).get('DishReturnSum', pd.Series(dtype=float)), errors='coerce')
        if len(ret) and ret.sum() >= 1000: add(3, 'Возвраты', f'Возвраты блюд за день', ret.sum(), 'Кто и по каким чекам')
        # вынос, похожий на зал: без наценки за обслуживание 10%
        if TAKEAWAY_SECTION and 'RestaurantSection' in live:      # секция выноса задаётся в restaurants.json
            tk = live[live.RestaurantSection == TAKEAWAY_SECTION]
            for key, g in tk.groupby('key'):
                r = g.iloc[0]; net = g.DishDiscountSumInt.sum(); gu = pd.to_numeric(r.GuestNum, errors='coerce'); gu = 0 if pd.isna(gu) else gu
                if g.IncreaseSum.sum() > 0 or (gu < TAKEAWAY_MIN_GUESTS and net < TAKEAWAY_MIN_SUM): continue
                add(3 if net >= 100000 else 2, 'Вынос похож на зал (без наценки 10%)', f'{r.open} ст.{r.TableNum} {int(gu)} гост. · {short(r.waiter, 14)}', net, f'Упущено обслуживание ≈ {money(net * 0.1)}. Банкет/зал пробит как вынос? Кто разрешил')
        # блюда в зале без наценки 10% (в iiko наценка привязана к категории блюда: сбой категории = потеря 10%)
        if HALL_SECTIONS and 'IncreaseSum' in live and 'RestaurantSection' in live:   # залы задаются в restaurants.json
            hl = live[live.RestaurantSection.isin(HALL_SECTIONS) & (live.IncreaseSum == 0) & (live.DishDiscountSumInt > 0) & ~live.nopay]
            if len(hl) and FEE_EXEMPT: hl = hl[~hl.DishName.astype(str).apply(lambda n: any(x.lower() in n.lower() for x in FEE_EXEMPT)).astype(bool)]
            for name, g in hl.groupby('DishName'):
                s = g.DishDiscountSumInt.sum()
                add(2 if s >= 5000 else 1, 'Блюдо без наценки 10% в зале', f'{name}: {len(g)} поз. ({short(g.iloc[0].get("DishGroup"), 16)})', s, f'Упущено ≈ {money(s * 0.1)}. Проверить категорию блюда в карточке iiko (наценка привязана к категории)')
        # банкеты
        b = banquets.banquet_orders(df)
        for key, r in b.iterrows():
            g = df[df.key == key]
            if str(r.table) in VIP_TABLES and not r.vip_paid and not r.vip_del: add(2, 'Банкет: VIP не пробит', f'{r.open} ст.{r.table} {int(r.guests)} гост. {short(r.waiter, 12)}', r.net, 'Аренда VIP не пробита при VIP-столе')
    # смены
    sh = k.cashshifts(d - dt.timedelta(days=1), d + dt.timedelta(days=1))
    if len(sh):
        sh = sh[(sh.openDate.dt.date == d)]
        for _, s in sh.iterrows():
            if s.cashDiff and abs(s.cashDiff) > 0: add(2 if abs(s.cashDiff) < 100000 else 3, 'Смена с расхождением', f'№{s.sessionNumber} {s.cashier}: {money(s.cashDiff, True)}', abs(s.cashDiff), 'Выручка сдана позже? Акт сдачи')
            if s.sessionStatus == 'UNACCEPTED' and pd.notna(s.closeDate) and (dt.datetime.now(TZ).date() - d).days >= 2: add(1, 'Смена не принята', f'№{s.sessionNumber} {s.cashier}', 0, 'Принять смену в iikoOffice')
    # события
    if len(ev):
        acc = k.accounts()
        for _, e in ev.iterrows():
            t = e.get('type'); tm = e['dt'].strftime('%H:%M') if pd.notna(e.get('dt')) else ''; sm = pd.to_numeric(e.get('sum'), errors='coerce'); sm = 0 if pd.isna(sm) else abs(sm)
            pair = {acc.get(e.get('account'), '?'), acc.get(e.get('corrAccount'), '?')}
            routine = (pair == {'Kaspi Bank', 'Терминал Каспий банк'}) or (any(pair == rp for rp in ROUTINE_PAIRS) and sm < MANUAL_ENTRY_ALERT * 5)
            if t == 'accountingTransactionDeleted' and routine and sm < MANUAL_ENTRY_ALERT: continue
            if t == 'accountingTransactionCreated' and routine: continue
            if t in ('accountingTransactionDeleted',) : add(3 if sm >= MANUAL_ENTRY_ALERT else 2, 'Удалена ручная проводка', f'{tm} {e.get("who")}: {acc.get(e.get("account"), "?")} ↔ {acc.get(e.get("corrAccount"), "?")}', sm, 'Первичный документ, кто согласовал')
            elif t == 'accountingTransactionCreated' and sm >= MANUAL_ENTRY_ALERT: add(2, 'Крупная ручная проводка', f'{tm} {e.get("who")}: {acc.get(e.get("account"), "?")} ↔ {acc.get(e.get("corrAccount"), "?")}', sm, 'Основание платежа')
            elif t == 'documentDeleted': add(2, 'Удалён документ', f'{tm} {e.get("who")}: {e.get("documentType")} №{e.get("documentNumber")}', 0, 'Причина удаления')
            elif t == 'documentUnprocessed': add(2, 'Документ распроведён', f'{tm} {e.get("who")}: {e.get("documentType")} №{e.get("documentNumber")}', 0, 'Что менялось после проведения')
            elif t in ('userPermissionChanged', 'rolePermissionChanged'): pass   # в отчёте «Доступы»
            elif t == 'productDeleted': add(1, 'Удалена номенклатура', f'{tm} {e.get("who")}', 0, '')
        mod = ev[ev.type == 'documentModified']
        for (who, dty), g in mod.groupby(['who', 'documentType']):
            if len(g) >= 5 or dty in ('INCOMING_INVENTORY',): add(2 if dty == 'INCOMING_INVENTORY' else 1, 'Правки документов', f'{who}: {dty} — {len(g)} правок', 0, 'Сравнить версии, особенно акты инвентаризации')
        ns = ev[ev.type == 'startAfterIncorrectShutdown']
        if len(ns) >= 3: add(1, 'Аварийные перезапуски кассы', f'{len(ns)} за день', 0, 'Сбой ПО/питания или обход контроля')
        pcd = ev[(ev.type == 'permissionChecked') & (ev.success.astype(str) != '1')]
        if len(pcd) >= 5: add(1, 'Отказы в разрешениях', f'{len(pcd)} отказов', 0, 'Кто пытался выполнить запрещённое')
        ch = ev[ev.type.isin(['orderDiscounted', 'dishServedCancelled', 'deletedNewItems'])]
        night = ch[(ch.dt.dt.hour >= 2) & (ch.dt.dt.hour < 9)] if len(ch) else ch
        if len(night): add(1, 'Ночные операции (02–09 ч)', f'{len(night)} правок заказов', 0, 'Кто работал в нерабочее время')
    # закупки: подорожание >10% и удалённые накладные
    try:
        inv = k.incoming(d, d)
        for (sup, doc), g in inv[inv.status != 'PROCESSED'].groupby(['supplier', 'doc']): add(2, 'Удалена накладная', f'{sup} №{doc}', g['sum'].sum(), 'Причина удаления')
        ok = inv[inv.status == 'PROCESSED'].groupby(['supplier', 'docid']).agg(t=('sum', 'sum')).reset_index()
        for _, r in ok[ok.duplicated(['supplier', 't'], keep=False)].drop_duplicates(['supplier', 't']).iterrows(): add(2, 'Возможный дубль накладной', f'{r.supplier}: {money(r.t)}', r.t, 'Не оприходовано/оплачено дважды')
        wo = k.writeoffs(d, d)
        if len(wo):
            wo = wo[wo.status == 'PROCESSED']
            for acc_, g in wo.groupby('account'):
                if g.cost.sum() >= 50000: add(2, 'Крупное списание', f'{acc_}: {money(g.cost.sum())}', g.cost.sum(), 'Основание, акт подписан?')
    except Exception as e: print('dangerous/purchases', e)
    return items

def build(k, d):
    items = collect(k, d); lines = [header('Опасные операции', d)]
    if not items: return [lines[0] + '\n\n✅ Опасных операций за день не найдено.'], []
    items.sort(key=lambda x: (-x[0], -x[3]))
    cnt = {r: sum(1 for i in items if i[0] == r) for r in (3, 2, 1)}
    lines.append(f'🔴 {cnt[3]} · 🟠 {cnt[2]} · 🟡 {cnt[1]}\nЭто очередь на проверку, а не обвинения.')
    for r in (3, 2, 1):
        sel = [i for i in items if i[0] == r]
        if not sel: continue
        by = {}
        for it in sel: by.setdefault(it[1], []).append(it)
        for cat, lst in by.items():
            txt = f'{RISK[r]} <b>{esc(cat)}</b> ({len(lst)})\n'
            for it in lst[:8]: txt += f'• {esc(it[2])}' + (f' — <b>{money(it[3])}</b>' if it[3] else '') + '\n'
            if len(lst) > 8: txt += f'… и ещё {len(lst) - 8}\n'
            if lst[0][4]: txt += f'<i>Проверить: {esc(lst[0][4])}</i>'
            lines.append(txt.strip())
    return ['\n\n'.join(lines)], []
