from .base import *

def build(k, d):
    """Норма заказа: средний расход за 14 дней → сколько заказать, чтобы хватило на N дней."""
    lines = [header('Норма заказа', d, ' · расчёт на утро')]
    d0 = d - dt.timedelta(days=14)
    cons = k.olap('TRANSACTIONS', ['Contr-Product.Name', 'Store'], ['Amount'], d0, d + dt.timedelta(days=1), extra={'TransactionType': {'filterType': 'IncludeValues', 'values': ['SESSION_WRITEOFF']}})
    pr = k.products(); bal = k.balance()
    if not len(cons): return [lines[0] + '\n\nНет данных о расходе.'], []
    cons = cons.rename(columns={'Contr-Product.Name': 'pname'})
    # расход в кг: количество списания по ингредиенту берём из проводок склада
    st = k.olap('TRANSACTIONS', ['Product.Name', 'Store', 'Account.Type'], ['Amount'], d0, d + dt.timedelta(days=1), extra={'TransactionType': {'filterType': 'IncludeValues', 'values': ['SESSION_WRITEOFF', 'WRITEOFF']}})
    st = st[st['Account.Type'] == 'INVENTORY_ASSETS'].rename(columns={'Product.Name': 'pname'})
    use = st.groupby('pname').Amount.sum().mul(-1).clip(lower=0) / 14
    inv = k.incoming(d - dt.timedelta(days=60), d); inv = inv[(inv.status == 'PROCESSED') & (inv.amount > 0)]
    last = inv.sort_values('date').groupby('pname').last()[['supplier', 'price', 'unit', 'group']] if len(inv) else pd.DataFrame()
    stock = bal.groupby('pname').amount.sum()
    negs = []
    for name, per_day in use.items():
        s0 = float(stock.get(name, 0)); pr0 = last.price.get(name, 0) if len(last) and name in last.index else 0
        if s0 < 0 and per_day > 0 and (per_day * pr0 >= NORM_MIN_DAILY_COST or per_day >= 20):
            negs.append([short(name, 26), f'{s0:.1f}', f'{per_day:.1f}/д'])
    rows = []
    for name, per_day in use.items():
        if per_day <= 0: continue
        grp = last.group.get(name) if len(last) and name in last.index else (pr[pr.pname == name].group.iloc[0] if len(pr[pr.pname == name]) else None)
        if grp not in NORM_GROUPS: continue
        cover = COVER_DAYS.get(grp, COVER_DEFAULT); s = float(stock.get(name, 0)); left = s / per_day if per_day else 99
        s_eff = max(s, 0); left = s_eff / per_day if per_day else 99
        need = max(0, per_day * cover - s_eff)
        sup = last.supplier.get(name, '—') if len(last) and name in last.index else '—'; price = last.price.get(name, 0) if len(last) and name in last.index else 0
        if per_day * price < NORM_MIN_DAILY_COST or need <= 0 or left > cover: continue
        unit = last.unit.get(name, '') if len(last) and name in last.index else ''
        rows.append(dict(pname=name, grp=grp, per_day=per_day, stock=s, neg=s < 0, left=left, cover=cover, need=need, sup=sup, price=price, unit=unit, cost=need * price))
    negtxt = ('\n\n⚠️ <b>Отрицательный остаток в iiko</b> (продаём без прихода — нужна инвентаризация/ввод накладной)\n' + pre(sorted(negs, key=lambda x: float(x[1]))[:15], ['Товар', 'Остаток', 'Расход'])) if negs else ''
    if not rows: return [lines[0] + '\n\n✅ Все ключевые позиции обеспечены запасом по норме.' + negtxt], []
    r = pd.DataFrame(rows).sort_values('left')
    lines.append(f'Позиций к заказу: {len(r)} · ориентировочно на {money(r.cost.sum())}\nНорма: расход за 14 дней ÷ 14 × дни запаса по группе (мясо 3, овощи 3, зелень 2, напитки 7…). Остатки берутся из iiko, они могут быть неточными (см. инвентаризации).')
    urgent = r[r.left < 1].sort_values('cost', ascending=False)
    if len(urgent): lines.append('🔴 <b>Срочно (запас меньше суток)</b>\n' + pre([[short(x.pname, 24), f'{x.stock:.1f}' + ('*' if x.neg else ''), f'{x.per_day:.1f}/д', f'{x.need:.1f} {x.unit}', short(x.sup, 14)] for _, x in urgent.head(15).iterrows()], ['Товар', 'Остаток', 'Расход', 'Заказать', 'Поставщик']) + '\n* остаток в iiko отрицательный — нужна инвентаризация')
    for sup, g in r.groupby('sup'):
        g = g.sort_values('cost', ascending=False)
        lines.append(f'<b>{esc(sup)}</b> · ~{money(g.cost.sum())}\n' + pre([[short(x.pname, 24), f'{x.stock:.1f}', f'{x.left:.1f} дн', f'{x.need:.1f} {x.unit}', money(x.cost)] for _, x in g.head(12).iterrows()], ['Товар', 'Остаток', 'Хватит', 'Заказать', 'Сумма']))
    return ['\n\n'.join(lines) + negtxt], []
