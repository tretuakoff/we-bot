from .base import *

EXCL = {'Зарплата', 'Дивиденды', 'Расход продуктов'}

def build(k, d):
    df = k.olap('TRANSACTIONS', ['Account.Name', 'Account.Type', 'TransactionType', 'Comment', 'Counteragent.Name', 'Product.Name'], ['Sum.ResignedSum'], d, d + dt.timedelta(days=1))
    lines = [header('Прочие расходы за день', d)]
    if not len(df): return [lines[0] + '\n\nНет данных.'], []
    e = df[df['Account.Type'].isin(['EXPENSES', 'OTHER_EXPENSES']) & ~df['Account.Name'].isin(EXCL)].copy()
    e = e[e['Sum.ResignedSum'] != 0]
    tot = e['Sum.ResignedSum'].sum()
    if not len(e): return [lines[0] + '\n\nПрочих расходов за день не проведено.'], []
    lines.append(f'<b>Итого: {money(tot)}</b>')
    g = e.groupby('Account.Name')['Sum.ResignedSum'].sum().sort_values(ascending=False)
    lines.append(pre([[a, money(v)] for a, v in g.items()], ['Статья', 'Сумма']))
    e['what'] = e.Comment.fillna('').where(e.Comment.fillna('') != '', e['Counteragent.Name'].fillna('')).where(lambda s: s != '', e['Product.Name'].fillna(''))
    det = e.groupby(['Account.Name', 'what'])['Sum.ResignedSum'].sum().reset_index().sort_values('Sum.ResignedSum', ascending=False).head(20)
    lines.append('<b>Детали</b>\n' + pre([[short(r['Account.Name'], 22), short(r.what, 30), money(r['Sum.ResignedSum'])] for _, r in det.iterrows()]))
    # зарплата и дивиденды отдельной строкой
    sal = df[df['Account.Name'] == 'Зарплата']['Sum.ResignedSum'].sum(); div = df[df['Account.Name'] == 'Дивиденды']['Sum.ResignedSum'].sum()
    extra = []
    if sal: extra.append(f'Зарплата (начислено/выплачено в iiko): {money(sal)}')
    if div: extra.append(f'Дивиденды: {money(div)}')
    if extra: lines.append('\n'.join(extra))
    big = e[e['Sum.ResignedSum'] >= MANUAL_ENTRY_ALERT]
    if len(big): lines.append('⚠️ Крупные статьи ≥ ' + money(MANUAL_ENTRY_ALERT) + ': ' + ', '.join(sorted(set(big['Account.Name']))))
    return ['\n\n'.join(lines)], []
