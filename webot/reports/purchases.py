from .base import *

def build(k, d):
    inv = k.incoming(d, d)
    lines = [header('Закупки', d)]
    if not len(inv): return [lines[0] + '\n\nНакладных за день нет.'], []
    ok = inv[inv.status == 'PROCESSED']; bad = inv[inv.status != 'PROCESSED']
    docs = ok.docid.nunique(); tot = ok['sum'].sum()
    lines.append(f'<b>Принято накладных: {docs} на {money(tot)}</b>')
    bs = ok.groupby('supplier').agg(docs=('docid', 'nunique'), sum=('sum', 'sum')).sort_values('sum', ascending=False)
    lines.append(pre([[short(s, 30), int(r.docs), money(r['sum'])] for s, r in bs.iterrows()], ['Поставщик', 'Накл.', 'Сумма']))
    top = ok.sort_values('sum', ascending=False).head(12)
    lines.append('<b>Крупнейшие позиции</b>\n' + pre([[short(r.pname, 24), short(r.supplier, 14), f'{r.amount:g} {r.unit or ""}', money(r.price), money(r['sum'])] for _, r in top.iterrows()], ['Товар', 'Поставщик', 'Кол-во', 'Цена', 'Сумма']))
    gg = ok.groupby('group')['sum'].sum().sort_values(ascending=False).head(6)
    lines.append('По группам: ' + ', '.join(f'{esc(g)} {money(v)}' for g, v in gg.items()))
    # накопительно за месяц и прошлый месяц
    m0 = d.replace(day=1); mtd = k.incoming(m0, d); mtd = mtd[mtd.status == 'PROCESSED']
    pm1 = (m0 - dt.timedelta(days=1)).replace(day=1); pm = k.incoming(pm1, pm1.replace(day=min(d.day, 28))); pm = pm[pm.status == 'PROCESSED']
    lines.append(f'С начала месяца: {money(mtd["sum"].sum())} · за тот же период прошлого месяца: {money(pm["sum"].sum())}')
    if len(bad): lines.append('⚠️ Удалённые/непроведённые накладные за день: ' + ', '.join(f'{esc(r.supplier)} №{r.doc} {money(r["sum"])}' for _, r in bad.groupby(['docid']).agg(supplier=('supplier', 'first'), doc=('doc', 'first'), sum=('sum', 'sum')).iterrows()))
    dup = ok.groupby(['supplier', 'docid']).agg(total=('sum', 'sum')).reset_index()
    dd = dup[dup.duplicated(['supplier', 'total'], keep=False)]
    if len(dd): lines.append('⚠️ Возможные дубли (одинаковый поставщик и сумма): ' + ', '.join(sorted({f'{s} {money(t)}' for s, t in zip(dd.supplier, dd.total)})))
    return ['\n\n'.join(lines)], []
