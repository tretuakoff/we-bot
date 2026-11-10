"""Недельный отчёт в формате аудита (Audit_HIVA_iiko): те же листы и стиль, данные за неделю."""
import datetime as dt, pandas as pd, numpy as np
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from ..config import *
from ..util import *
from .. import daydata

HDR = PatternFill('solid', fgColor='1F3864'); RED = PatternFill('solid', fgColor='F8CBAD'); ORG = PatternFill('solid', fgColor='FFE699'); GRN = PatternFill('solid', fgColor='C6E0B4'); YEL = PatternFill('solid', fgColor='FFF2CC')

class Book:
    def __init__(self): self.wb = Workbook(); self.wb.remove(self.wb.active)
    def sheet(self, name):
        ws = self.wb.create_sheet(name[:31]); ws.sheet_view.showGridLines = False; ws._r = 1; return ws
    def title(self, ws, text, sub=None):
        ws.cell(ws._r, 1, text).font = Font(bold=True, size=13, color='1F3864'); ws._r += 1
        if sub: c = ws.cell(ws._r, 1, sub); c.font = Font(italic=True, color='595959'); ws._r += 1
        ws._r += 0
    def table(self, ws, df, idx=False, title=None, note=None, pct=(), fills=None):
        if title: ws._r += 1; ws.cell(ws._r, 1, title).font = Font(bold=True, size=11, color='1F3864'); ws._r += 1
        if note: c = ws.cell(ws._r, 1, note); c.font = Font(italic=True, color='595959'); ws._r += 1
        d = df.reset_index() if idx else df.copy(); r0 = ws._r
        if not len(d.columns): return
        for j, c in enumerate(d.columns, 1):
            x = ws.cell(r0, j, str(c)); x.font = Font(bold=True, color='FFFFFF'); x.fill = HDR; x.alignment = Alignment(wrap_text=True, vertical='center')
        for i, row in enumerate(d.itertuples(index=False), 1):
            for j, v in enumerate(row, 1):
                if hasattr(v, 'item'): v = v.item()
                if isinstance(v, float) and (v != v or v in (float('inf'), float('-inf'))): v = None
                if isinstance(v, (pd.Timestamp, dt.date)): v = str(v)[:10]
                c = ws.cell(r0 + i, j, v); nm = str(d.columns[j - 1])
                if isinstance(v, (int, float)) and not isinstance(v, bool): c.number_format = '0.0' if ('%' in nm or nm in pct) else '#,##0'
                if isinstance(v, str) and len(v) > 70: c.alignment = Alignment(wrap_text=True, vertical='top')
                if v == '🔴': c.fill = RED
                elif v == '🟠': c.fill = ORG
                elif v == '🟡': c.fill = YEL
                if fills and nm in fills and isinstance(v, (int, float)) and v: c.fill = fills[nm](v) or PatternFill()
        ws._r = r0 + len(d) + 2
    def text(self, ws, lines, height=34, span=8):
        for t in lines:
            c = ws.cell(ws._r, 1, '• ' + t); c.alignment = Alignment(wrap_text=True, vertical='top'); ws.merge_cells(start_row=ws._r, start_column=1, end_row=ws._r, end_column=span); ws.row_dimensions[ws._r].height = height; ws._r += 1
    def widths(self, ws, w):
        for i, x in enumerate(w, 1): ws.column_dimensions[get_column_letter(i)].width = x

def _flat(days):
    O, P, X, C, I, D, S, A, E = [], [], [], [], [], [], [], [], []
    for d in days:
        for o in d['orders']:
            live = [l for l in o['l'] if l[4] == 0]
            O.append(dict(Дата=d['date'], Время=o['t'], Стол=o['tb'], Гостей=o['gu'], Официант=o['w'], Кассир=o['ca'], Сумма_меню=o['g'], Выручка=o['n'], Скидка=o['dc'], Удалено=o['dt'], После_печати=o['da'],
                          Оплата=o['pay'], Без_оплаты=o['np'], Банкет=o['bq'], VIP=o['vip'], Себестоимость=sum(l[5] for l in live), Заказ=o['k'], Блюда=', '.join(l[0] for l in o['l'][:3]), lines=o['l']))
        for p in d['purchases']:
            for l in p['l']: P.append(dict(Дата=d['date'], Накладная=p['doc'], Поставщик=p['sup'], Статус=p['st'], Склад=p['store'], Товар=l[0], Ед=l[1], Кол_во=l[2], Цена=l[3], Сумма=l[4], Была=l[5], Изм_pct=l[6], Группа=l[7]))
        for e in d['expenses']: X.append(dict(Дата=d['date'], Статья=e[0], Тип=e[1], Операция=e[2], За_что=e[3], Сумма=e[4], Документ=e[5]))
        for e in d['cash']: C.append(dict(Дата=d['date'], Счёт=e[0], Операция=e[1], Приход=e[2], Расход=e[3], Описание=e[4], Документ=e[5]))
        for e in d.get('inv', []): I.append(dict(Дата=d['date'], Склад=e[0], Товар=e[1], Кол_во=e[2], Сумма=e[3], Акт=e[4]))
        for e in d['danger']: D.append(dict(Дата=d['date'], Риск={3: '🔴', 2: '🟠', 1: '🟡'}[e[0]], Категория=e[1], Описание=e[2], Сумма=e[3], Что_проверить=e[4]))
        for e in d['shifts']: S.append(dict(Дата=d['date'], Смена=e[0], Кассир=e[1], Открыта=e[2], Закрыта=e[3], Наличные=e[4], Карта=e[5], Расхождение=e[6], Статус=e[7]))
        for e in d.get('access', []): A.append(dict(Дата=d['date'], Время=e[0], Событие=e[1], Кому=e[2], Право=e[3], Что_сделали=e[4], Кто_изменил=e[5]))
        for e in d.get('edits', []): E.append(dict(Дата=d['date'], Время=e[0], Кто=e[1], Действие=e[2], Документ=e[3] + ' №' + e[4]))
        for e in d.get('cons', []): pass
    return [pd.DataFrame(x) for x in (O, P, X, C, I, D, S, A, E)]

def _kpi(O):
    if not len(O): return dict(rev=0, checks=0, avg=0, guests=0, del_=0, aft=0, disc=0, comp=0, cost=0, gross=0)
    paid = O[(O.Без_оплаты == 0) & (O.Выручка > 0)]
    return dict(rev=O.Выручка.sum(), checks=len(paid), avg=O.Выручка.sum() / len(paid) if len(paid) else 0, guests=paid.Гостей.sum(), del_=O.Удалено.sum(), aft=O.После_печати.sum(), disc=O.Скидка.sum(),
                comp=O[O.Без_оплаты == 1].Сумма_меню.sum(), cost=O.Себестоимость.sum(), gross=O.Сумма_меню.sum() + O.Удалено.sum())

def build(k, d0, d1):
    days = daydata.get_range(k, d0, d1); pd0 = d0 - dt.timedelta(days=7); pd1 = d1 - dt.timedelta(days=7); pdays = daydata.get_range(k, pd0, pd1)
    O, P, X, C, I, D, S, A, E = _flat(days); PO = _flat(pdays)[0]; K, PK = _kpi(O), _kpi(PO)
    bk = Book(); ndays = (d1 - d0).days + 1
    tx = k.olap('TRANSACTIONS', ['Account.Name', 'Account.Type', 'TransactionType'], ['Sum.ResignedSum'], d0, d1 + dt.timedelta(days=1))
    def dlt(a, b): return f'{(a / b - 1) * 100:+.0f}%' if b else '—'
    # ---- Executive Summary
    ws = bk.sheet('Executive Summary'); bk.title(ws, f'НЕДЕЛЬНЫЙ ОТЧЁТ — ресторан «{RESTAURANT}»', f'Период: {rus_date(d0)} – {rus_date(d1)} · сравнение с {rus_date(pd0)} – {rus_date(pd1)} · источник: iiko')
    pur = P[P.Статус == 'PROCESSED'].Сумма.sum() if len(P) else 0
    ex = X[(X.Тип.isin(['EXPENSES', 'OTHER_EXPENSES'])) & (~X.Статья.isin(['Зарплата', 'Дивиденды']))].Сумма.sum() if len(X) else 0
    kp = pd.DataFrame([['Выручка (нетто)', K['rev'], PK['rev'], dlt(K['rev'], PK['rev']), f'{K["rev"] / ndays:,.0f} ₸ в день'.replace(',', ' ')],
                       ['Чеков', K['checks'], PK['checks'], dlt(K['checks'], PK['checks']), f'гостей {int(K["guests"])}'],
                       ['Средний чек', K['avg'], PK['avg'], dlt(K['avg'], PK['avg']), ''],
                       ['Продажи по меню до удалений', K['gross'], PK['gross'], dlt(K['gross'], PK['gross']), ''],
                       ['Удалено (по меню)', K['del_'], PK['del_'], dlt(K['del_'], PK['del_']), f'{K["del_"] / K["gross"] * 100 if K["gross"] else 0:.1f}% продаж'],
                       ['  из них после печати', K['aft'], PK['aft'], dlt(K['aft'], PK['aft']), 'главный риск: блюдо ушло на кухню'],
                       ['Скидки', K['disc'], PK['disc'], dlt(K['disc'], PK['disc']), ''], ['Комплименты (без оплаты)', K['comp'], PK['comp'], dlt(K['comp'], PK['comp']), ''],
                       ['Себестоимость по меню (расчётная)', K['cost'], PK['cost'], dlt(K['cost'], PK['cost']), f'{K["cost"] / K["rev"] * 100 if K["rev"] else 0:.1f}% выручки'],
                       ['Закупки', pur, None, '', f'{pur / K["rev"] * 100 if K["rev"] else 0:.0f}% выручки'], ['Прочие расходы (без ФОТ и дивидендов)', ex, None, '', ''],
                       ['Опасных операций', len(D), None, '', f'критических: {int((D.Риск == "🔴").sum()) if len(D) else 0}, высоких: {int((D.Риск == "🟠").sum()) if len(D) else 0}']],
                      columns=['Показатель', 'Неделя', 'Пред. неделя', 'Δ', 'Комментарий'])
    bk.table(ws, kp)
    concl = []
    if K['gross'] and K['del_'] / K['gross'] > 0.05: concl.append(f'Удаления {K["del_"] / K["gross"] * 100:.1f}% продаж — выше нормы 3%. Включить обязательную причину удаления.')
    if K['aft'] > 0: concl.append(f'Есть удаления ПОСЛЕ печати на {money(K["aft"])} — разобрать каждое (лист «Удаления»).')
    if K['rev'] and K['cost'] / K['rev'] > 0.45: concl.append(f'Расчётная себестоимость {K["cost"] / K["rev"] * 100:.0f}% — выше 45%; см. лист «Food cost и маржа».')
    if PK['rev'] and K['rev'] < PK['rev'] * 0.9: concl.append(f'Выручка упала на {abs((K["rev"] / PK["rev"] - 1) * 100):.0f}% к прошлой неделе.')
    if len(D) and (D.Риск == '🔴').any(): concl.append(f'Критических опасных операций: {int((D.Риск == "🔴").sum())} — лист «Опасные операции».')
    if not concl: concl.append('Существенных отклонений за неделю не найдено.')
    ws._r += 0; ws.cell(ws._r, 1, 'Главные выводы недели').font = Font(bold=True, size=12, color='1F3864'); ws._r += 1; bk.text(ws, concl, 32, 5); bk.widths(ws, [42, 18, 18, 12, 60])
    # ---- P&L
    ws = bk.sheet('P&L неделя'); bk.title(ws, 'P&L за неделю по проводкам iiko, ₸', 'Зарплата в iiko проводится пакетами (аванс/расчёт) — недельный % ФОТ не показателен; смотрите месячный отчёт.')
    if len(tx):
        g = tx.groupby(['Account.Type', 'Account.Name'])['Sum.ResignedSum'].sum().reset_index(); inc = g[g['Account.Type'] == 'INCOME']['Sum.ResignedSum'].sum()
        cg = g[g['Account.Type'] == 'COST_OF_GOODS_SOLD']['Sum.ResignedSum'].sum(); sal = g[g['Account.Name'] == 'Зарплата']['Sum.ResignedSum'].sum(); dv = g[g['Account.Name'] == 'Дивиденды']['Sum.ResignedSum'].sum()
        oth = g[g['Account.Type'].isin(['EXPENSES', 'OTHER_EXPENSES']) & ~g['Account.Name'].isin(['Зарплата', 'Дивиденды'])]['Sum.ResignedSum'].sum()
        pl = pd.DataFrame([['Выручка (доходные счета)', inc], ['Себестоимость (COGS)', cg], ['Валовая прибыль', inc - cg], ['Зарплата выплачена', sal], ['Прочие расходы', oth], ['Результат до аренды/налогов', inc - cg - sal - oth], ['Дивиденды (не расход)', dv]], columns=['Статья', '₸']); bk.table(ws, pl)
        bk.table(ws, g[g['Account.Type'].isin(['INCOME', 'COST_OF_GOODS_SOLD', 'EXPENSES', 'OTHER_EXPENSES', 'OTHER_INCOME'])].rename(columns={'Account.Type': 'Тип', 'Account.Name': 'Счёт', 'Sum.ResignedSum': '₸'}).sort_values('₸', key=abs, ascending=False), title='Все статьи за неделю')
    bk.widths(ws, [48, 32, 18])
    # ---- Выручка
    ws = bk.sheet('Выручка'); bk.title(ws, 'Выручка: дни, дни недели, часы, оплата')
    if len(O):
        day = O.groupby('Дата').apply(lambda g: pd.Series(dict(Выручка=g.Выручка.sum(), Чеков=((g.Без_оплаты == 0) & (g.Выручка > 0)).sum(), Гостей=g.Гостей.sum(), Скидки=g.Скидка.sum(), Удалено=g.Удалено.sum()))); day['Ср. чек'] = day.Выручка / day.Чеков
        day['Δ % к пред. неделе'] = [(v / PO.Выручка.sum() * 7 - 1) * 100 if len(PO) else None for v in day.Выручка]; bk.table(ws, day, idx=True, title='По дням')
        O['Час'] = O.Время.str[:2]; h = O.groupby('Час').agg(Выручка=('Выручка', 'sum'), Заказов=('Заказ', 'count')); bk.table(ws, h, idx=True, title='По часам открытия заказа')
        pay = O.groupby('Оплата').Выручка.sum().sort_values(ascending=False).to_frame('Выручка'); pay['Доля %'] = pay.Выручка / pay.Выручка.sum() * 100; bk.table(ws, pay, idx=True, title='По оплатам')
    bk.widths(ws, [22, 16, 12, 12, 14, 14, 12, 20])
    # ---- Удаления
    ws = bk.sheet('Удаления'); bk.title(ws, 'Удаления', 'Не доказательство нарушения — очередь на проверку. «До печати» = блюдо на кухню не печаталось.')
    if len(O):
        dl = O[O.Удалено > 0]
        if len(dl):
            bk.table(ws, dl.groupby('Официант').agg(Удалено=('Удалено', 'sum'), После_печати=('После_печати', 'sum'), Заказов=('Заказ', 'count')).sort_values('Удалено', ascending=False), idx=True, title='По официантам')
            bk.table(ws, dl.groupby('Кассир').agg(Удалено=('Удалено', 'sum'), После_печати=('После_печати', 'sum'), Заказов=('Заказ', 'count')).sort_values('Удалено', ascending=False), idx=True, title='По кассирам')
            bk.table(ws, dl.sort_values('Удалено', ascending=False).head(60)[['Дата', 'Время', 'Стол', 'Официант', 'Кассир', 'Удалено', 'После_печати', 'Блюда']], title='ТОП-60 заказов по сумме удаления')
            dd = []
            for _, o in dl.iterrows():
                for l in o.lines:
                    if l[4] > 0: dd.append([l[0], l[2], 'после печати' if l[4] == 3 else 'до печати'])
            if dd: bk.table(ws, pd.DataFrame(dd, columns=['Блюдо', 'Сумма', 'Когда']).groupby(['Блюдо', 'Когда']).Сумма.agg(['sum', 'count']).reset_index().rename(columns={'sum': 'Сумма', 'count': 'Строк'}).sort_values('Сумма', ascending=False).head(25), title='ТОП-25 удалённых блюд')
    bk.widths(ws, [28, 14, 14, 14, 24, 14, 14, 50])
    # ---- Скидки и комплименты
    ws = bk.sheet('Скидки и комплименты'); bk.title(ws, 'Скидки и комплименты')
    if len(O):
        sc = O[O.Скидка > 0]; cp = O[(O.Без_оплаты == 1) & (O.Сумма_меню > 0)]
        bk.table(ws, sc[['Дата', 'Время', 'Стол', 'Официант', 'Кассир', 'Сумма_меню', 'Скидка']].sort_values('Скидка', ascending=False) if len(sc) else pd.DataFrame({'Скидок за неделю нет': []}), title=f'Скидки: {money(sc.Скидка.sum())}')
        bk.table(ws, cp[['Дата', 'Время', 'Стол', 'Официант', 'Кассир', 'Сумма_меню', 'Блюда']] if len(cp) else pd.DataFrame({'Комплиментов за неделю нет': []}), title=f'Заказы без оплаты (комплименты): {money(cp.Сумма_меню.sum())}')
    bk.widths(ws, [14, 10, 10, 26, 26, 14, 40])
    # ---- Опасные операции
    ws = bk.sheet('Опасные операции'); bk.title(ws, 'Опасные операции за неделю', '🔴 критический · 🟠 высокий · 🟡 средний. Это очередь на проверку, а не обвинения.')
    if len(D):
        D['o'] = D.Риск.map({'🔴': 0, '🟠': 1, '🟡': 2}); bk.table(ws, D.sort_values(['o', 'Сумма'], ascending=[True, False]).drop(columns='o'), title=f'Всего: {len(D)}')
        bk.table(ws, D.groupby(['Риск', 'Категория']).size().rename('Кол-во').reset_index(), title='Свод по категориям')
    else: ws.cell(ws._r, 1, '✅ Опасных операций за неделю не найдено')
    bk.widths(ws, [12, 8, 30, 70, 14, 50])
    # ---- Закупки и поставщики
    ws = bk.sheet('Закупки и поставщики'); bk.title(ws, 'Закупки и поставщики')
    if len(P):
        Pp = P[P.Статус == 'PROCESSED']
        sp = Pp.groupby('Поставщик').agg(Сумма=('Сумма', 'sum'), Накладных=('Накладная', 'nunique'), Позиций=('Товар', 'count')).sort_values('Сумма', ascending=False); sp['Доля %'] = sp.Сумма / sp.Сумма.sum() * 100
        bk.table(ws, sp, idx=True, title=f'Закупки за неделю: {money(Pp.Сумма.sum())}'); bk.table(ws, Pp.groupby('Группа').Сумма.sum().sort_values(ascending=False).to_frame('Сумма'), idx=True, title='По группам')
        bk.table(ws, Pp.groupby(['Дата', 'Накладная', 'Поставщик']).Сумма.sum().reset_index(), title='Накладные')
        bad = P[P.Статус != 'PROCESSED']
        if len(bad): bk.table(ws, bad.groupby(['Дата', 'Накладная', 'Поставщик']).Сумма.sum().reset_index(), title='Удалённые/непроведённые накладные')
    bk.widths(ws, [30, 16, 14, 12, 12])
    # ---- Цены и переплаты
    ws = bk.sheet('Цены и переплаты'); bk.title(ws, 'Изменение цен закупки', 'Сравнение с прошлой закупкой того же товара (у того же поставщика, а если его не было — у любого).')
    if len(P):
        ch = P[(P.Статус == 'PROCESSED') & P.Изм_pct.notna() & (P.Изм_pct.abs() >= PRICE_ALERT_PCT)].copy(); ch['Доп. затраты'] = (ch.Цена - ch.Была) * ch.Кол_во
        bk.table(ws, ch.sort_values('Доп. затраты', ascending=False)[['Дата', 'Поставщик', 'Товар', 'Ед', 'Кол_во', 'Была', 'Цена', 'Изм_pct', 'Доп. затраты']].rename(columns={'Изм_pct': 'Δ %'}) if len(ch) else pd.DataFrame({'Существенных изменений цен нет': []}), title=f'Изменения ≥{PRICE_ALERT_PCT}%: {len(ch)} позиций, итого {money(ch["Доп. затраты"].sum() if len(ch) else 0)}')
        # переплата к лучшему поставщику
        Pp = P[P.Статус == 'PROCESSED']; best = Pp.groupby(['Товар', 'Поставщик']).apply(lambda g: g.Сумма.sum() / g.Кол_во.sum()).reset_index(name='p')
        if len(best):
            mn = best.groupby('Товар').p.min().rename('Лучшая цена'); j = best.join(mn, on='Товар'); j = j[(j.p > j['Лучшая цена'] * 1.05)].merge(Pp.groupby(['Товар', 'Поставщик']).Кол_во.sum().reset_index(), on=['Товар', 'Поставщик'])
            j['Переплата'] = (j.p - j['Лучшая цена']) * j.Кол_во
            if len(j): bk.table(ws, j.sort_values('Переплата', ascending=False).head(30).rename(columns={'p': 'Цена'}), title='Дороже, чем у другого поставщика на этой неделе')
    bk.widths(ws, [14, 28, 30, 8, 10, 12, 12, 10, 14])
    # ---- Инвентаризации
    ws = bk.sheet('Инвентаризации'); bk.title(ws, 'Инвентаризации за неделю', '«+» излишек, «−» недостача (проводки iiko).')
    if len(I):
        docs = I.groupby(['Дата', 'Акт', 'Склад']).apply(lambda g: pd.Series(dict(Недостача=g[g.Сумма < 0].Сумма.sum(), Излишек=g[g.Сумма > 0].Сумма.sum(), Позиций=len(g)))).reset_index(); bk.table(ws, docs, title='Акты')
        bk.table(ws, I.sort_values('Сумма').head(40)[['Дата', 'Склад', 'Товар', 'Кол_во', 'Сумма', 'Акт']], title='ТОП-40 недостач'); bk.table(ws, I.sort_values('Сумма', ascending=False).head(25)[['Дата', 'Склад', 'Товар', 'Кол_во', 'Сумма', 'Акт']], title='ТОП-25 излишков')
    else: ws.cell(ws._r, 1, 'Инвентаризаций за неделю не было')
    bk.widths(ws, [14, 22, 34, 12, 14, 10])
    # ---- Списания
    ws = bk.sheet('Списания'); bk.title(ws, 'Списания (акты)')
    try:
        wo = k.writeoffs(d0, d1)
        if len(wo):
            wo = wo[wo.status == 'PROCESSED']; bk.table(ws, wo.groupby('account').cost.agg(['sum', 'count']).rename(columns={'sum': 'Сумма', 'count': 'Строк'}).sort_values('Сумма', ascending=False), idx=True, title=f'По причинам (итого {money(wo.cost.sum())})')
            bk.table(ws, wo.groupby('pname').agg(Сумма=('cost', 'sum'), Кол_во=('amount', 'sum')).sort_values('Сумма', ascending=False).head(30), idx=True, title='ТОП-30 товаров')
        else: ws.cell(ws._r, 1, 'Актов списания за неделю нет')
    except Exception as e: ws.cell(ws._r, 1, f'Не удалось загрузить акты: {e}')
    bk.widths(ws, [36, 16, 12])
    # ---- Food cost и маржа
    ws = bk.sheet('Food cost и маржа'); bk.title(ws, 'Food cost и маржа по блюдам', 'Себестоимость — расчётная по ТТК iiko (ProductCostBase).')
    if len(O):
        rows = []
        for _, o in O.iterrows():
            for l in o.lines:
                if l[4] == 0: rows.append([l[0], l[1], l[3], l[5]])
        if rows:
            dsh = pd.DataFrame(rows, columns=['Блюдо', 'Порций', 'Выручка', 'Себестоимость']).groupby('Блюдо').sum().reset_index(); dsh['FC %'] = dsh.Себестоимость / dsh.Выручка * 100; dsh['Маржа'] = dsh.Выручка - dsh.Себестоимость
            bk.table(ws, dsh.sort_values('Маржа', ascending=False).head(30), title='ТОП-30 по прибыли'); bk.table(ws, dsh[dsh.Выручка > 15000].sort_values('FC %', ascending=False).head(25), title='ТОП-25 по проблемности (FC%)', fills={'FC %': lambda v: RED if v > 55 else ORG if v > 45 else None})
    bk.widths(ws, [40, 12, 14, 14, 10, 14])
    # ---- Cash flow
    ws = bk.sheet('Cash flow'); bk.title(ws, 'Деньги: движение по счетам и кассовые смены')
    if len(C):
        bk.table(ws, C.groupby(['Счёт', 'Операция']).agg(Приход=('Приход', 'sum'), Расход=('Расход', 'sum')).reset_index(), title='Движение по денежным счетам')
        big = C[C.Расход >= 20000].sort_values('Расход', ascending=False).head(40); bk.table(ws, big[['Дата', 'Счёт', 'Операция', 'Расход', 'Описание']], title='Крупнейшие расходы')
    if len(S): bk.table(ws, S, title='Кассовые смены', fills={'Расхождение': lambda v: RED if v else None})
    bk.widths(ws, [14, 28, 24, 16, 16, 40])
    # ---- Персонал
    ws = bk.sheet('Персонал (Risk Matrix)'); bk.title(ws, 'Operational Risk Matrix', 'Индекс — ранг удалений/скидок/комплиментов. НЕ означает вину: у админов часть операций — их должностная функция.')
    if len(O):
        st = O.groupby('Официант').apply(lambda g: pd.Series(dict(Выручка=g.Выручка.sum(), Чеков=((g.Без_оплаты == 0) & (g.Выручка > 0)).sum(), Удалено=g.Удалено.sum(), После_печати=g.После_печати.sum(), Скидки=g.Скидка.sum(), Комплименты=g[g.Без_оплаты == 1].Сумма_меню.sum())))
        st['Удалено %'] = st.Удалено / (st.Выручка + st.Удалено).replace(0, np.nan) * 100; st = st[st.Выручка > 20000]
        st['Индекс риска'] = (0.5 * st['Удалено %'].rank(pct=True) + 0.25 * st.Скидки.rank(pct=True) + 0.25 * st.После_печати.rank(pct=True)) * 100
        bk.table(ws, st.sort_values('Индекс риска', ascending=False).head(40), idx=True, title='Официанты')
        ck = O.groupby('Кассир').agg(Выручка=('Выручка', 'sum'), Удалено=('Удалено', 'sum'), После_печати=('После_печати', 'sum'), Скидки=('Скидка', 'sum')); bk.table(ws, ck.sort_values('Выручка', ascending=False), idx=True, title='Кассиры')
    bk.widths(ws, [30, 14, 10, 14, 14, 14, 14, 12, 12])
    # ---- Отзывы 2ГИС
    ws = bk.sheet('Отзывы 2ГИС'); bk.title(ws, 'Отзывы 2ГИС за неделю')
    try:
        from . import reviews as rvm
        rv, meta = rvm.fetch(days=(today() - d0).days + 3, max_pages=15); rv = [r for r in rv if d0 <= r['created'].date() <= d1]
        ws.cell(ws._r, 1, f'Рейтинг: {meta.get("branch_rating")} · всего отзывов: {meta.get("branch_reviews_count")} · за неделю: {len(rv)}, негативных: {sum(1 for r in rv if r["rating"] <= NEGATIVE_RATING_MAX)}'); ws._r += 1
        bk.table(ws, pd.DataFrame([dict(Дата=r['created'].strftime('%Y-%m-%d %H:%M'), Оценка=r['rating'], Автор=r['author'], Отзыв=r['text']) for r in sorted(rv, key=lambda x: x['rating'])]) if rv else pd.DataFrame({'Отзывов за неделю нет': []}))
    except Exception as e: ws.cell(ws._r, 1, f'Не удалось загрузить отзывы: {e}')
    bk.widths(ws, [20, 10, 26, 100])
    # ---- Действия пользователей
    ws = bk.sheet('Действия пользователей'); bk.title(ws, 'Права доступа и правки документов (журнал событий iiko)')
    bk.table(ws, A if len(A) else pd.DataFrame({'Изменений прав за неделю нет': []}), title='Изменения прав доступа')
    if len(E): bk.table(ws, E.groupby(['Кто', 'Действие']).size().rename('Событий').reset_index().sort_values('Событий', ascending=False), title='Правки и удаления документов (свод)'); bk.table(ws, E.head(150), title='Журнал правок (первые 150)')
    bk.widths(ws, [14, 10, 26, 26, 24, 22, 22])
    # ---- Потери
    ws = bk.sheet('Потери (3 типа)'); bk.title(ws, 'Сколько теряется за неделю: подтверждённые / вероятные / потенциальные, ₸', 'Категории не пересекаются. Это оценка для приоритизации, а не сумма хищений.')
    inv_short = -I[I.Сумма < 0].Сумма.sum() if len(I) else 0
    cost_comp = O[O.Без_оплаты == 1].Себестоимость.sum() if len(O) else 0
    wo_sum = wo.cost.sum() if 'wo' in locals() and len(wo) else 0
    del_cost = sum(l[5] for _, o in O.iterrows() for l in o.lines if l[4] > 0) if len(O) else 0
    over = 0
    if len(P):
        Pp = P[P.Статус == 'PROCESSED']; bp = Pp.groupby(['Товар', 'Поставщик']).apply(lambda g: g.Сумма.sum() / g.Кол_во.sum()).reset_index(name='p'); mn = bp.groupby('Товар').p.min().rename('m'); q = Pp.groupby(['Товар', 'Поставщик']).Кол_во.sum().reset_index(); bp = bp.join(mn, on='Товар').merge(q, on=['Товар', 'Поставщик']); over = ((bp.p - bp.m).clip(lower=0) * bp.Кол_во).sum()
    loss = pd.DataFrame([['1. Подтверждённые', 'Недостачи инвентаризаций', inv_short], ['1. Подтверждённые', 'Скидки', K['disc']], ['1. Подтверждённые', 'Комплименты (себестоимость)', cost_comp], ['1. Подтверждённые', 'Акты списания (порча, питание, представительские)', wo_sum],
                         ['2. Вероятные', 'Переплата поставщикам к лучшей цене недели', over], ['3. Потенциальные', 'Себестоимость удалённых позиций (если выданы без оплаты)', del_cost]], columns=['Тип', 'Статья', '₸'])
    bk.table(ws, loss); tot = loss.groupby('Тип')['₸'].sum().to_frame('Итого ₸'); tot['% выручки'] = tot['Итого ₸'] / K['rev'] * 100 if K['rev'] else 0; bk.table(ws, tot, idx=True, title='Итого'); bk.widths(ws, [22, 60, 16])
    # ---- Red Flags
    ws = bk.sheet('Red Flags'); bk.title(ws, 'Красные флаги: пороги и значения недели')
    dp = K['del_'] / K['gross'] * 100 if K['gross'] else 0; fcp = K['cost'] / K['rev'] * 100 if K['rev'] else 0
    def flag(v, r, o): return '🔴' if v > r else '🟠' if v > o else '🟢'
    rf = pd.DataFrame([['Удаления % продаж', '> 3%', f'{dp:.1f}%', flag(dp, 8, 3)], ['Удаления после печати', 'любое', money(K['aft']), '🔴' if K['aft'] > 0 else '🟢'], ['Скидки % выручки', '> 1,5%', f'{K["disc"] / K["rev"] * 100 if K["rev"] else 0:.1f}%', flag(K['disc'] / K['rev'] * 100 if K['rev'] else 0, 3, 1.5)],
                       ['Комплименты', '> 0,3% выручки', money(K['comp']), '🟠' if K['comp'] > 0.003 * K['rev'] else '🟢'], ['Расчётный food cost', '> 42%', f'{fcp:.1f}%', flag(fcp, 50, 42)],
                       ['Смены с расхождением', '≠ 0', str(int((S.Расхождение != 0).sum()) if len(S) else 0), '🟠' if len(S) and (S.Расхождение != 0).any() else '🟢'], ['Опасные операции 🔴', 'любые', str(int((D.Риск == '🔴').sum()) if len(D) else 0), '🔴' if len(D) and (D.Риск == '🔴').any() else '🟢'],
                       ['Изменения прав доступа', '> 5 за неделю', str(len(A)), '🔴' if len(A) > 5 else '🟢'], ['Инвентаризационная недостача', '> 1,5% себестоимости', money(inv_short), '🟠' if K['cost'] and inv_short > 0.015 * K['cost'] else '🟢']], columns=['Флаг', 'Порог', 'Значение', 'Статус'])
    bk.table(ws, rf); bk.widths(ws, [40, 24, 20, 10])
    # ---- План
    ws = bk.sheet('План на неделю'); bk.title(ws, 'Что сделать на этой неделе (автоматически по данным)')
    todo = []
    if K['aft'] > 0: todo.append('Разобрать удаления после печати: кто, что, было ли блюдо выдано (лист «Удаления»).')
    if dp > 5: todo.append('Включить обязательную причину удаления и пароль менеджера.')
    if len(D) and (D.Риск == '🔴').any(): todo.append('Проверить все критические операции (лист «Опасные операции»).')
    if len(S) and (S.Расхождение != 0).any(): todo.append('Смены с расхождением: получить акты сдачи выручки.')
    if len(A): todo.append('Проверить изменения прав доступа: кто и почему менял (лист «Действия пользователей»).')
    if over > 20000: todo.append(f'Переплата поставщикам {money(over)}: согласовать единую цену с лучшим поставщиком.')
    if fcp > 45: todo.append('Пересчитать себестоимость меню для блюд с высоким FC.')
    todo.append('Сверить остатки: позиции с отрицательным остатком — ввести накладные или провести инвентаризацию.')
    bk.text(ws, todo, 30, 3); bk.widths(ws, [110, 10, 10])
    fn = OUTBOX / f'Отчёт_недели_{d0}_{d1}.xlsx'; bk.wb.save(fn); return str(fn)
