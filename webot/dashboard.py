"""Визуальные дашборды (PNG) для Telegram: день и период."""
import datetime as dt, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt, matplotlib.gridspec as gs, numpy as np, pandas as pd
from matplotlib.patches import FancyBboxPatch, Circle
from .config import *
from .util import *
from .reports.base import day_lines, order_totals, same_weekday_avg
from .reports import dangerous, cash_flow

NAVY, ORANGE, GREEN, RED, AMBER, GREY, LIGHT = '#1F3864', '#E8833A', '#2E9E6B', '#D64545', '#F2A93B', '#7A8599', '#F3F5F9'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'axes.spines.top': False, 'axes.spines.right': False, 'axes.edgecolor': '#C9CFDA', 'axes.labelcolor': GREY,
                     'xtick.color': GREY, 'ytick.color': GREY, 'axes.titleweight': 'bold', 'axes.titlesize': 12, 'axes.titlecolor': NAVY, 'axes.titlelocation': 'left'})

def m(x):
    x = float(x); a = abs(x)
    if a >= 1e6: return f'{x / 1e6:.2f} млн'.replace('.', ',')
    if a >= 1e3: return f'{x / 1e3:.0f} тыс'
    return f'{x:.0f}'

def tile(ax, title, value, sub='', color=NAVY, sub_color=GREY):
    ax.axis('off'); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.add_patch(FancyBboxPatch((0.02, 0.05), 0.96, 0.9, boxstyle='round,pad=0,rounding_size=0.06', fc='white', ec='#DDE2EB', lw=1.2))
    ax.add_patch(FancyBboxPatch((0.02, 0.05), 0.025, 0.9, boxstyle='square,pad=0', fc=color, ec='none'))
    ax.text(0.09, 0.74, title, fontsize=10.5, color=GREY, va='center')
    ax.text(0.09, 0.43, value, fontsize=19, color=color, va='center', fontweight='bold')
    if sub: ax.text(0.09, 0.15, sub, fontsize=9.5, color=sub_color, va='center')

def title_band(fig, text, sub):
    ax = fig.add_axes([0, 0.945, 1, 0.055]); ax.axis('off'); ax.add_patch(plt.Rectangle((0, 0), 1, 1, fc=NAVY, ec='none'))
    ax.text(0.015, 0.5, text, color='white', fontsize=19, fontweight='bold', va='center'); ax.text(0.985, 0.5, sub, color='#C9D3EA', fontsize=11, ha='right', va='center')

def fc_color(v): return GREEN if v < 40 else AMBER if v < 55 else RED

def _daily(k, d0, d1):
    df = k.olap('SALES', ['OpenDate.Typed'], ['DishDiscountSumInt'], d0, d1)
    if not len(df): return pd.Series(dtype=float)
    s = df.set_index(df['OpenDate.Typed'].str[:10]).DishDiscountSumInt; s.index = pd.to_datetime(s.index); return s

def day_dashboard(k, d, out_dir=None):
    df = day_lines(k, d)
    live = df[~df.deleted] if len(df) else df
    ot = order_totals(df) if len(df) else pd.DataFrame(); paid = ot[~ot.nopay] if len(ot) else ot
    rev = live.DishDiscountSumInt.sum() if len(live) else 0; gross = df.DishSumInt.sum() if len(df) else 0
    checks = len(paid); guests = paid.guests.sum() if len(paid) else 0
    avg_rev, _ = same_weekday_avg(k, d)
    dl = df[df.deleted & (df.DishSumInt > 0)] if len(df) else df
    del_sum = dl.DishSumInt.sum() if len(dl) else 0; del_aft = dl[dl.printed].DishSumInt.sum() if len(dl) else 0
    trend = _daily(k, d - dt.timedelta(days=13), d + dt.timedelta(days=1)).reindex(pd.date_range(d - dt.timedelta(days=13), d)).fillna(0)
    inv = k.incoming(d, d); inv_ok = inv[inv.status == 'PROCESSED'] if len(inv) else inv; purch = inv_ok['sum'].sum() if len(inv_ok) else 0
    try: tx = cash_flow.cash_tx(k, d)
    except Exception: tx = pd.DataFrame()
    payout = other = 0
    if len(tx):
        c = tx[tx['Account.Type'] == 'CASH']; payout = c[c.TransactionType == 'PAYOUT']['Sum.Outgoing'].sum()
        e = tx[tx['Account.Type'].isin(['EXPENSES', 'OTHER_EXPENSES']) & ~tx['Account.Name'].isin(['Зарплата', 'Дивиденды', 'Расход продуктов'])]; other = e['Sum.ResignedSum'].sum()
    try: items = dangerous.collect(k, d)
    except Exception as e_: print('dashboard dangerous', e_); items = []
    cnt = {r: sum(1 for i in items if i[0] == r) for r in (3, 2, 1)}

    fig = plt.figure(figsize=(16, 11.2), dpi=110, facecolor=LIGHT)
    title_band(fig, f'{RESTAURANT.upper()} · Дашборд дня', f'{rus_date(d)} ({wd(d)}) · данные iiko')
    g = gs.GridSpec(4, 6, figure=fig, left=0.075, right=0.975, top=0.925, bottom=0.05, hspace=0.45, wspace=0.62, height_ratios=[0.62, 1.5, 1.5, 1.35])
    delta = (rev / avg_rev - 1) * 100 if avg_rev else None
    tile(fig.add_subplot(g[0, 0:2]), 'Выручка', f'{m(rev)} тг', (f'{delta:+.0f}% к среднему {wd(d)} ({m(avg_rev)})' if delta is not None else ''), GREEN if (delta or 0) >= 0 else RED, GREEN if (delta or 0) >= 0 else RED)
    tile(fig.add_subplot(g[0, 2]), 'Чеков / гостей', f'{checks} / {int(guests)}', '')
    tile(fig.add_subplot(g[0, 3]), 'Средний чек', f'{rev / checks if checks else 0:,.0f} тг'.replace(',', ' '), '')
    dp = del_sum / gross * 100 if gross else 0
    tile(fig.add_subplot(g[0, 4]), 'Удалено (по меню)', f'{m(del_sum)} тг', f'{dp:.1f}% продаж · после печати {m(del_aft)}', RED if del_aft > 0 or dp > 8 else AMBER if dp > 3 else GREEN, GREY)
    tile(fig.add_subplot(g[0, 5]), 'Закупки за день', f'{m(purch)} тг', f'накладных: {inv_ok.docid.nunique() if len(inv_ok) else 0}')

    # тренд 14 дней
    ax = fig.add_subplot(g[1, 0:4]); ax.set_title('Выручка за 14 дней')
    cols = [ORANGE if x == pd.Timestamp(d) else '#9DB2D6' for x in trend.index]
    ax.bar(range(len(trend)), trend.values / 1e6, color=cols, width=0.72)
    ax.set_xticks(range(len(trend))); ax.set_xticklabels([f'{x.day:02d}\n{wd(x.date())}' for x in trend.index], fontsize=9)
    if avg_rev: ax.axhline(avg_rev / 1e6, color=NAVY, ls='--', lw=1.2); ax.text(len(trend) - 0.4, avg_rev / 1e6, f'среднее {wd(d)}: {m(avg_rev)}', color=NAVY, fontsize=9, va='bottom', ha='right', bbox=dict(fc='white', ec='none', pad=1.5))
    for i, v in enumerate(trend.values):
        if v: ax.text(i, v / 1e6, f'{v / 1e6:.2f}', ha='center', va='bottom', fontsize=8, color=GREY)
    ax.set_ylabel('млн тг')
    # оплаты
    ax = fig.add_subplot(g[1, 4:6]); ax.set_title('Оплаты')
    pay = live.groupby('PayTypes').DishDiscountSumInt.sum().sort_values(ascending=False) if len(live) else pd.Series(dtype=float); pay = pay[pay > 0]
    if len(pay):
        pal = [NAVY, ORANGE, GREEN, AMBER, '#9DB2D6', GREY]
        w, _ = ax.pie(pay.values, colors=pal[:len(pay)], startangle=90, counterclock=False, wedgeprops=dict(width=0.38, edgecolor='white'))
        ax.legend(w, [f'{short(i, 14)} {v / pay.sum() * 100:.0f}%' for i, v in pay.items()], loc='upper center', bbox_to_anchor=(0.5, 0.02), frameon=False, fontsize=9, ncol=2)
        ax.text(0, 0, m(pay.sum()), ha='center', va='center', fontsize=13, fontweight='bold', color=NAVY)
    else: ax.axis('off')
    # часы
    ax = fig.add_subplot(g[2, 0:3]); ax.set_title('Выручка по часам открытия заказа')
    if len(paid):
        h = paid.assign(h=paid.open.str[:2].astype(int)).groupby('h').net.sum(); order = list(range(10, 24)) + [0, 1, 2, 3]; h = h.reindex(order).fillna(0)
        ax.bar(range(len(h)), h.values / 1e3, color=[ORANGE if v == h.max() else '#9DB2D6' for v in h.values], width=0.72)
        ax.set_xticks(range(len(h))); ax.set_xticklabels([f'{x:02d}' for x in h.index], fontsize=9); ax.set_ylabel('тыс тг')
    # блюда
    ax = fig.add_subplot(g[2, 3:6]); ax.set_title('Топ блюд: выручка и себестоимость (цвет = FC)')
    if len(live):
        dish = live.groupby('DishName').agg(net=('DishDiscountSumInt', 'sum'), cost=('ProductCostBase.ProductCost', 'sum')).sort_values('net', ascending=False).head(8)[::-1]
        dish['fc'] = dish.cost / dish.net * 100
        ax.barh(range(len(dish)), dish.net / 1e3, color=[fc_color(v) for v in dish.fc], height=0.66)
        ax.set_yticks(range(len(dish))); ax.set_yticklabels([short(i, 26) for i in dish.index], fontsize=9)
        for i, (n_, f_) in enumerate(zip(dish.net, dish.fc)): ax.text(n_ / 1e3, i, f'  {m(n_)} · FC {f_:.0f}%', va='center', fontsize=8.5, color=GREY)
        ax.set_xlim(0, dish.net.max() / 1e3 * 1.45); ax.set_xlabel('тыс тг')
    # удаления
    ax = fig.add_subplot(g[3, 0:2]); ax.set_title('Удаления по официантам')
    if len(dl):
        w_ = dl.groupby('waiter').agg(s=('DishSumInt', 'sum'), a=('DishSumInt', lambda x: x[dl.loc[x.index, 'printed']].sum())).sort_values('s', ascending=False).head(6)[::-1]
        ax.barh(range(len(w_)), (w_.s - w_.a) / 1e3, color='#9DB2D6', height=0.62, label='до печати'); ax.barh(range(len(w_)), w_.a / 1e3, left=(w_.s - w_.a) / 1e3, color=RED, height=0.62, label='после печати')
        ax.set_yticks(range(len(w_))); ax.set_yticklabels([short(i, 16) for i in w_.index], fontsize=9); ax.legend(frameon=False, fontsize=8.5, loc='lower right'); ax.set_xlabel('тыс тг')
    else:
        ax.axis('off'); ax.text(0.5, 0.5, 'Удалений нет', ha='center', va='center', color=GREEN, fontsize=14, transform=ax.transAxes)
    # риски
    ax = fig.add_subplot(g[3, 2:4]); ax.set_title('Опасные операции'); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis('off')
    for i, (r, col, lab) in enumerate([(3, RED, 'критич.'), (2, AMBER, 'высокий'), (1, '#E6D34A', 'средний')]):
        cx = 0.17 + i * 0.3; ax.add_patch(Circle((cx, 0.72), 0.11, fc=col if cnt[r] else '#E3E7EE', ec='none')); ax.text(cx, 0.72, str(cnt[r]), ha='center', va='center', fontsize=20, color='white' if cnt[r] else GREY, fontweight='bold'); ax.text(cx, 0.48, lab, ha='center', fontsize=9.5, color=GREY)
    top = sorted(items, key=lambda x: (-x[0], -x[3]))[:4]
    for i, it in enumerate(top): ax.text(0.02, 0.32 - i * 0.085, f'• {short(it[1], 28)}: {short(it[2], 42)}', fontsize=8.6, color=NAVY, va='center')
    if not top: ax.text(0.5, 0.25, 'Нарушений не найдено', ha='center', color=GREEN, fontsize=12)
    # деньги
    ax = fig.add_subplot(g[3, 4:6]); ax.set_title('Деньги и расходы'); ax.axis('off'); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    cash = live[live.PayTypes == 'Наличные'].DishDiscountSumInt.sum() if len(live) else 0; card = live[live.PayTypes == 'Банковские карты'].DishDiscountSumInt.sum() if len(live) else 0
    rows = [('Наличные (выручка)', cash), ('Карты (выручка)', card), ('Выплаты из кассы', payout), ('Прочие расходы', other), ('Закупки (накладные)', purch)]
    for i, (a, b) in enumerate(rows):
        y = 0.84 - i * 0.16; ax.text(0.02, y, a, fontsize=10.5, color=GREY, va='center'); ax.text(0.98, y, f'{b:,.0f} тг'.replace(',', ' '), fontsize=11, color=NAVY, ha='right', va='center', fontweight='bold'); ax.plot([0.02, 0.98], [y - 0.075] * 2, color='#E3E7EE', lw=0.8)
    fig.text(0.975, 0.012, f'сформировано {dt.datetime.now(TZ):%d.%m.%Y %H:%M} · «{RESTAURANT}» · iiko', ha='right', fontsize=8.5, color=GREY)
    out = (out_dir or OUTBOX); out = pathlib_path(out); out.mkdir(parents=True, exist_ok=True)
    fn = out / f'dashboard_{d}.png'; fig.savefig(fn, facecolor=fig.get_facecolor()); plt.close(fig); return str(fn)

def pathlib_path(p):
    import pathlib; return pathlib.Path(p)

def period_dashboard(k, d0, d1_incl, title, prev0, prev1_incl):
    d1 = d1_incl + dt.timedelta(days=1); df = day_lines(k, d0, d1); live = df[~df.deleted]; ot = order_totals(df); paid = ot[~ot.nopay]
    rev = live.DishDiscountSumInt.sum(); ndays = (d1_incl - d0).days + 1
    pdf = day_lines(k, prev0, prev1_incl + dt.timedelta(days=1)); prev_rev = pdf[~pdf.deleted].DishDiscountSumInt.sum() if len(pdf) else 0
    daily = live.groupby('OpenDate.Typed').DishDiscountSumInt.sum(); daily.index = pd.to_datetime(daily.index.str[:10])
    pd_ = pdf[~pdf.deleted].groupby('OpenDate.Typed').DishDiscountSumInt.sum() if len(pdf) else pd.Series(dtype=float)
    dl = df[df.deleted & (df.DishSumInt > 0)]; gross = df.DishSumInt.sum()
    inv = k.incoming(d0, d1_incl); inv = inv[inv.status == 'PROCESSED'] if len(inv) else inv
    fig = plt.figure(figsize=(16, 10.5), dpi=110, facecolor=LIGHT)
    title_band(fig, f'{RESTAURANT.upper()} · {title}', f'{rus_date(d0)} – {rus_date(d1_incl)}')
    g = gs.GridSpec(3, 6, figure=fig, left=0.075, right=0.975, top=0.925, bottom=0.05, hspace=0.45, wspace=0.62, height_ratios=[0.62, 1.55, 1.5])
    delta = (rev / prev_rev - 1) * 100 if prev_rev else None
    tile(fig.add_subplot(g[0, 0:2]), 'Выручка за период', f'{m(rev)} тг', f'{delta:+.0f}% к прошлому периоду ({m(prev_rev)})' if delta is not None else '', GREEN if (delta or 0) >= 0 else RED, GREEN if (delta or 0) >= 0 else RED)
    tile(fig.add_subplot(g[0, 2]), 'Чеков', f'{len(paid)}', f'гостей {int(paid.guests.sum())}')
    tile(fig.add_subplot(g[0, 3]), 'Средний чек', f'{rev / len(paid) if len(paid) else 0:,.0f} тг'.replace(',', ' '), f'в день {m(rev / ndays)}')
    tile(fig.add_subplot(g[0, 4]), 'Удалено', f'{dl.DishSumInt.sum() / gross * 100 if gross else 0:.1f}%', f'после печати {m(dl[dl.printed].DishSumInt.sum())} тг', AMBER, GREY)
    tile(fig.add_subplot(g[0, 5]), 'Закупки', f'{m(inv["sum"].sum() if len(inv) else 0)} тг', f'{(inv["sum"].sum() / rev * 100 if rev and len(inv) else 0):.0f}% выручки')
    ax = fig.add_subplot(g[1, 0:4]); ax.set_title('Выручка по дням (столбцы) и прошлый период (линия)')
    ax.bar(range(len(daily)), daily.values / 1e6, color='#9DB2D6', width=0.72)
    if len(pd_):
        pv = pd_.values[:len(daily)] / 1e6; ax.plot(range(len(pv)), pv, color=ORANGE, lw=2, marker='o', ms=4)
    ax.set_xticks(range(len(daily))); ax.set_xticklabels([f'{x.day:02d}\n{wd(x.date())}' if ndays <= 16 else (f'{x.day:02d}' if x.day % 2 else '') for x in daily.index], fontsize=8.5); ax.set_ylabel('млн тг')
    ax = fig.add_subplot(g[1, 4:6]); ax.set_title('Закупки: поставщики')
    if len(inv):
        s = inv.groupby('supplier')['sum'].sum().sort_values(ascending=False); top = s.head(6); other = s.iloc[6:].sum(); vals = list(top.values) + ([other] if other else []); labs = [short(i, 16) for i in top.index] + (['прочие'] if other else [])
        w, _ = ax.pie(vals, colors=[NAVY, ORANGE, GREEN, AMBER, '#9DB2D6', GREY, '#C9CFDA'][:len(vals)], startangle=90, counterclock=False, wedgeprops=dict(width=0.38, edgecolor='white'))
        ax.legend(w, [f'{a} {v / sum(vals) * 100:.0f}%' for a, v in zip(labs, vals)], loc='upper center', bbox_to_anchor=(0.5, 0.02), frameon=False, fontsize=8.5, ncol=2)
    ax = fig.add_subplot(g[2, 0:3]); ax.set_title('Топ блюд: выручка и себестоимость (цвет = FC)')
    dish = live.groupby('DishName').agg(net=('DishDiscountSumInt', 'sum'), cost=('ProductCostBase.ProductCost', 'sum')).sort_values('net', ascending=False).head(8)[::-1]; dish['fc'] = dish.cost / dish.net * 100
    ax.barh(range(len(dish)), dish.net / 1e3, color=[fc_color(v) for v in dish.fc], height=0.66); ax.set_yticks(range(len(dish))); ax.set_yticklabels([short(i, 26) for i in dish.index], fontsize=9)
    for i, (n_, f_) in enumerate(zip(dish.net, dish.fc)): ax.text(n_ / 1e3, i, f'  {m(n_)} · FC {f_:.0f}%', va='center', fontsize=8.5, color=GREY)
    ax.set_xlim(0, dish.net.max() / 1e3 * 1.45)
    ax = fig.add_subplot(g[2, 3:6]); ax.set_title('Удаления по официантам')
    if len(dl):
        w_ = dl.groupby('waiter').DishSumInt.sum().sort_values(ascending=False).head(7)[::-1]; ax.barh(range(len(w_)), w_.values / 1e3, color='#9DB2D6', height=0.62)
        ax.set_yticks(range(len(w_))); ax.set_yticklabels([short(i, 20) for i in w_.index], fontsize=9); ax.set_xlabel('тыс тг')
    fig.text(0.975, 0.012, f'сформировано {dt.datetime.now(TZ):%d.%m.%Y %H:%M} · «{RESTAURANT}» · iiko', ha='right', fontsize=8.5, color=GREY)
    fn = OUTBOX / f'dashboard_{d0}_{d1_incl}.png'; fig.savefig(fn, facecolor=fig.get_facecolor()); plt.close(fig); return str(fn)
