from .base import *
import json
from ..config import STATE

PERM_FILE = STATE / 'permissions_ru.json'   # можно дописать перевод кодов прав: {"F_CLOR": "Открывать смену", ...}
CHANGE_TYPES = {'userPermissionChanged': 'Права сотрудника', 'rolePermissionChanged': 'Права роли', 'userCreated': 'Создан сотрудник', 'userUpdated': 'Изменён сотрудник', 'userDeleted': 'Удалён сотрудник'}

def perm_name(code):
    m = json.loads(PERM_FILE.read_text()) if PERM_FILE.exists() else {}
    return m.get(code, code)

def build(k, d, rolling_hours=None):
    if rolling_hours:
        t1 = dt.datetime.now(TZ).replace(tzinfo=None); ev = k.events(t1 - dt.timedelta(hours=rolling_hours), t1)
        lines = [f'<b>{esc(RESTAURANT)} · Доступы и права</b>\nза последние {rolling_hours} ч']
    else:
        ev = events_day(k, d); lines = [header('Доступы и права', d)]
    if not len(ev): return [lines[0] + '\n\nНет данных.'], []
    ch = ev[ev.type.isin(CHANGE_TYPES)].copy()
    if not len(ch): return [lines[0] + '\n\n✅ Изменений доступов за период нет.'], []
    lines.append(f'Изменений: {len(ch)} · сотрудников затронуто: {ch.get("userName", pd.Series(dtype=str)).nunique()}')
    emp = k.employees()
    ch['target'] = ch.get('userName'); 
    if 'userId' in ch: ch['target'] = ch.target.fillna(ch.userId.map(emp))
    unknown = set()
    for tgt, g in ch.groupby(ch.target.fillna('(роль/не указано)')):
        by = g.groupby('who').size().to_dict()
        txt = f'<b>{esc(tgt)}</b> — изменил(а): ' + ', '.join(f'{esc(w)} ({n})' for w, n in by.items()) + f' · {g.dt.min().strftime("%d.%m %H:%M")}'
        rows = []
        for _, e in g.sort_values('dt').iterrows():
            code = e.get('permissionCode'); code = code if isinstance(code, str) and code else None; st = {'ALLOW': '✅ разрешено', 'DENY': '⛔ запрещено', 'DEFAULT': '↺ по умолчанию'}.get(e.get('permissionState'), CHANGE_TYPES.get(e.get('type')))
            if code: rows.append([e['dt'].strftime('%H:%M'), perm_name(code), st])
            else: rows.append([e['dt'].strftime('%H:%M'), CHANGE_TYPES.get(e.get('type')), ''])
            if code and perm_name(code) == code: unknown.add(code)
        txt += '\n' + pre(rows[:25], ['Время', 'Право', 'Что сделали']) + (f'\n… и ещё {len(rows) - 25}' if len(rows) > 25 else '')
        # что этот сотрудник делал за период
        mine = ev[ev.who == tgt]
        if len(mine):
            c = mine.type.value_counts()
            ops = []
            for key, lab in [('orderDeleted', 'удалено заказов'), ('deletedNewItems', 'удалено неотпеч. строк'), ('deletedPrintedItems', 'удалено отпечатанных'), ('orderDiscounted', 'скидок'),
                             ('orderPrepayReturned', 'возвратов предоплаты'), ('Изъятая сумма', 'изъятий из кассы'), ('documentModified', 'правок документов'), ('documentCreated', 'создано документов'),
                             ('accountingTransactionCreated', 'ручных проводок'), ('accountingTransactionDeleted', 'удалено проводок'), ('permissionChecked', 'запросов разрешений')]:
                if c.get(key): ops.append(f'{lab}: {c[key]}')
            txt += '\nОперации сотрудника за период: ' + (esc('; '.join(ops)) if ops else 'не совершал операций, требующих контроля')
        else: txt += '\nОперации сотрудника за период: нет'
        lines.append(txt)
    if unknown: lines.append('Коды прав без расшифровки: ' + ', '.join(sorted(unknown)) + ' (перевод можно дописать в state/permissions_ru.json)')
    return ['\n\n'.join(lines)], []
