import datetime as dt, pandas as pd, numpy as np
from ..config import *
from ..util import *

LINE_ROWS = ['OpenDate.Typed', 'SessionNum', 'OrderNum', 'OpenTime', 'CloseTime', 'Cashier', 'OrderWaiter.Name', 'TableNum', 'GuestNum', 'DishName',
             'DishGroup', 'OrderDeleted', 'DeletedWithWriteoff', 'DeletionComment', 'RemovalType', 'PayTypes', 'OrderDiscount.Type', 'DishServicePrintTime', 'RestaurantSection']
LINE_AGGS = ['DishAmountInt', 'DishSumInt', 'DishDiscountSumInt', 'DiscountSum', 'ProductCostBase.ProductCost', 'IncreaseSum']

def day_lines(k, d, d1=None):
    """Все строки продаж за бизнес-дату d (или [d, d1))."""
    df = k.olap('SALES', LINE_ROWS, LINE_AGGS, d, d1 or d + dt.timedelta(days=1))
    if not len(df): return df
    df['deleted'] = (df.OrderDeleted == 'DELETED') | (df.DeletedWithWriteoff != 'NOT_DELETED')
    df['printed'] = df.DishServicePrintTime.notna() & (df.DishServicePrintTime.astype(str).str.len() > 5)
    df['key'] = df['OpenDate.Typed'].astype(str).str[:10] + '|' + df.SessionNum.astype(str) + '|' + df.OrderNum.astype(str)
    df['open'] = df.OpenTime.astype(str).str[11:16]; df['close'] = df.CloseTime.astype(str).str[11:16]
    df['waiter'] = df['OrderWaiter.Name']; df['cashier'] = df['Cashier']
    df['nopay'] = df.PayTypes == '(без оплаты)'
    return df

def order_totals(df):
    """Свод по заказам."""
    live = df[~df.deleted]
    g = live.groupby('key').agg(date=('OpenDate.Typed', 'first'), open=('open', 'first'), close=('close', 'first'), table=('TableNum', 'first'), guests=('GuestNum', 'first'),
                                waiter=('waiter', 'first'), cashier=('cashier', 'first'), gross=('DishSumInt', 'sum'), net=('DishDiscountSumInt', 'sum'),
                                disc=('DiscountSum', 'sum'), pay=('PayTypes', lambda s: ', '.join(sorted(set(s)))), nopay=('nopay', 'all'))
    return g

def events_day(k, d, hours_from=5):
    t0 = dt.datetime.combine(d, dt.time(hours_from)); return k.events(t0, t0 + dt.timedelta(days=1))

def header(title, d=None, extra=''):
    s = f'<b>{esc(RESTAURANT)} · {esc(title)}</b>'
    if d: s += f'\n{rus_date(d)} ({wd(d)}){extra}'
    return s

def same_weekday_avg(k, d, weeks=4):
    """Средняя выручка в такие же дни недели за предыдущие weeks недель."""
    d0 = d - dt.timedelta(days=7 * weeks)
    df = k.olap('SALES', ['OpenDate.Typed'], ['DishDiscountSumInt', 'UniqOrderId.OrdersCount'], d0, d)
    if not len(df): return None, None
    df['d'] = pd.to_datetime(df['OpenDate.Typed'].str[:10]); df = df[df.d.dt.weekday == d.weekday()]
    return (df.DishDiscountSumInt.mean(), df['UniqOrderId.OrdersCount'].mean()) if len(df) else (None, None)
