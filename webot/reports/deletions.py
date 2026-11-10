from .base import *

def build(k, d):
    df = day_lines(k, d); lines = [header('Удаления', d)]
    if not len(df): return [lines[0] + '\n\nНет продаж.'], []
    dl = df[df.deleted & (df.DishSumInt > 0)]
    gross = df.DishSumInt.sum()
    if not len(dl): return [lines[0] + '\n\n✅ Удалений за день нет.'], []
    aft = dl[dl.printed]; bef = dl[~dl.printed]
    lines.append(f'<b>Удалено (по ценам меню): {money(dl.DishSumInt.sum())} = {pct(dl.DishSumInt.sum() / gross * 100)} продаж</b> ({len(dl)} строк, себестоимость ≈{money(dl["ProductCostBase.ProductCost"].sum())})')
    lines.append(f'• до печати на кухню: {money(bef.DishSumInt.sum())} ({len(bef)} строк) — правки заказа\n• 🔴 после печати: {money(aft.DishSumInt.sum())} ({len(aft)} строк)')
    def who(col, n=8):
        g = dl.groupby(col).agg(s=('DishSumInt', 'sum'), a=('DishSumInt', lambda x: x[dl.loc[x.index, 'printed']].sum()))
        base = df.groupby(col).DishSumInt.sum()
        g['pct'] = g.s / base.reindex(g.index) * 100
        return pre([[short(i, 24), money(r.s), pct(r.pct, 0), money(r.a)] for i, r in g.sort_values('s', ascending=False).head(n).iterrows()], ['', 'Удалено', '% продаж', 'после печати'])
    lines.append('<b>По официантам</b>\n' + who('waiter')); lines.append('<b>По кассирам</b>\n' + who('cashier', 6))
    o = dl.groupby('key').agg(open=('open', 'first'), table=('TableNum', 'first'), waiter=('waiter', 'first'), cashier=('cashier', 'first'), s=('DishSumInt', 'sum'), n=('DishName', 'count'),
                              a=('printed', 'sum'), full=('OrderDeleted', lambda x: (x == 'DELETED').any()), dishes=('DishName', lambda x: ', '.join(list(dict.fromkeys(x))[:2])),
                              reason=('DeletionComment', lambda x: next((v for v in x if isinstance(v, str) and v.strip()), ''))).sort_values('s', ascending=False)
    top = o[o.s >= 10000].head(10)
    if len(top):
        lines.append('<b>Крупнейшие заказы с удалениями</b>\n' + pre([[r.open, f'ст.{r.table}', short(r.waiter, 12), money(r.s), ('заказ целиком' if r.full else 'позиции') + (' ⚠после печати' if r.a else ''), short(r.dishes, 26)] for _, r in top.iterrows()],
                                                                    ['Время', 'Стол', 'Офиц.', 'Сумма', 'Что', 'Блюда']))
    rs = dl.groupby(dl.DeletionComment.fillna('').replace('', '(причина не указана)')).DishSumInt.sum().sort_values(ascending=False).head(5)
    lines.append('Причины: ' + '; '.join(f'{esc(short(i, 30))} — {money(v)}' for i, v in rs.items()))
    if len(aft): lines.append('<b>🔴 Удалено после печати (детально)</b>\n' + pre([[r.open, short(r.waiter, 12), short(r.cashier, 12), short(r.DishName, 24), money(r.DishSumInt), short(r.DeletionComment or '', 16)] for _, r in aft.sort_values('DishSumInt', ascending=False).head(15).iterrows()], ['Открыт', 'Офиц.', 'Кассир', 'Блюдо', 'Сумма', 'Причина']))
    return ['\n\n'.join(lines)], []
