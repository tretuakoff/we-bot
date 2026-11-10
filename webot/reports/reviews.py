import json, datetime as dt, requests
from ..config import *
from ..util import *

SEEN = STATE / f'seen_reviews_{SLUG or "default"}.json'
API = 'https://public-api.reviews.2gis.com/2.0/branches/{id}/reviews'

def fetch(days=7, max_pages=10):
    params = dict(limit=50, is_advertiser='false', fields='meta.branch_rating,meta.branch_reviews_count,meta.total_count', rated='true', sort_by='date_created', key=TWOGIS_KEY, locale='ru_KZ')
    url = API.format(id=TWOGIS_BRANCH_ID); out = []; meta = {}
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    for _ in range(max_pages):
        r = requests.get(url, params=params, headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://2gis.kz/'}, timeout=30); r.raise_for_status()
        data = r.json(); meta = data.get('meta', {}); rv = data.get('reviews', [])
        if not rv: break
        stop = False
        for x in rv:
            created = dt.datetime.fromisoformat(x['date_created'])
            if created < since: stop = True; continue
            out.append(dict(id=str(x['id']), rating=x['rating'], text=(x.get('text') or '').strip(), created=created.astimezone(TZ), author=(x.get('user') or {}).get('name') or 'Аноним', url=x.get('url')))
        nxt = meta.get('next_link')
        if stop or not nxt: break
        url, params = nxt, {}
    return out, meta

def build(k=None, d=None, only_new=True, days=7):
    if not TWOGIS_BRANCH_ID: return [], []
    rv, meta = fetch(days)
    seen = set(json.loads(SEEN.read_text())) if SEEN.exists() else set()
    neg = [r for r in rv if r['rating'] <= NEGATIVE_RATING_MAX]
    new = [r for r in neg if r['id'] not in seen] if only_new else neg
    if TG_TOKEN: SEEN.write_text(json.dumps(sorted(seen | {r['id'] for r in rv})))   # в сухом прогоне не помечаем отзывы прочитанными
    if not new: return [], []
    lines = [f'<b>{esc(RESTAURANT)} · Негативные отзывы 2ГИС</b>\nРейтинг: {meta.get("branch_rating", "—")} · всего отзывов: {meta.get("branch_reviews_count", "—")}']
    for r in sorted(new, key=lambda x: x['created'], reverse=True):
        lines.append(f'{"⭐" * r["rating"]} <b>{r["rating"]}/5</b> · {r["created"].strftime("%d.%m.%Y %H:%M")} · {esc(r["author"])}\n{esc(r["text"][:600]) or "(без текста)"}')
    return ['\n\n'.join(lines)], []
