import html, datetime as dt, re
from .config import TZ

def today(): return dt.datetime.now(TZ).date()
def yesterday(): return today() - dt.timedelta(days=1)
def parse_date(s): return dt.date.fromisoformat(s)
def rus_date(d): return d.strftime('%d.%m.%Y')
WD = ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс']
def wd(d): return WD[d.weekday()]

def money(x, sign=False):
    try: x = float(x)
    except Exception: return '—'
    s = f'{abs(x):,.0f}'.replace(',', ' ')
    pre = ('+' if x > 0 else '−' if x < 0 else '') if sign else ('−' if x < 0 else '')
    return f'{pre}{s} ₸'
def num(x, d=0):
    try: return f'{float(x):,.{d}f}'.replace(',', ' ')
    except Exception: return '—'
def pct(x, d=1, sign=False):
    try: x = float(x)
    except Exception: return '—'
    return f'{x:+.{d}f}%' if sign else f'{x:.{d}f}%'
def esc(s): return html.escape(str(s if s is not None else ''), quote=False)
def short(s, n=40):
    s = str(s or ''); return s if len(s) <= n else s[:n - 1] + '…'

def pre(rows, headers=None, widths=None):
    """Таблица моноширинным текстом для Telegram (<pre>)."""
    rows = [[str(c) for c in r] for r in rows]
    if headers: rows = [list(map(str, headers))] + rows
    if not rows: return ''
    n = max(len(r) for r in rows)
    ws = widths or [min(max(len(r[i]) if i < len(r) else 0 for r in rows), 28) for i in range(n)]
    out = []
    for k, r in enumerate(rows):
        cells = []
        for i in range(n):
            c = r[i] if i < len(r) else ''
            c = c if len(c) <= ws[i] else c[:ws[i] - 1] + '…'
            cells.append(c.ljust(ws[i]) if i == 0 else c.rjust(ws[i]) if re.match(r'^[−+\d\s.,%₸-]+$', c) else c.ljust(ws[i]))
        out.append('  '.join(cells).rstrip())
        if headers and k == 0: out.append('─' * min(sum(ws) + 2 * (n - 1), 60))
    return '<pre>' + esc('\n'.join(out)) + '</pre>'

def split_msg(text, limit=3900):
    if len(text) <= limit: return [text]
    parts, cur = [], ''
    for block in text.split('\n\n'):
        if len(cur) + len(block) + 2 > limit and cur:
            parts.append(cur); cur = ''
        if len(block) > limit:
            # режем длинный блок по строкам, сохраняя <pre>
            inpre = block.startswith('<pre>')
            body = block[5:-6] if inpre else block
            chunk = ''
            for ln in body.split('\n'):
                if len(chunk) + len(ln) + 1 > limit - 12:
                    parts.append(('<pre>' + chunk + '</pre>') if inpre else chunk); chunk = ''
                chunk += ln + '\n'
            if chunk: cur = (('<pre>' + chunk + '</pre>') if inpre else chunk)
            continue
        cur += ('\n\n' if cur else '') + block
    if cur: parts.append(cur)
    return parts
