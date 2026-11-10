"""Еженедельный (пн) и ежемесячный (28-го) отчёты о деятельности + Excel."""
import calendar
from .base import *
from . import dangerous, reviews
from ..config import OUTBOX, SLUG

def _range_stats(k, d0, d1):
    """d1 не включительно."""
    daily = k.olap('SALES', ['OpenDate.Typed', 'PayTypes'], ['DishDiscountSumInt', 'DishSumInt', 'DiscountSum', 'UniqOrderId.OrdersCount', 'GuestNum', 'ProductCostBase.ProductCost'], d0, d1)
    if not len(daily): return None
    daily['d'] = pd.to_datetime(daily['OpenDate.Typed'].str[:10])
    return daily

def _kpi(daily):
    if daily is None or not len(daily): return dict(rev=0, gross=0, disc=0, orders=0, guests=0, cost=0)
    d = daily[daily.PayTypes != '(без оплаты)'] if False else daily
    return dict(rev=daily.DishDiscountSumInt.sum(), gross=daily.DishSumInt.sum(), disc=daily.DiscountSum.sum(), orders=daily['UniqOrderId.OrdersCount'].sum(), guests=daily.GuestNum.sum(), cost=daily['ProductCostBase.ProductCost'].sum())

def _cmp(a, b, money_=True):
    if not b: return ''
    return f' ({pct((a / b - 1) * 100, 0, True)})'

def build(k, d0, d1_incl, title, prev0, prev1_incl, forecast_days=None):
    """d0..d1_incl — период (включительно); prev — сравнение."""
    d1 = d1_incl + dt.timedelta(days=1); p1 = prev1_incl + dt.timedelta(days=1)
    cur = _range_stats(k, d0, d1); prv = _range_stats(k, prev0, p1)
    lines = [f'<b>{esc(RESTAURANT)} · {esc(title)}</b>\n{rus_date(d0)} – {rus_date(d1_incl)}  (сравнение: {rus_date(prev0)} – {rus_date(prev1_incl)})']
    if cur is None: return [lines[0] + '\n\nПродаж за период нет.'], []
    K, P = _kpi(cur), _kpi(prv)
    # чек-счёт по неоплаченным исключаем: возьмём по заказам
    lines_df = day_lines(k, d0, d1)
    live = lines_df[~lines_df.deleted]; ot = order_totals(lines_df); paid = ot[~ot.nopay]
    checks = len(paid); guests = paid.guests.sum(); rev = live.DishDiscountSumInt.sum()
    plines = day_lines(k, prev0, p1); plive = plines[~plines.deleted] if len(plines) else plines; pot = order_totals(plines) if len(plines) else pd.DataFrame(); ppaid = pot[~pot.nopay] if len(pot) else pot
    prev_rev = plive.DishDiscountSumInt.sum() if len(plive) else 0; prev_checks = len(ppaid)
    ndays = (d1_incl - d0).days + 1
    lines.append(f'💰 <b>Выручка: {money(rev)}</b>{_cmp(rev, prev_rev)} · в день {money(rev / ndays)}\nЧеков: {checks}{_cmp(checks, prev_checks)} · Гостей: {int(guests)} · Средний чек: {money(rev / checks if checks else 0)}' + (f' (было {money(prev_rev / prev_checks)})' if prev_checks else ''))
    if forecast_days:
        lines.append(f'📈 Прогноз на месяц ({forecast_days} дн.) при текущем темпе: {money(rev / ndays * forecast_days)}')
    # по дням
    dd = live.groupby('OpenDate.Typed').DishDiscountSumInt.sum()
    rows = [[f'{rus_date(dt.date.fromisoformat(str(i)[:10]))[:5]} {wd(dt.date.fromisoformat(str(i)[:10]))}', money(v)] for i, v in dd.items()]
    if ndays <= 8: lines.append(pre(rows, ['День', 'Выручка']))
    else:
        wk = live.assign(w=pd.to_datetime(live['OpenDate.Typed'].str[:10]).dt.to_period('W-SUN').astype(str)).groupby('w').DishDiscountSumInt.sum()
        lines.append('По неделям\n' + pre([[i.replace('/', ' – ')[5:10] + ' – ' + i.split('/')[1][5:10] if False else (i.split('/')[0][8:10] + '.' + i.split('/')[0][5:7] + ' – ' + i.split('/')[1][8:10] + '.' + i.split('/')[1][5:7]), money(v)] for i, v in wk.items()], ['Неделя', 'Выручка']))
    bd = live.assign(wd=pd.to_datetime(live['OpenDate.Typed'].str[:10]).dt.weekday).groupby('wd').DishDiscountSumInt.sum()
    if len(bd) >= 5: lines.append('Дни недели: ' + ', '.join(f'{WD[i]} {money(v / max(1, sum(1 for x in pd.date_range(d0, d1_incl) if x.weekday() == i)))}' for i, v in bd.items()) + ' (среднее за день)')
    pay = live.groupby('PayTypes').DishDiscountSumInt.sum().sort_values(ascending=False)
    lines.append('Оплаты: ' + ', '.join(f'{esc(i)} {pct(v / rev * 100, 0)}' for i, v in pay.items() if v))
    # блюда и себестоимость
    dish = live.groupby(['DishGroup', 'DishName']).agg(q=('DishAmountInt', 'sum'), net=('DishDiscountSumInt', 'sum'), cost=('ProductCostBase.ProductCost', 'sum')).reset_index()
    dish['fc'] = dish.cost / dish.net * 100; dish['margin'] = dish.net - dish.cost
    cost = live['ProductCostBase.ProductCost'].sum()
    lines.append(f'🍽 <b>Себестоимость по меню (расчётная): {pct(cost / rev * 100 if rev else 0)}</b>' + (f' (было {pct(plive["ProductCostBase.ProductCost"].sum() / prev_rev * 100)})' if prev_rev else ''))
    lines.append('<b>Топ-8 блюд по выручке</b>\n' + pre([[short(r.DishName, 28), int(r.q), money(r.net), pct(r.fc, 0)] for _, r in dish.sort_values('net', ascending=False).head(8).iterrows()], ['Блюдо', 'Порций', 'Выручка', 'FC']))
    bad = dish[(dish.net > 20000 * ndays / 7) & (dish.fc > 55)].sort_values('net', ascending=False).head(6)
    if len(bad): lines.append('⚠️ Блюда с высокой себестоимостью (>55%): ' + '; '.join(f'{esc(r.DishName)} {pct(r.fc, 0)}' for _, r in bad.iterrows()))
    # удаления и скидки
    dl = lines_df[lines_df.deleted & (lines_df.DishSumInt > 0)]; gross = lines_df.DishSumInt.sum()
    lines.append(f'🗑 Удалено: {money(dl.DishSumInt.sum())} = {pct(dl.DishSumInt.sum() / gross * 100 if gross else 0)} продаж (до печати {money(dl[~dl.printed].DishSumInt.sum())}, <b>после печати {money(dl[dl.printed].DishSumInt.sum())}</b>)\n'
                 f'🏷 Скидки: {money(live.DiscountSum.sum())} ({pct(live.DiscountSum.sum() / live.DishSumInt.sum() * 100 if len(live) else 0)}) · без оплаты (комплименты): {money(lines_df[(~lines_df.deleted) & lines_df.nopay].DishSumInt.sum())}')
    top_del = dl.groupby('waiter').DishSumInt.sum().sort_values(ascending=False).head(5)
    if len(top_del): lines.append('Удаления по официантам: ' + ', '.join(f'{esc(short(i, 18))} {money(v)}' for i, v in top_del.items()))
    # закупки
    inv = k.incoming(d0, d1_incl); inv = inv[inv.status == 'PROCESSED'] if len(inv) else inv
    pinv = k.incoming(prev0, prev1_incl); pinv = pinv[pinv.status == 'PROCESSED'] if len(pinv) else pinv
    pur = inv['sum'].sum() if len(inv) else 0; ppur = pinv['sum'].sum() if len(pinv) else 0
    lines.append(f'🛒 <b>Закупки: {money(pur)}</b>{_cmp(pur, ppur)} = {pct(pur / rev * 100 if rev else 0)} выручки')
    if len(inv):
        bs = inv.groupby('supplier')['sum'].sum().sort_values(ascending=False).head(6)
        lines.append(pre([[short(i, 28), money(v), pct(v / pur * 100, 0)] for i, v in bs.items()], ['Поставщик', 'Сумма', 'Доля']))
    # изменение цен по периодам
    pchg = None
    if len(inv) and len(pinv):
        a = inv.groupby('pname').apply(lambda g: g['sum'].sum() / g.amount.sum()); b = pinv.groupby('pname').apply(lambda g: g['sum'].sum() / g.amount.sum())
        q = inv.groupby('pname').amount.sum(); j = pd.DataFrame({'now': a, 'prev': b, 'q': q}).dropna(); j['chg'] = (j.now / j.prev - 1) * 100; j['eff'] = (j.now - j.prev) * j.q
        j = j.replace([float('inf'), float('-inf')], float('nan')).dropna(); j = j[(j.chg.abs() >= PRICE_ALERT_PCT) & (j.eff.abs() >= 3000) & (j.prev > 0)]; pchg = j
        up = j[j.chg > 0].sort_values('eff', ascending=False).head(6); dn = j[j.chg < 0].sort_values('eff').head(4)
        if len(up): lines.append('⬆ Подорожали (ср. цена к прошлому периоду): ' + '; '.join(f'{esc(short(i, 20))} {pct(r.chg, 0, True)} ({money(r.eff, True)})' for i, r in up.iterrows()))
        if len(dn): lines.append('⬇ Подешевели: ' + '; '.join(f'{esc(short(i, 20))} {pct(r.chg, 0, True)} ({money(r.eff, True)})' for i, r in dn.iterrows()))
    # финансы из проводок
    tx = k.olap('TRANSACTIONS', ['Account.Name', 'Account.Type', 'TransactionType'], ['Sum.ResignedSum', 'Sum.Incoming', 'Sum.Outgoing'], d0, d1)
    fin = {}
    if len(tx):
        e = tx[tx['Account.Type'].isin(['EXPENSES', 'OTHER_EXPENSES'])]
        sal = e[e['Account.Name'] == 'Зарплата']['Sum.ResignedSum'].sum(); div = e[e['Account.Name'] == 'Дивиденды']['Sum.ResignedSum'].sum()
        oth = e[~e['Account.Name'].isin(['Зарплата', 'Дивиденды'])]['Sum.ResignedSum'].sum()
        cogs = tx[tx['Account.Type'] == 'COST_OF_GOODS_SOLD']['Sum.ResignedSum'].sum()
        inv_c = tx[(tx.TransactionType == 'INVENTORY_CORRECTION') & (tx['Account.Type'] == 'INVENTORY_ASSETS')]
        short_ = inv_c[inv_c['Sum.ResignedSum'] < 0]['Sum.ResignedSum'].sum(); surp = inv_c[inv_c['Sum.ResignedSum'] > 0]['Sum.ResignedSum'].sum()
        fin = dict(sal=sal, div=div, oth=oth, cogs=cogs, short=short_, surp=surp)
        weekly_ = ndays <= 8
        lines.append(f'📊 <b>Финансы по проводкам iiko</b>\nСебестоимость (списание+инвентаризации): {money(cogs)} = {pct(cogs / rev * 100 if rev else 0)}\nЗарплата выплачена: {money(sal)}' + ('' if weekly_ else f' = {pct(sal / rev * 100 if rev else 0)} выручки') + f' · Прочие расходы: {money(oth)} · Дивиденды: {money(div)}\n'
                     f'Инвентаризации за период: недостачи {money(short_)} · излишки {money(surp, True)}')
        if weekly_: lines.append('ℹ️ Зарплата выдаётся пакетами (аванс/расчёт), поэтому %ФОТ и Prime Cost считаются в месячном отчёте.')
        else:
            lines.append(f'Оценка операц. прибыли (до аренды/налогов): {money(rev - cogs - sal - oth)} = {pct((rev - cogs - sal - oth) / rev * 100 if rev else 0)}\nPrime Cost (себестоимость + ФОТ): {pct((cogs + sal) / rev * 100 if rev else 0)} (ориентир 60–65%)\nℹ️ Зарплата в iiko проводится по факту выплат и до конца месяца показывается неполной — прибыль и Prime Cost предварительные.')
    # опасные операции за период (по дням)
    from collections import Counter
    cnt = Counter(); allitems = []
    for i in range(ndays):
        day = d0 + dt.timedelta(days=i)
        try:
            for it in dangerous.collect(k, day): cnt[(it[0], it[1])] += 1; allitems.append((day,) + it)
        except Exception as e: print('period/dangerous', day, e)
    if cnt:
        crit = sorted(cnt.items(), key=lambda x: (-x[0][0], -x[1]))[:10]
        lines.append('🚨 <b>Опасные операции за период</b>\n' + pre([[dangerous.RISK[r], short(c, 34), n] for (r, c), n in crit], ['', 'Категория', 'Кол-во']))
    else: lines.append('🚨 Опасных операций за период не найдено.')
    # отзывы
    try:
        if TWOGIS_BRANCH_ID:
            rv, meta = reviews.fetch(days=max(ndays, 7)); rv = [r for r in rv if d0 <= r['created'].date() <= d1_incl]
            neg = [r for r in rv if r['rating'] <= NEGATIVE_RATING_MAX]
            lines.append(f'⭐ 2ГИС: рейтинг {meta.get("branch_rating", "—")}, за период отзывов {len(rv)}, негативных {len(neg)}')
    except Exception as e: print('reviews', e)
    # авто-выводы
    tips = []
    if dl.DishSumInt.sum() / gross * 100 > 5: tips.append('удаления выше 5% продаж — включить обязательную причину удаления')
    if len(dl[dl.printed]) > 0: tips.append(f'есть удаления после печати ({money(dl[dl.printed].DishSumInt.sum())}) — разобрать каждое')
    if fin and ndays > 8 and fin['sal'] / rev * 100 > 35: tips.append('ФОТ выше 35% выручки — сверить табель и график')
    if fin and fin['short'] < -0.02 * cost: tips.append('недостачи инвентаризаций выше 2% — усилить контроль склада')
    if pchg is not None and len(pchg[pchg.chg > 10]) >= 3: tips.append('несколько позиций подорожали более чем на 10% — пересмотреть поставщиков')
    if tips: lines.append('💡 <b>На что обратить внимание</b>\n' + '\n'.join('• ' + esc(t) for t in tips))
    # Excel
    fn = OUTBOX / f'{SLUG or "we"}_{"week" if ndays <= 8 else "month"}_{d0}_{d1_incl}.xlsx'
    with pd.ExcelWriter(fn, engine='openpyxl') as xw:
        dd2 = live.groupby('OpenDate.Typed').agg(Выручка=('DishDiscountSumInt', 'sum'), Скидки=('DiscountSum', 'sum'), Себестоимость=('ProductCostBase.ProductCost', 'sum')); dd2.to_excel(xw, sheet_name='По дням')
        dish.sort_values('net', ascending=False).rename(columns={'DishGroup': 'Группа', 'DishName': 'Блюдо', 'q': 'Порций', 'net': 'Выручка', 'cost': 'Себестоимость', 'fc': 'FC %', 'margin': 'Маржа'}).to_excel(xw, sheet_name='Блюда', index=False)
        if len(inv): inv.groupby(['supplier', 'pname']).agg(кг=('amount', 'sum'), сумма=('sum', 'sum'), цена=('price', 'mean')).reset_index().to_excel(xw, sheet_name='Закупки', index=False)
        if pchg is not None and len(pchg): pchg.reset_index().rename(columns={'pname': 'Товар', 'now': 'Цена сейчас', 'prev': 'Цена раньше', 'q': 'Кол-во', 'chg': 'Δ %', 'eff': 'Эффект ₸'}).to_excel(xw, sheet_name='Изменение цен', index=False)
        if len(dl): dl[['OpenDate.Typed', 'open', 'TableNum', 'waiter', 'cashier', 'DishName', 'DishSumInt', 'printed', 'DeletionComment']].rename(columns={'OpenDate.Typed': 'Дата', 'open': 'Время', 'TableNum': 'Стол', 'waiter': 'Официант', 'cashier': 'Кассир', 'DishName': 'Блюдо', 'DishSumInt': 'Сумма', 'printed': 'После печати', 'DeletionComment': 'Причина'}).to_excel(xw, sheet_name='Удаления', index=False)
        if allitems: pd.DataFrame(allitems, columns=['Дата', 'Риск', 'Категория', 'Описание', 'Сумма', 'Что проверить']).to_excel(xw, sheet_name='Опасные операции', index=False)
        if len(tx): tx.groupby(['Account.Type', 'Account.Name'])['Sum.ResignedSum'].sum().reset_index().to_excel(xw, sheet_name='Проводки по счетам', index=False)
    return ['\n\n'.join(lines)], [str(fn)]

def weekly(k, today_=None):
    t = today_ or today(); end = t - dt.timedelta(days=t.weekday() + 1)   # прошлое воскресенье
    start = end - dt.timedelta(days=6)
    return build(k, start, end, 'Недельный отчёт о деятельности', start - dt.timedelta(days=7), end - dt.timedelta(days=7))

def monthly(k, today_=None):
    t = today_ or today(); end = t - dt.timedelta(days=1); start = end.replace(day=1)
    pm_end = (start - dt.timedelta(days=1)); pm_start = pm_end.replace(day=1); pm_to = pm_start.replace(day=min(end.day, pm_end.day))
    dim = calendar.monthrange(end.year, end.month)[1]
    return build(k, start, end, 'Месячный отчёт о деятельности', pm_start, pm_to, forecast_days=dim)
