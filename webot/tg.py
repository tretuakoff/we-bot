"""Отправка в Telegram. Без TG_TOKEN работает сухой прогон: сообщения печатаются и сохраняются в outbox/."""
import json, time, datetime as dt, re, pathlib, requests
from .config import *
from .util import split_msg

RECIP = STATE / 'recipients.json'

def norm_phone(p):
    if str(p).startswith('tg_'): return str(p)
    d = re.sub(r'\D', '', str(p))
    if len(d) == 11 and d.startswith('8'): d = '7' + d[1:]
    if len(d) == 10: d = '7' + d
    return d

def recipients():
    """{'77020552222': chat_id, ...} — только подтверждённые через /start."""
    if RECIP.exists(): return json.loads(RECIP.read_text())
    return {}

def save_recipient(phone, chat_id):
    r = recipients(); r[norm_phone(phone)] = chat_id; RECIP.write_text(json.dumps(r, ensure_ascii=False, indent=1))

def api(method, **kw):
    return requests.post(f'https://api.telegram.org/bot{TG_TOKEN}/{method}', timeout=60, **kw)

def _dry(name, text, files):
    stamp = dt.datetime.now(TZ).strftime('%Y%m%d_%H%M%S')
    f = OUTBOX / f'{stamp}_{re.sub(r"[^\w-]", "_", name)}.txt'
    f.write_text(text if isinstance(text, str) else '\n\n'.join(text), encoding='utf-8')
    for fp in files or []:
        import shutil; shutil.copy(fp, OUTBOX / f'{stamp}_{pathlib.Path(fp).name}')

def send(name, texts, files=None, only=None, photos=None, caption=None):
    """texts: str или list[str] (HTML). Возвращает число доставленных получателей (или 0 в сухом прогоне)."""
    texts = [texts] if isinstance(texts, str) else list(texts)
    parts = [p for t in texts for p in split_msg(t)]
    if not TG_TOKEN:
        print(f'\n===== [DRY] {name} =====')
        for p in parts: print(re.sub(r'</?(b|i|pre|code|a[^>]*)>', '', p)); print()
        for f in files or []: print(f'[файл] {f}')
        for f in photos or []: print(f'[картинка] {f}')
        _dry(name, parts, list(files or []) + list(photos or [])); return 0
    targets = recipients(); ok = 0
    if only: targets = {k: v for k, v in targets.items() if k in only}
    if not targets: print('нет подтверждённых получателей: пусть напишут /start боту и поделятся номером'); return 0
    for phone, chat in targets.items():
        try:
            for ph in photos or []:
                with open(ph, 'rb') as fh:
                    r = api('sendPhoto', data={'chat_id': chat, 'caption': (caption or name)[:1000], 'parse_mode': 'HTML'}, files={'photo': fh})
                if not r.ok: print('tg photo error', phone, r.text[:200])
            for p in parts:
                r = api('sendMessage', data={'chat_id': chat, 'text': p, 'parse_mode': 'HTML', 'disable_web_page_preview': 'true'})
                if r.status_code == 429: time.sleep(int(r.json().get('parameters', {}).get('retry_after', 3))); r = api('sendMessage', data={'chat_id': chat, 'text': p, 'parse_mode': 'HTML'})
                if not r.ok: print('tg error', phone, r.text[:200])
                time.sleep(0.4)
            for f in files or []:
                with open(f, 'rb') as fh: api('sendDocument', data={'chat_id': chat}, files={'document': fh})
            ok += 1
        except Exception as e: print('tg fail', phone, e)
    return ok
