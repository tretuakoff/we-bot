"""Сборка интерактивного HTML-дашборда из детальных данных по дням."""
import json, datetime as dt, pathlib
from .config import *
from .util import *
from . import daydata

TEMPLATE = pathlib.Path(__file__).parent / 'templates' / 'dashboard.html'

def build_html(days, out, stock=None, prices=None, reviews=None):
    data = json.dumps(days, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    meta = json.dumps({'gen': dt.datetime.now(TZ).strftime('%d.%m.%Y %H:%M'), 'stock': stock or [], 'prices': prices or {}, 'reviews': reviews or []}, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')
    html = TEMPLATE.read_text(encoding='utf-8').replace('__DATA__', data).replace('__META__', meta)
    out = pathlib.Path(out); out.write_text(html, encoding='utf-8'); return str(out)

def make(k, end=None, days=45, out=None):
    end = end or yesterday(); d0 = end - dt.timedelta(days=days - 1)
    ds = daydata.get_range(k, d0, end)
    ds = [x for x in ds if x['orders'] or x['purchases']]
    rv = []
    try:
        from .reports import reviews as rvm
        items, meta = rvm.fetch(days=days + 5, max_pages=20)
        rv = [dict(d=r['created'].strftime('%Y-%m-%d'), t=r['created'].strftime('%H:%M'), r=r['rating'], a=r['author'], x=r['text']) for r in items]
        rv.append(dict(meta=dict(rating=meta.get('branch_rating'), total=meta.get('branch_reviews_count'))))
    except Exception as e: print('webdash reviews', e)
    return build_html(ds, out or (OUTBOX / f'{SLUG or "we"}_dashboard_{end}.html'), daydata.stock_snapshot(k), daydata.last_prices(k, end), rv)
