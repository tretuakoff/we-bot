#!/usr/bin/env python3
"""Telegram-бот сети WE: подтверждение номеров получателей и отчёты по команде.
Запуск: python poll.py (работает постоянно) или python poll.py --once (облако: обработать накопившееся и выйти)."""
import time, json, datetime as dt, traceback, subprocess, sys, threading
from webot.config import *
from webot import tg
from webot.util import *

NAMES = 'cash flow expenses purchases prices norm deletions cashiers banquets dangerous journal reviews access'.split()
NAMES_RU = {'cash': 'кассовый день', 'flow': 'приход/расход', 'expenses': 'прочие расходы', 'purchases': 'закупки', 'prices': 'изменение цен', 'norm': 'норма заказа', 'deletions': 'удаления',
            'cashiers': 'операции кассиров', 'banquets': 'банкеты', 'dangerous': 'опасные операции', 'journal': 'журнал событий: касса и заказы', 'reviews': 'отзывы 2ГИС', 'access': 'доступы'}


def rest_list():
    return '\n'.join(f'<code>{esc(r["slug"])}</code> — {esc(r.get("name", r["slug"]))}' + ('' if r.get('system', 'iiko') == 'iiko' else f' ({esc(r["system"])}, скоро)')
                     for r in RESTAURANTS if r.get('active') is not False)


HELP = (f'<b>Бот сети {esc(NETWORK)}</b> — отчёты по ресторанам\n\n'
        'Каждое утро в 09:00 приходит пакет за вчера по каждому ресторану.\n\n'
        '/reports — список отчётов и ресторанов\n'
        '/report &lt;отчёт&gt; [ГГГГ-ММ-ДД] [ресторан] — отчёт сейчас, например <code>/report deletions</code>\n'
        '/dashboard [дата] [ресторан] — дашборд дня · /day [дата] [ресторан] — дашборд и все отчёты за день\n'
        '/status — проверить, что бот работает\n\n'
        'Без ресторана отчёт приходит по всем ресторанам сети.')


def reply(chat, text, markup=None):
    data = {'chat_id': chat, 'text': text, 'parse_mode': 'HTML'}
    if markup: data['reply_markup'] = json.dumps(markup)
    tg.api('sendMessage', data=data)


def phone_of(chat):
    for p, c in tg.recipients().items():
        if c == chat: return p


def _spawn(args):
    kw = dict(cwd=str(ROOT), stdout=open(LOGS / 'poll_run.log', 'a'), stderr=subprocess.STDOUT)
    if '--once' in sys.argv: return subprocess.run(args, **kw)   # облако: дождаться отправки
    return subprocess.Popen(args, **kw)


def _split_args(parts):
    """[дата] [ресторан] в любом порядке -> (['--date', ...], ['--restaurant', slug] или ['--all'])."""
    date, rest = [], ['--all']
    for p in parts:
        if len(p) == 10 and p[4] == '-' and p[7] == '-': date = ['--date', p]; continue
        hit = next((r for r in RESTAURANTS if p.lower() in (r['slug'].lower(), r.get('name', '').lower()) or p.lower() in r.get('name', '').lower()), None)
        if hit: rest = ['--restaurant', hit['slug']]
    return date, rest


def handle(u):
    m = u.get('message') or {}
    if not m: return
    chat = m['chat']['id']; text = (m.get('text') or '').strip(); frm = m.get('from', {})
    if 'contact' in m:
        c = m['contact']; ph = tg.norm_phone(c.get('phone_number', ''))
        if c.get('user_id') != frm.get('id'): return reply(chat, 'Поделитесь <b>своим</b> номером кнопкой ниже.')
        if ph in [tg.norm_phone(x) for x in ALLOWED_PHONES]:
            tg.save_recipient(ph, chat)
            reply(chat, f'✅ Готово. Номер подтверждён, отчёты сети {esc(NETWORK)} будут приходить сюда.\n\n' + HELP, {'remove_keyboard': True})
        else: reply(chat, 'Этот номер не в списке получателей. Обратитесь к владельцу.', {'remove_keyboard': True})
        return
    uname = (frm.get('username') or '').lower()
    if text.startswith('/start') and uname and uname in ALLOWED_USERNAMES:
        tg.save_recipient('tg_' + uname, chat)
        return reply(chat, f'✅ Готово. Вы подключены, отчёты сети {esc(NETWORK)} будут приходить сюда.\n\n' + HELP, {'remove_keyboard': True})
    if text.startswith('/start'):
        return reply(chat, f'Здравствуйте! Чтобы получать отчёты сети {esc(NETWORK)}, подтвердите номер телефона.',
                     {'keyboard': [[{'text': '📱 Поделиться номером', 'request_contact': True}]], 'resize_keyboard': True, 'one_time_keyboard': True})
    ph = phone_of(chat)
    if not ph: return reply(chat, 'Сначала нажмите /start и подтвердите номер.')
    if text.startswith('/help') or text.startswith('/reports'):
        return reply(chat, HELP + '\n\n<b>Отчёты:</b>\n' + '\n'.join(f'<code>{n}</code> — {NAMES_RU[n]}' for n in NAMES) + '\n\n<b>Рестораны:</b>\n' + rest_list())
    if text.startswith('/status'):
        return reply(chat, f'Бот работает. Получателей подтверждено: {len(tg.recipients())}. Сейчас {dt.datetime.now(TZ):%d.%m.%Y %H:%M} (Алматы).')
    if text.startswith(('/dashboard', '/day', '/report')):
        parts = text.split(); cmd = parts[0][1:].split('@')[0]
        args = [sys.executable, 'run.py']
        if cmd == 'report':
            if len(parts) < 2 or parts[1] not in NAMES: return reply(chat, 'Укажите отчёт: ' + ', '.join(NAMES))
            date, rest = _split_args(parts[2:]); args += ['report', parts[1]] + date + rest
        else:
            date, rest = _split_args(parts[1:]); args += [cmd] + date + rest
        reply(chat, '⏳ Формирую…')
        _spawn(args + ['--to', ph, '--force'])
        return
    reply(chat, 'Не понял команду. /help')


def once():
    if not TG_TOKEN: print('Нет TG_TOKEN'); return 0
    off_f = tg.STATE / 'offset.json'; offset = json.loads(off_f.read_text()).get('offset') if off_f.exists() else None; n = 0
    while True:
        r = tg.api('getUpdates', data={'timeout': 0, 'limit': 50, 'offset': offset or 0, 'allowed_updates': json.dumps(['message'])}).json()
        ups = r.get('result', [])
        if not ups: break
        for u in ups:
            offset = u['update_id'] + 1; n += 1
            try: handle(u)
            except Exception: traceback.print_exc()
            off_f.write_text(json.dumps({'offset': offset}))
    print('обработано обновлений:', n); return n


def main():
    if '--once' in sys.argv: once(); return
    if not TG_TOKEN: print('Нет TG_TOKEN в .env'); sys.exit(1)
    offset = None; print('бот запущен')
    while True:
        try:
            r = tg.api('getUpdates', data={'timeout': 50, 'offset': offset or 0, 'allowed_updates': json.dumps(['message'])}).json()
            for u in r.get('result', []):
                offset = u['update_id'] + 1
                threading.Thread(target=handle, args=(u,)).start()
        except Exception as e: print('poll error', e); time.sleep(5)


if __name__ == '__main__': main()
