from .base import *
from . import reviews

def _stars(n): return '⭐' * int(n)

def build(k, d):
    lines = [header('Отзывы 2ГИС', d)]
    if not TWOGIS_BRANCH_ID: return [lines[0] + '\n\nID филиала 2ГИС не задан.'], []
    days = max(35, (today() - d).days + 3)
    rv, meta = reviews.fetch(days=days, max_pages=15)
    day = [r for r in rv if r['created'].date() == d]
    rating, total = meta.get('branch_rating', '—'), meta.get('branch_reviews_count', '—')
    neg = [r for r in day if r['rating'] <= NEGATIVE_RATING_MAX]
    lines.append(f'Рейтинг: <b>{rating}</b> · всего отзывов: {total} · за день: <b>{len(day)}</b>' + (f' · негативных: <b>{len(neg)}</b> 🔴' if neg else ' · негативных нет ✅'))
    if day:
        avg = sum(r['rating'] for r in day) / len(day); lines.append(f'Средняя оценка за день: {avg:.1f}')
        for r in sorted(day, key=lambda x: x['rating']):
            lines.append(f'{"🔴 " if r["rating"] <= NEGATIVE_RATING_MAX else ""}{_stars(r["rating"])} <b>{r["rating"]}/5</b> · {r["created"].strftime("%H:%M")} · {esc(r["author"])}\n{esc(r["text"][:600]) or "(без текста)"}')
    else: lines.append(f'За {rus_date(d)} новых отзывов не было.')
    if not neg:
        older = [r for r in rv if r['rating'] <= NEGATIVE_RATING_MAX and r['created'].date() != d][:3]
        if older: lines.append('<b>Последние негативные отзывы (для контекста)</b>\n' + '\n\n'.join(f'{_stars(r["rating"])} {r["created"].strftime("%d.%m")} · {esc(r["author"])}: {esc(r["text"][:300]) or "(без текста)"}' for r in older))
    return ['\n\n'.join(lines)], []
