from .base import *

def history(k, d, days=90):
    h = k.incoming(d - dt.timedelta(days=days), d)
    return h[(h.status == 'PROCESSED') & (h.amount > 0) & (h.price > 0)] if len(h) else h

def build(k, d):
    h = history(k, d); lines = [header('Изменение цен', d)]
    if not len(h): return [lines[0] + '\n\nНет данных.'], []
    today_ = h[h.date.dt.date == d]; prev = h[h.date.dt.date < d]
    chg = []
    for (sup, pid), g in today_.groupby(['supplier', 'product']):
        name = g.pname.iloc[0]; qty = g.amount.sum(); p_now = g['sum'].sum() / qty
        ps = prev[(prev['product'] == pid) & (prev.supplier == sup)].sort_values('date'); pa = prev[prev['product'] == pid].sort_values('date')
        base = None; basis = ''
        if len(ps): base = ps.iloc[-1].price; basis = 'у этого поставщика'
        elif len(pa): base = pa.iloc[-1].price; basis = f'у {pa.iloc[-1].supplier}'
        others = prev[(prev['product'] == pid) & (prev.date >= pd.Timestamp(d - dt.timedelta(days=60)))]
        best = None
        if len(others):
            b = others.groupby('supplier').apply(lambda x: x['sum'].sum() / x.amount.sum()); b = b[b.index != sup]
            if len(b): best = (b.idxmin(), b.min())
        change = (p_now / base - 1) * 100 if base else None
        chg.append(dict(pname=name, supplier=sup, qty=qty, unit=g.unit.iloc[0], now=p_now, base=base, basis=basis, change=change, best=best,
                        effect=(p_now - base) * qty if base else 0, over=(p_now - best[1]) * qty if best and p_now > best[1] else 0, new=base is None))
    if not chg: return [lines[0] + '\n\nПоставок за день не было.'], []
    c = pd.DataFrame(chg)
    up = c[(c.change >= PRICE_ALERT_PCT)].sort_values('effect', ascending=False)
    dn = c[(c.change <= -PRICE_ALERT_PCT)].sort_values('effect')
    lines.append(f'Проверено позиций: {len(c)} · подорожало ≥{PRICE_ALERT_PCT}%: {len(up)} · подешевело: {len(dn)} · новых товаров/цен: {int(c.new.sum())}')
    def rows(df_): return [[('🔴 ' if r.change >= PRICE_RED_PCT else '') + short(r.pname, 22), short(r.supplier, 12), num(r.base), num(r.now), pct(r.change, 0, True), money(r.effect, True)] for _, r in df_.iterrows()]
    if len(up): lines.append('<b>⬆ Подорожало</b> (к прошлой закупке)\n' + pre(rows(up.head(20)), ['Товар', 'Поставщик', 'Было', 'Стало', 'Δ%', 'Доп.затраты']))
    if len(dn): lines.append('<b>⬇ Подешевело</b>\n' + pre(rows(dn.head(10)), ['Товар', 'Поставщик', 'Было', 'Стало', 'Δ%', 'Экономия']))
    ov = c[c.over > 1000].sort_values('over', ascending=False).head(10)
    if len(ov): lines.append('<b>Дороже, чем у другого поставщика (60 дней)</b>\n' + pre([[short(r.pname, 22), short(r.supplier, 12), num(r.now), f'{short(r.best[0], 12)} {num(r.best[1])}', money(r.over)] for _, r in ov.iterrows()], ['Товар', 'Купили у', 'Цена', 'Дешевле у', 'Переплата']))
    nw = c[c.new].head(8)
    if len(nw): lines.append('Новые в закупках (нет истории): ' + ', '.join(f'{esc(r.pname)} {num(r.now)}' for _, r in nw.iterrows()))
    tot_over = c.over.sum()
    lines.append(f'Итого потенциальная переплата за день: {money(tot_over)}')
    # изменения цен в меню (события iiko)
    try:
        ev = events_day(k, d)
        if len(ev) and 'defaultSalePriceChanged' in set(ev.type):
            e = ev[ev.type == 'defaultSalePriceChanged']; pr = k.products().set_index('product')['pname']
            lines.append('<b>Изменения цен в меню</b>\n' + pre([[short(pr.get(r.get('productId'), r.get('productId')), 30), r.get('priceOld'), r.get('price'), short(r.get('who'), 16)] for _, r in e.iterrows()], ['Блюдо', 'Было', 'Стало', 'Кто']))
    except Exception: pass
    return ['\n\n'.join(lines)], []
