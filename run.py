#!/usr/bin/env python3
"""Запуск отчётов: python run.py <команда> [--date YYYY-MM-DD] [--to 7702...] [--force]
Команды: morning (дашборд + пакет за вчера), day --date (всё за день), dashboard, backfill --date ОТ [ДО], report <имя>, weekly, monthly, reviews, access, norm, list"""
import os, sys, json, argparse, traceback, subprocess, datetime as dt
if '--restaurant' in sys.argv:     # ресторан выбирается до загрузки настроек
    os.environ['WE_RESTAURANT'] = sys.argv[sys.argv.index('--restaurant') + 1]
from webot.config import *
from webot.iiko import Iiko
from webot import tg
from webot.util import *
from webot import dashboard, webdash
from webot.reports import week_xlsx
import shutil, pathlib
from webot.reports import cash_day, cash_flow, other_exp, purchases, prices, order_norm, deletions, cashier_ops, banquets, dangerous, access, reviews, period, reviews_day, journal

REPORTS = {'cash': ('Кассовый день', cash_day), 'flow': ('Приход/расход', cash_flow), 'expenses': ('Прочие расходы', other_exp), 'purchases': ('Закупки', purchases),
           'prices': ('Изменение цен', prices), 'norm': ('Норма заказа', order_norm), 'deletions': ('Удаления', deletions), 'cashiers': ('Операции кассиров', cashier_ops), 'journal': ('Журнал событий', journal),
           'banquets': ('Банкеты', banquets), 'reviews': ('Отзывы 2ГИС', reviews_day), 'dangerous': ('Опасные операции', dangerous), 'access': ('Доступы', access)}
MORNING = ['cash', 'flow', 'expenses', 'purchases', 'prices', 'deletions', 'cashiers', 'banquets', 'dangerous', 'journal', 'reviews', 'access']
SENT = STATE / f'sent_{SLUG or "default"}.json'

def _sent(): return json.loads(SENT.read_text()) if SENT.exists() else {}
def _mark(key): s = _sent(); s[key] = dt.datetime.now(TZ).isoformat(timespec='seconds'); SENT.write_text(json.dumps(s, ensure_ascii=False, indent=1))

ARCHIVE = ROOT / 'archive'
NO_ARCHIVE = CLOUD
def archive(d, name, texts=None, files=None, photos=None):
    """Архив: archive/ГГГГ-ММ-ДД/<название>.txt + дашборд + Excel — для каждого дня."""
    if NO_ARCHIVE: return
    dd = ARCHIVE / str(d); dd.mkdir(parents=True, exist_ok=True)
    if texts:
        import re as _re
        (dd / (_re.sub(r'[^\w-]', '_', name) + '.txt')).write_text('\n\n'.join(_re.sub(r'</?(b|i|code|a[^>]*)>', '', t) if False else t for t in texts), encoding='utf-8')
    for f in list(files or []) + list(photos or []): shutil.copy(f, dd / pathlib.Path(f).name)

def deliver(name, key, texts, files, only, force, photos=None, d=None):
    if not texts: return False
    if not force and key in _sent(): print(f'пропуск (уже отправлено): {key}'); return False
    if d: archive(d, name, texts, files, photos)
    n = tg.send(name, texts, files, only=only, photos=photos, caption=f'<b>{esc(RESTAURANT)} · {esc(name)}</b>' + (f'\n{rus_date(d)} ({wd(d)})' if d else ''))
    if TG_TOKEN and n: _mark(key)      # в сухом прогоне и без получателей отправка не считается выполненной
    return True

def run_report(k, code, d, only, force, rolling=None):
    title, mod = REPORTS[code]
    try:
        texts, files = mod.build(k, d, rolling_hours=rolling) if (code == 'access' and rolling) else mod.build(k, d)
        if rolling and texts and 'Изменений доступов за период нет' in texts[0]: return
        deliver(title, f'{code}:{d}' + (f':r{dt.datetime.now(TZ):%Y%m%d%H}' if rolling else ''), texts, files, only, force or bool(rolling), d=None if rolling else d)
    except Exception as e:
        traceback.print_exc(); (LOGS / 'errors.log').open('a').write(f'{dt.datetime.now(TZ)} {code} {d}: {e}\n')
        tg.send(f'ошибка {code}', f'⚠️ Отчёт «{esc(title)}» за {rus_date(d)} не сформирован: {esc(str(e)[:200])}', only=only)

def run_dashboard(k, d, only, force):
    try:
        img = dashboard.day_dashboard(k, d)
        html = webdash.make(k, end=d, days=45)
        deliver('Дашборд дня', f'dashboard:{d}', [f'📊 Дашборд за {rus_date(d)} ({wd(d)}).\n🖱 Файл ниже — интерактивный: откройте в браузере, нажимайте на показатели и строки, чтобы раскрыть заказы, накладные и документы; раздел «Заказ (норма)» — остаток, средний расход и сколько заказать.'], [html], only, force, photos=[img], d=d)
    except Exception as e:
        traceback.print_exc(); (LOGS / 'errors.log').open('a').write(f'{dt.datetime.now(TZ)} dashboard {d}: {e}\n')

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('cmd'); ap.add_argument('arg', nargs='?')
    ap.add_argument('--date'); ap.add_argument('--to', help='номер получателя (иначе все)'); ap.add_argument('--force', action='store_true'); ap.add_argument('--hours', type=int)
    ap.add_argument('--restaurant', help='slug ресторана из restaurants.json'); ap.add_argument('--all', action='store_true', help='все рестораны по очереди')
    a = ap.parse_args(); only = [tg.norm_phone(a.to)] if a.to else None
    if a.all:      # каждый ресторан — отдельным процессом: свои настройки, логин iiko и отметки об отправке
        args = [x for x in sys.argv[1:] if x != '--all']; fails = 0
        for r in RESTAURANTS:
            if r.get('active') is False: continue
            print(f'\n######## {r.get("name")} ({r.get("slug")}, {r.get("system", "iiko")}) ########', flush=True)
            fails += subprocess.run([sys.executable, __file__] + args + ['--restaurant', r['slug']], cwd=str(ROOT)).returncode != 0
        sys.exit(1 if fails else 0)
    if RESTAURANTS and not SLUG: print('Укажите --restaurant <slug> или --all. Рестораны: ' + ', '.join(r['slug'] for r in RESTAURANTS)); sys.exit(2)
    if SLUG and not RESTAURANT_CFG: print(f'Ресторан {SLUG} не найден в {RESTAURANTS_FILE.name}'); sys.exit(2)
    if SYSTEM != 'iiko': print(f'{RESTAURANT}: {SYSTEM} подключается отдельным агентом в ресторане — пока пропускаю'); return
    if not IIKO_URL: print(f'{RESTAURANT}: ' + (ACCOUNTS_ERROR or f'нет строки «{SLUG}» в секрете IIKO_ACCOUNTS')); sys.exit(1)
    d = parse_date(a.date) if a.date else yesterday()
    if a.cmd == 'list': print('\n'.join(f'{c:10} {t}' for c, (t, _) in REPORTS.items()) + '\nweekly / monthly / reviews / morning'); return
    with Iiko() as k:
        if a.cmd == 'dashboard': run_dashboard(k, d, only, a.force)
        elif a.cmd == 'day':      # всё за день: дашборд + все отчёты (по запросу)
            run_dashboard(k, d, only, True)
            for c in MORNING: run_report(k, c, d, only, True)
        elif a.cmd == 'backfill':   # архив прошлых дней без отправки: python run.py backfill --from 2026-09-01 --to 2026-09-23
            a0, a1 = parse_date(a.date), parse_date(a.arg) if a.arg else yesterday()
            for i in range((a1 - a0).days + 1):
                day = a0 + dt.timedelta(days=i)
                try:
                    if (ARCHIVE / str(day) / f'dashboard_{day}.png').exists(): print('уже есть', day); continue
                    (ARCHIVE / str(day)).mkdir(parents=True, exist_ok=True); dashboard.day_dashboard(k, day, out_dir=ARCHIVE / str(day))
                    for c in MORNING:
                        if c in ('access',): continue
                        texts, files = REPORTS[c][1].build(k, day); archive(day, REPORTS[c][0], texts, files)
                    print('архив', day)
                except Exception as e: print('ошибка', day, e)
        elif a.cmd == 'morning':
            run_dashboard(k, d, only, a.force)
            for c in MORNING:
                run_report(k, c, d, only, a.force)
                if c == 'access': pass
        elif a.cmd == 'report': run_report(k, a.arg, d if a.date else (today() if a.arg == 'norm' else d), only, a.force)
        elif a.cmd == 'norm': run_report(k, 'norm', today(), only, a.force)
        elif a.cmd == 'access': run_report(k, 'access', today(), only, True, rolling=a.hours or 3)
        elif a.cmd == 'weekly':
            t0 = parse_date(a.date) if a.date else today(); end = t0 - dt.timedelta(days=t0.weekday() + 1); st = end - dt.timedelta(days=6)
            t, f = period.weekly(k, t0); img = dashboard.period_dashboard(k, st, end, 'Недельный дашборд', st - dt.timedelta(days=7), end - dt.timedelta(days=7))
            xl = week_xlsx.build(k, st, end); html = webdash.make(k, end=end, days=45)
            deliver('Недельный отчёт', f'weekly:{a.date or today()}', t, [xl, html], only, a.force, photos=[img])
        elif a.cmd == 'monthly':
            t0 = parse_date(a.date) if a.date else today(); end = t0 - dt.timedelta(days=1); st = end.replace(day=1); pe = st - dt.timedelta(days=1); ps = pe.replace(day=1)
            t, f = period.monthly(k, t0); img = dashboard.period_dashboard(k, st, end, 'Месячный дашборд', ps, ps.replace(day=min(end.day, pe.day)))
            deliver('Месячный отчёт', f'monthly:{a.date or today()}', t, f, only, a.force, photos=[img])
        elif a.cmd == 'reviews':
            t, f = reviews.build(); deliver('Негативные отзывы', f'reviews:{dt.datetime.now(TZ):%Y%m%d%H%M}', t, f, only, True)
        else: print('неизвестная команда'); sys.exit(2)

if __name__ == '__main__': main()
