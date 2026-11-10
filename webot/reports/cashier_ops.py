from .base import *

def build(k, d):
    """Операции кассиров ТОЛЬКО после печати на кухню (правки до печати не показываем)."""
    df = day_lines(k, d); ev = events_day(k, d); lines = [header('Операции кассиров (после печати)', d)]
    if not len(df): return [lines[0] + '\n\nНет данных.'], []
    aft = df[df.deleted & df.printed & (df.DishSumInt > 0)]
    disc = df[(~df.deleted) & (df.DiscountSum > 0)]
    comps = df[(~df.deleted) & df.nopay & (df.DishSumInt > 0)]
    per = {}
    def add(cashier, kind, text, amount=0):
        per.setdefault(cashier or '—', []).append((kind, text, amount))
    for _, r in aft.iterrows(): add(r.cashier, 'Удалено после печати', f'{r.open} ст.{r.TableNum} {r.DishName} ({short(r.waiter, 12)})', r.DishSumInt)
    for key, g in disc.groupby('key'):
        r = g.iloc[0]; s = g.DiscountSum.sum(); base = g.DishSumInt.sum()
        add(r.cashier, 'Скидка', f'{r.open} ст.{r.TableNum} ({short(r.waiter, 12)}) {pct(s / base * 100 if base else 0, 0)} «{r["OrderDiscount.Type"] or "ручная"}»', s)
    for key, g in comps.groupby('key'):
        r = g.iloc[0]; add(r.cashier, 'Заказ без оплаты', f'{r.open} ст.{r.TableNum} ({short(r.waiter, 12)}) {short(", ".join(list(dict.fromkeys(g.DishName))[:2]), 30)}', g.DishSumInt.sum())
    if len(ev):
        for _, e in ev.iterrows():
            t = e.get('type'); who = e.get('who'); tm = e['dt'].strftime('%H:%M') if pd.notna(e.get('dt')) else ''
            sm = pd.to_numeric(e.get('sum'), errors='coerce'); sm = 0 if pd.isna(sm) else abs(sm)
            if t == 'deletedPrintedItems': add(who, 'Удалено после печати (журнал)', f'{tm} ст.{e.get("tableNum")} {e.get("dishes")}', 0)
            elif t == 'orderPrepayReturned': add(who, 'Возврат предоплаты', f'{tm} ст.{e.get("tableNum")}', abs(pd.to_numeric(e.get('orderSumAfterDiscount'), errors='coerce') or 0))
            elif t in ('Изъятая сумма', 'payOutMade'): add(who, 'Выплата/изъятие из кассы', f'{tm} {e.get("name") or ""} {short(e.get("comment") or "", 26)}', sm)
            elif t == 'orderDiscountDeleted': add(who, 'Снята скидка', f'{tm} ст.{e.get("tableNum")}', 0)
            elif t == 'orderMoved': pass
            elif t == 'permissionChecked' and 'отпечатан' in str(e.get('permissionName', '')).lower():
                add(who, 'Разрешение: ' + short(e.get('permissionName'), 40), f'{tm} {"выдано" if str(e.get("success")) == "1" else "ОТКАЗАНО"}', 0)
    if not per: return [lines[0] + '\n\n✅ Операций после печати за день нет (удаления, скидки, заказы без оплаты, возвраты, изъятия).'], []
    tot = sum(a for v in per.values() for _, _, a in v)
    lines.append(f'Операций: {sum(len(v) for v in per.values())} на {money(tot)}. Правки до печати в этот отчёт не входят.')
    for c, ops in sorted(per.items(), key=lambda x: -sum(a for _, _, a in x[1])):
        s = sum(a for _, _, a in ops)
        rows = [[k_, short(t_, 44), money(a)] for k_, t_, a in sorted(ops, key=lambda x: -x[2])[:12]]
        lines.append(f'<b>{esc(c)}</b> · {len(ops)} оп. · {money(s)}\n' + pre(rows, ['Операция', 'Детали', 'Сумма']))
    return ['\n\n'.join(lines)], []
