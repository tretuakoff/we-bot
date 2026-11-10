from .base import *

def build(k, d):
    df = day_lines(k, d)
    if not len(df): return [header('Кассовый день', d) + '\n\nПродаж за день нет.'], []
    live = df[~df.deleted]; ot = order_totals(df)
    paid = ot[~ot.nopay]
    rev = live.DishDiscountSumInt.sum(); gross = live.DishSumInt.sum(); disc = live.DiscountSum.sum()
    checks = len(paid); guests = paid.guests.sum()
    by_pay = live.groupby('PayTypes').DishDiscountSumInt.sum().sort_values(ascending=False)
    avg_rev, avg_ch = same_weekday_avg(k, d)
    lines = [header('Кассовый день', d)]
    cmp = f' ({pct((rev / avg_rev - 1) * 100, 0, True)} к среднему {wd(d)} за 4 недели: {money(avg_rev)})' if avg_rev else ''
    lines.append(f'💰 <b>Выручка: {money(rev)}</b>{cmp}')
    lines.append(f'Чеков: {checks} · Гостей: {int(guests)} · Средний чек: {money(rev / checks if checks else 0)}')
    lines.append(f'Продажи по меню: {money(gross)} · Скидки: {money(disc)} ({pct(disc / gross * 100 if gross else 0)})')
    rows = [[p, money(v), pct(v / rev * 100 if rev else 0, 0)] for p, v in by_pay.items() if v]
    lines.append('<b>Оплаты</b>\n' + pre(rows, ['Тип', 'Сумма', 'Доля']))
    dele = df[df.deleted & (df.DishSumInt > 0)]
    lines.append(f'Удалено (по меню): {money(dele.DishSumInt.sum())} ({pct(dele.DishSumInt.sum() / df.DishSumInt.sum() * 100)} продаж), из них после печати {money(dele[dele.printed].DishSumInt.sum())}')
    hrs = paid.assign(h=paid.open.str[:2]).groupby('h').net.sum()
    if len(hrs):
        top = hrs.sort_values(ascending=False).head(3)
        lines.append('Пик по часам открытия: ' + ', '.join(f'{h}:00 — {money(v)}' for h, v in top.items()))
    # смены
    sh = k.cashshifts(d - dt.timedelta(days=1), d + dt.timedelta(days=1))
    if len(sh):
        sh = sh[(sh.openDate.dt.date == d) | ((sh.closeDate.dt.date == d) & (sh.openDate.dt.date < d))]
        rows = []
        for _, s in sh.iterrows():
            st = {'ACCEPTED': 'принята', 'UNACCEPTED': 'не принята', 'OPEN': 'открыта'}.get(s.sessionStatus, s.sessionStatus)
            rows.append([f'№{s.sessionNumber} {short(s.cashier or "", 18)}', s.openDate.strftime('%H:%M'), s.closeDate.strftime('%H:%M') if pd.notna(s.closeDate) else '—',
                         money(s.salesCash), money(s.salesCard), money(s.cashDiff, True), st])
        lines.append('<b>Кассовые смены</b>\n' + pre(rows, ['Смена', 'Откр', 'Закр', 'Нал', 'Карта', 'Расхожд.', 'Статус']))
        if (sh.cashDiff.fillna(0) != 0).any():
            lines.append('⚠️ Есть смены с расхождением наличных — см. «Опасные операции».')
    return ['\n\n'.join(lines)], []
