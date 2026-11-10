"""Детальные данные за день (заказы со строками, накладные, проводки, опасные операции…) → archive/data/ГГГГ-ММ-ДД.json.
Прошедшие дни не меняются, поэтому кэшируются и считаются один раз."""
import json, datetime as dt, pandas as pd, numpy as np
from .config import *
from .util import *
from .reports.base import day_lines, events_day
from .reports import dangerous, banquets

DATA = DATA_DIR
TX_TYPES = ['CASH', 'CARD', 'PREPAY', 'PREPAY_CLOSED', 'PREPAY_RETURN', 'PAYIN', 'PAYOUT', 'PAY_COLLECTION', 'CUSTOM', 'INVOICE_PAYMENT', 'EMPLOYEE_PAYMENT', 'WRITEOFF',
            'INVENTORY_CORRECTION', 'TRANSFER', 'PRODUCTION', 'TRANSFORMATION', 'OUTGOING_SERVICE', 'INCOMING_SERVICE', 'CASH_SHORTAGE', 'CASH_SURPLUS', 'PENALTY',
            'REVENUE_RETURN', 'STORE_COST_CORRECTION', 'OUTGOING_INVOICE_REVENUE']

def _r(x, n=0):
    try:
        v = float(x); return 0 if np.isnan(v) else round(v, n)
    except Exception: return 0
def _s(x): return '' if (x is None or (isinstance(x, float) and np.isnan(x))) else str(x)

def price_history(k, d, days=90):
    h = k.incoming(d - dt.timedelta(days=days), d)
    return h[(h.status == 'PROCESSED') & (h.amount > 0) & (h.price > 0)] if len(h) else h

def build_day(k, d, hist=None):
    df = day_lines(k, d)
    out = dict(v=2, date=str(d), wd=wd(d), orders=[], purchases=[], expenses=[], cash=[], danger=[], shifts=[], access=[], events={})
    if len(df):
        ban = banquets.banquet_orders(df)
        for key, g in df.groupby('key', sort=False):
            r = g.iloc[0]; live = g[~g.deleted]; dele = g[g.deleted]
            lines = []
            for _, x in g.iterrows():
                st = 0
                if x.deleted: st = 3 if x.printed else (2 if x.OrderDeleted == 'DELETED' else 1)   # 1 позиция удалена до печати, 2 заказ удалён (до печати), 3 удалено после печати
                lines.append([_s(x.DishName), _r(x.DishAmountInt, 2), _r(x.DishSumInt), _r(x.DishDiscountSumInt), st, _r(x['ProductCostBase.ProductCost'])])
            vip = 0
            if (live.DishName == VIP_DISH).any(): vip = 1
            elif (dele.DishName == VIP_DISH).any(): vip = 2
            out['orders'].append(dict(k=key.split('|', 1)[1], t=r.open, c=r.close, tb=_s(r.TableNum), gu=_r(r.GuestNum), w=_s(r.waiter), ca=_s(r.cashier),
                                      g=_r(live.DishSumInt.sum()), n=_r(live.DishDiscountSumInt.sum()), dc=_r(live.DiscountSum.sum()), dt=_r(dele[dele.DishSumInt > 0].DishSumInt.sum()),
                                      da=_r(dele[dele.printed].DishSumInt.sum()), pay=', '.join(sorted({_s(p) for p in live.PayTypes})) or ', '.join(sorted({_s(p) for p in g.PayTypes})),
                                      np=int(bool(len(live) and live.nopay.all() and live.DishSumInt.sum() > 0)), bq=int(key in ban.index), vip=vip, od=int((g.OrderDeleted == 'DELETED').any()),
                                      dtp=_s(', '.join(sorted({str(x) for x in live['OrderDiscount.Type'] if x}))), l=lines))
    # закупки
    inv = k.incoming(d, d)
    if len(inv):
        hist = hist if hist is not None else price_history(k, d)
        prev = hist[hist.date < pd.Timestamp(d)] if len(hist) else hist
        for (docid, doc, sup, st), g in inv.groupby(['docid', 'doc', 'supplier', 'status'], sort=False):
            ls = []
            for _, x in g.iterrows():
                p0 = None; basis = ''
                if len(prev):
                    ps = prev[(prev['product'] == x['product']) & (prev.supplier == sup)].sort_values('date'); pa = prev[prev['product'] == x['product']].sort_values('date')
                    if len(ps): p0 = ps.iloc[-1].price
                    elif len(pa): p0 = pa.iloc[-1].price; basis = pa.iloc[-1].supplier
                ls.append([_s(x.pname), _s(x.unit), _r(x.amount, 3), _r(x.price, 2), _r(x['sum']), _r(p0, 2) if p0 else 0, _r((x.price / p0 - 1) * 100, 1) if p0 else None, _s(x.group), basis])
            out['purchases'].append(dict(doc=_s(doc), sup=_s(sup), st=_s(st), sum=_r(g['sum'].sum()), store=_s(g.store.iloc[0]), l=ls))
    # проводки: расходы и деньги
    try:
        tx = k.olap('TRANSACTIONS', ['Account.Name', 'Account.Type', 'TransactionType', 'Comment', 'Counteragent.Name', 'Product.Name', 'Document'], ['Sum.Incoming', 'Sum.Outgoing', 'Sum.ResignedSum'],
                    d, d + dt.timedelta(days=1), extra={'TransactionType': {'filterType': 'IncludeValues', 'values': TX_TYPES}})
    except Exception as e: print('daydata tx', d, e); tx = pd.DataFrame()
    if len(tx):
        for _, x in tx.iterrows():
            what = _s(x.Comment) or _s(x['Counteragent.Name']) or _s(x['Product.Name'])
            if x['Account.Type'] in ('EXPENSES', 'OTHER_EXPENSES', 'COST_OF_GOODS_SOLD', 'OTHER_INCOME', 'INCOME') and x['Sum.ResignedSum'] != 0:
                out['expenses'].append([_s(x['Account.Name']), _s(x['Account.Type']), _s(x.TransactionType), what, _r(x['Sum.ResignedSum']), _s(x.Document)])
            if x['Account.Type'] == 'CASH' and (x['Sum.Incoming'] or x['Sum.Outgoing']):
                out['cash'].append([_s(x['Account.Name']), _s(x.TransactionType), _r(x['Sum.Incoming']), _r(x['Sum.Outgoing']), what, _s(x.Document)])
    # расход товаров по складам (продажи по ТТК и акты) и инвентаризации — для панели «Заказ»
    try:
        cn = k.olap('TRANSACTIONS', ['Product.Name', 'Store', 'Account.Type', 'TransactionType'], ['Amount', 'Sum.ResignedSum'], d, d + dt.timedelta(days=1),
                    extra={'TransactionType': {'filterType': 'IncludeValues', 'values': ['SESSION_WRITEOFF', 'WRITEOFF']}})
        cn = cn[(cn['Account.Type'] == 'INVENTORY_ASSETS') & (cn.Amount != 0)] if len(cn) else cn
        out['cons'] = [[_s(x.Store), _s(x['Product.Name']), _r(-x.Amount, 3), _r(-x['Sum.ResignedSum']), 1 if x.TransactionType == 'SESSION_WRITEOFF' else 2] for _, x in cn.iterrows()]
        iv = k.olap('TRANSACTIONS', ['Product.Name', 'Store', 'Account.Type', 'Document'], ['Amount', 'Sum.ResignedSum'], d, d + dt.timedelta(days=1),
                    extra={'TransactionType': {'filterType': 'IncludeValues', 'values': ['INVENTORY_CORRECTION']}})
        iv = iv[(iv['Account.Type'] == 'INVENTORY_ASSETS') & ((iv.Amount != 0) | (iv['Sum.ResignedSum'] != 0))] if len(iv) else iv
        out['inv'] = [[_s(x.Store), _s(x['Product.Name']), _r(x.Amount, 3), _r(x['Sum.ResignedSum']), _s(x.Document)] for _, x in iv.iterrows()]
    except Exception as e: print('daydata cons/inv', d, e)
    # опасные
    try: out['danger'] = [[i[0], i[1], i[2], _r(i[3]), i[4]] for i in dangerous.collect(k, d)]
    except Exception as e: print('daydata danger', d, e)
    # смены
    try:
        sh = k.cashshifts(d - dt.timedelta(days=1), d + dt.timedelta(days=1))
        if len(sh):
            for _, s in sh[sh.openDate.dt.date == d].iterrows():
                out['shifts'].append([int(s.sessionNumber), _s(s.cashier), s.openDate.strftime('%H:%M'), s.closeDate.strftime('%H:%M') if pd.notna(s.closeDate) else '', _r(s.salesCash), _r(s.salesCard), _r(s.cashDiff), _s(s.sessionStatus)])
    except Exception as e: print('daydata shifts', d, e)
    # события: доступы и правки
    try:
        ev = events_day(k, d)
        if len(ev):
            out['events'] = {kk: int(v) for kk, v in ev.type.value_counts().items() if kk in ('deletedNewItems', 'deletedPrintedItems', 'orderDeleted', 'orderDiscounted', 'documentModified', 'documentDeleted', 'accountingTransactionCreated',
                                                                                             'accountingTransactionDeleted', 'userPermissionChanged', 'permissionChecked', 'startAfterIncorrectShutdown', 'Изъятая сумма')}
            emp = k.employees()
            for _, e in ev[ev.type.isin(['userPermissionChanged', 'rolePermissionChanged', 'userCreated', 'userUpdated', 'userDeleted'])].iterrows():
                out['access'].append([e['dt'].strftime('%H:%M'), _s(e.type), _s(e.userName) or _s(emp.get(e.userId)), _s(e.permissionCode), _s(e.permissionState), _s(e.who)])
            out['edits'] = [[e['dt'].strftime('%H:%M'), _s(e.who), _s(e.type), _s(e.documentType), _s(e.documentNumber)] for _, e in ev[ev.type.isin(['documentModified', 'documentDeleted', 'documentUnprocessed'])].iterrows()][:300]
    except Exception as e: print('daydata events', d, e)
    return out

def get_day(k, d, hist=None, refresh=False):
    f = DATA / f'{d}.json'
    if f.exists() and not refresh and d < today():
        x = json.loads(f.read_text())
        if x.get('v', 1) >= 2: return x
    x = build_day(k, d, hist); f.write_text(json.dumps(x, ensure_ascii=False, separators=(',', ':'))); return x

def get_range(k, d0, d1, refresh=False):
    hist = None; out = []
    for i in range((d1 - d0).days + 1):
        d = d0 + dt.timedelta(days=i); f = DATA / f'{d}.json'
        if not (f.exists() and not refresh and d < today() and json.loads(f.read_text()).get('v', 1) >= 2) and hist is None: hist = price_history(k, d1)
        out.append(get_day(k, d, hist, refresh))
    return out

def stock_snapshot(k):
    """Текущие остатки по складам для панели «Заказ»."""
    b = k.balance()
    b = b[(b.amount.abs() > 1e-6) | (b['sum'].abs() > 1)]
    return [[_s(r.store), _s(r.pname), _s(r['group']), _s(r.unit), _r(r.amount, 3), _r(r['sum'])] for _, r in b.iterrows()]

def last_prices(k, d, days=120):
    """Последние закупочные цены и поставщики по товарам (для расчёта суммы заказа)."""
    h = price_history(k, d, days)
    if not len(h): return {}
    h = h.sort_values('date'); res = {}
    for (p, sto), g in h.groupby(['pname', 'store']):
        l = g.iloc[-1]; res[f'{sto}|{p}'] = [_s(l.supplier), _r(l.price, 2), str(l.date.date())]
    return res
