from .base import *

def banquet_orders(df):
    ot = order_totals(df)
    if not len(ot): return ot
    vip = df.groupby('key').apply(lambda g: pd.Series(dict(
        vip_paid=((g.DishName == VIP_DISH) & ~g.deleted).any(), vip_del=((g.DishName == VIP_DISH) & g.deleted).any(),
        company=g.DishName.str.contains('НА КОМПАНИЮ', case=False, na=False).any())))
    ot = ot.join(vip)
    m = (ot.gross >= BANQUET_MIN_SUM) | (ot.guests >= BANQUET_MIN_GUESTS) | ot.vip_paid | ot.vip_del | ot.company | ot.table.astype(str).isin(VIP_TABLES) & (ot.gross >= 30000)
    return ot[m]

def build(k, d):
    df = day_lines(k, d); lines = [header('Банкеты и крупные заказы', d)]
    if not len(df): return [lines[0] + '\n\nНет данных.'], []
    b = banquet_orders(df)
    if not len(b): return [lines[0] + '\n\nБанкетов и крупных заказов за день не было.'], []
    lines.append(f'Заказов: {len(b)} на {money(b.net.sum())} (критерии: от {money(BANQUET_MIN_SUM)} по меню, от {BANQUET_MIN_GUESTS} гостей, «НА КОМПАНИЮ», VIP-стол, аренда VIP)')
    flags_total = 0
    for key, r in b.sort_values('gross', ascending=False).iterrows():
        g = df[df.key == key]; live = g[~g.deleted]; dele = g[g.deleted & (g.DishSumInt > 0)]
        flags = []
        # скидка
        disc = live.DiscountSum.sum(); dtypes = ', '.join(sorted({str(x) for x in live['OrderDiscount.Type'] if x})) or ('ручная' if disc else '')
        disc_txt = f'ДА: {money(disc)} ({pct(disc / live.DishSumInt.sum() * 100, 0)}) {dtypes}' if disc > 0 else 'нет'
        if disc > 0: flags.append('скидка')
        # VIP
        is_vip_table = str(r.table) in VIP_TABLES
        vip_l = live[live.DishName == VIP_DISH]; vip_d = g[(g.DishName == VIP_DISH) & g.deleted]
        if len(vip_l): vip_txt = f'✅ пробит: {money(vip_l.DishDiscountSumInt.sum())} ({int(vip_l.DishAmountInt.sum())} ед.)'
        elif len(vip_d): vip_txt = f'🔴 пробит и УДАЛЁН: {money(vip_d.DishSumInt.sum())}'; flags.append('VIP удалён')
        elif is_vip_table: vip_txt = '🔴 НЕ пробит (стол VIP)'; flags.append('VIP не пробит')
        elif r.guests >= BANQUET_MIN_GUESTS: vip_txt = 'ℹ️ не пробит (компания ' + str(int(r.guests)) + ' гост., стол не VIP) — проверить, не было ли брони'
        else: vip_txt = 'не требуется (обычный стол)'
        # удаления
        aft = dele[dele.printed]
        if len(aft): flags.append('удаление после печати')
        if r.nopay: flags.append('без оплаты')
        dishes = live.groupby('DishName').agg(q=('DishAmountInt', 'sum'), s=('DishSumInt', 'sum')).sort_values('s', ascending=False)
        dl = ', '.join(f'{n} ×{q:g}' for n, q in dishes.q.head(8).items()) + (f' и ещё {len(dishes) - 8}' if len(dishes) > 8 else '')
        head = f'<b>{"🔴 " if flags else ""}Стол {esc(r.table)} · {r.open}–{r.close} · {int(r.guests)} гост.</b>\nОфициант: {esc(r.waiter)} · Кассир: {esc(r.cashier)}\nСумма: {money(r.net)} (по меню {money(r.gross)}) · оплата: {esc(r.pay)}'
        body = f'Блюда: {esc(dl)}\nСкидка: {esc(disc_txt)}\nАренда VIP: {esc(vip_txt)}'
        if len(dele): body += f'\nУдалено: {money(dele.DishSumInt.sum())} (до печати {money(dele[~dele.printed].DishSumInt.sum())}, после печати {money(aft.DishSumInt.sum())}): {esc(short(", ".join(list(dict.fromkeys(dele.DishName))[:4]), 90))}'
        if flags: body += '\n⚠️ ' + esc('; '.join(flags)); flags_total += 1
        lines.append(head + '\n' + body)
    if flags_total: lines.insert(1, f'⚠️ Требуют внимания: {flags_total} из {len(b)}')
    return ['\n\n'.join(lines)], []
