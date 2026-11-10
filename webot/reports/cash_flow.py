from .base import *

CASH_ACC = ['Торговые кассы', 'Главная касса', 'Kaspi Bank', 'Терминал Каспий банк', 'Денежные средства, эквайринг']
TYPE_RU = {'CASH': 'Наличная выручка', 'CARD': 'Оплата картой', 'PREPAY': 'Предоплата', 'PREPAY_RETURN': 'Возврат предоплаты', 'PAYIN': 'Внесение в кассу', 'PAYOUT': 'Выплата из кассы',
           'PAY_COLLECTION': 'Инкассация (перенос в главную кассу)', 'SESSION_ACCEPTANCE': 'Приёмка смены', 'CUSTOM': 'Ручная проводка', 'INVOICE_PAYMENT': 'Оплата поставщику', 'CASH_SHORTAGE': 'Недостача кассы',
           'CASH_SURPLUS': 'Излишек кассы', 'REVENUE_RETURN': 'Возврат выручки', 'EMPLOYEE_PAYMENT': 'Выплата сотруднику'}

def cash_tx(k, d):
    df = k.olap('TRANSACTIONS', ['Account.Name', 'Account.Type', 'TransactionType', 'Comment', 'Counteragent.Name', 'Product.Name', 'Document'],
                ['Sum.Incoming', 'Sum.Outgoing', 'Sum.ResignedSum'], d, d + dt.timedelta(days=1))
    return df

def build(k, d):
    df = cash_tx(k, d)
    lines = [header('Приход / расход денег', d)]
    if not len(df): return [lines[0] + '\n\nДвижений нет.'], []
    c = df[df['Account.Type'] == 'CASH'].copy()
    # приход = увеличение денежных счетов, расход = уменьшение (без внутренних переносов «приёмка смены»)
    c['inc'] = c['Sum.Incoming']; c['out'] = c['Sum.Outgoing']
    real = c[~c.TransactionType.isin(['SESSION_ACCEPTANCE'])]
    by_acc = real.groupby('Account.Name').agg(inc=('inc', 'sum'), out=('out', 'sum'))
    by_acc = by_acc[(by_acc.inc != 0) | (by_acc.out != 0)]
    rows = [[a, money(r.inc), money(r.out), money(r.inc - r.out, True)] for a, r in by_acc.iterrows()]
    lines.append('<b>По счетам</b>\n' + pre(rows, ['Счёт', 'Приход', 'Расход', 'Итог']))
    inc_t = real[real.inc > 0].groupby('TransactionType').inc.sum().sort_values(ascending=False)
    out_t = real[real.out > 0].groupby('TransactionType').out.sum().sort_values(ascending=False)
    lines.append('<b>Приход по видам</b>\n' + pre([[TYPE_RU.get(t, t), money(v)] for t, v in inc_t.items()]))
    lines.append('<b>Расход по видам</b>\n' + pre([[TYPE_RU.get(t, t), money(v)] for t, v in out_t.items()]))
    # детали расходов кассы: кому/за что
    det = real[(real.out > 0) & real.TransactionType.isin(['PAYOUT', 'CUSTOM', 'INVOICE_PAYMENT', 'PAY_COLLECTION', 'EMPLOYEE_PAYMENT'])].copy()
    det['what'] = det.Comment.fillna('').where(det.Comment.fillna('') != '', det['Counteragent.Name'].fillna('')).where(lambda s: s != '', det['Product.Name'].fillna(''))
    g = det.groupby(['Account.Name', 'TransactionType', 'what']).out.sum().reset_index().sort_values('out', ascending=False).head(25)
    if len(g):
        lines.append('<b>Крупнейшие расходы (кому / за что)</b>\n' + pre([[short(r.what or TYPE_RU.get(r.TransactionType, r.TransactionType), 34), short(r['Account.Name'], 14), money(r.out)] for _, r in g.iterrows()]))
    return ['\n\n'.join(lines)], []
