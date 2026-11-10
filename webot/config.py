"""Настройки бота сети WE: .env / секреты GitHub, список ресторанов restaurants.json и пороги ниже.
Ресторан выбирается переменной WE_RESTAURANT (slug из restaurants.json); run.py --all запускает все по очереди."""
import os, json, pathlib, datetime as dt

ROOT = pathlib.Path(__file__).resolve().parent.parent
STATE = pathlib.Path(os.environ['WE_STATE_DIR']) if os.environ.get('WE_STATE_DIR') else ROOT / 'state'
OUTBOX = ROOT / 'outbox'; LOGS = ROOT / 'logs'
DATA_DIR = pathlib.Path(os.environ['WE_DATA_DIR']) if os.environ.get('WE_DATA_DIR') else ROOT / 'archive' / 'data'
CLOUD = bool(os.environ.get('WE_CLOUD'))
for p in (STATE, OUTBOX, LOGS, DATA_DIR): p.mkdir(parents=True, exist_ok=True)

def _load_env():
    f = ROOT / '.env'
    if f.exists():
        for line in f.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1); os.environ.setdefault(k.strip(), v.strip())
_load_env()

NETWORK = os.environ.get('WE_NETWORK', 'WE')
RESTAURANTS_FILE = pathlib.Path(os.environ.get('WE_RESTAURANTS_FILE') or ROOT / 'restaurants.json')
RESTAURANTS = json.loads(RESTAURANTS_FILE.read_text(encoding='utf-8')) if RESTAURANTS_FILE.exists() else []
SLUG = os.environ.get('WE_RESTAURANT', '').strip()
_R = next((r for r in RESTAURANTS if r.get('slug') == SLUG), {})
RESTAURANT_CFG = _R
SYSTEM = _R.get('system', 'iiko')
if SLUG:   # у каждого ресторана своя папка данных
    DATA_DIR = DATA_DIR / SLUG; DATA_DIR.mkdir(parents=True, exist_ok=True)
def _parse_accounts(raw):
    """Секрет IIKO_ACCOUNTS: по строке на ресторан «имя адрес логин пароль» или JSON {"имя": {"url", "login", "password"}}.
    Ошибка в секрете не ломает бота: регистрация получателей работает, а ресторан сообщает, что не так."""
    raw = (raw or '').strip()
    if not raw: return {}, ''
    if raw.startswith('{'):
        try: return json.loads(raw), ''
        except Exception as e: return {}, f'секрет IIKO_ACCOUNTS не читается как JSON ({getattr(e, "msg", e)}, символ {getattr(e, "pos", "?")}). Проще записать по строке на ресторан: имя адрес логин пароль'
    out = {}
    for line in raw.splitlines():
        parts = line.strip().split(None, 3)
        if not parts or parts[0].startswith('#'): continue
        if len(parts) < 4: return out, f'строка «{parts[0]} …» в секрете IIKO_ACCOUNTS: нужно 4 части через пробел — имя, адрес, логин, пароль'
        url = parts[1] if parts[1].startswith('http') else 'https://' + parts[1]
        out[parts[0]] = {'url': url, 'login': parts[2], 'password': parts[3]}
    return out, ''
IIKO_ACCOUNTS_MAP, ACCOUNTS_ERROR = _parse_accounts(os.environ.get('IIKO_ACCOUNTS'))
_ACC = IIKO_ACCOUNTS_MAP.get(SLUG, {})
IIKO_URL = (_ACC.get('url') or os.environ.get('IIKO_URL', '')).rstrip('/')
IIKO_LOGIN = _ACC.get('login') or os.environ.get('IIKO_LOGIN', '')
IIKO_PASSWORD = _ACC.get('password') or os.environ.get('IIKO_PASSWORD', '')
TG_TOKEN = os.environ.get('TG_TOKEN', '').strip()
ALLOWED_PHONES = [p.strip() for p in os.environ.get('ALLOWED_PHONES', '').split(',') if p.strip()]
# дополнительный список получателей в репозитории: по номеру в строке, после # — комментарий
_PHONES_FILE = ROOT / 'allowed_phones.txt'
if _PHONES_FILE.exists():
    ALLOWED_PHONES += [l.split('#')[0].strip() for l in _PHONES_FILE.read_text(encoding='utf-8').splitlines() if l.split('#')[0].strip()]
ALLOWED_USERNAMES = [u.strip().lstrip('@').lower() for u in os.environ.get('ALLOWED_USERNAMES', '').split(',') if u.strip()]
TWOGIS_BRANCH_ID = str(_R.get('twogis_branch_id') or '').strip()
TWOGIS_KEY = '6e7e1929-4ea9-4a5d-8c05-d601860389bd'   # публичный ключ веб-виджета 2ГИС

TZ = dt.timezone(dt.timedelta(hours=5))    # Алматы (UTC+5)
RESTAURANT = _R.get('name') or NETWORK
_S = _R.get('settings') or {}   # особенности ресторана: VIP-столы, залы, вынос и т.п.

# ---- пороги ----
DEL_ORDER_ALERT = 100_000        # заказ с удалениями от этой суммы попадает в опасные операции
DISCOUNT_ALERT_PCT = 10          # скидка на заказ от этого % или суммы ниже
DISCOUNT_ALERT_SUM = 20_000
BANQUET_MIN_SUM = 150_000        # заказ считается банкетом/крупным от суммы по меню
BANQUET_MIN_GUESTS = 10
VIP_TABLES = [str(x) for x in _S.get('vip_tables', [])]   # столы, где должна пробиваться аренда VIP
VIP_DISH = _S.get('vip_dish', '')
TAKEAWAY_SECTION = _S.get('takeaway_section', '')   # секция выноса: там наценка за обслуживание не берётся
TAKEAWAY_MIN_GUESTS = 3            # вынос с таким числом гостей или чеком от суммы ниже похож на зал/банкет
TAKEAWAY_MIN_SUM = 30_000
HALL_SECTIONS = _S.get('hall_sections', [])   # залы, где должна начисляться наценка за обслуживание
# блюда, на которые наценка 10% в залах не начисляется по настройке iiko (нет категории блюда) — не считаем нарушением
FEE_EXEMPT = _S.get('fee_exempt', [])
PRICE_ALERT_PCT = 5              # изменение цены закупки от % попадает в отчёт
PRICE_RED_PCT = 10
MANUAL_ENTRY_ALERT = 100_000     # ручные проводки / выплаты от суммы
NEGATIVE_RATING_MAX = 4          # отзыв негативный при оценке не выше
# дни запаса для «нормы заказа» по группе (по умолчанию DEFAULT)
COVER_DAYS = {'МЯСО': 3, 'ОВОЩИ': 3, 'ЗЕЛЕНЬ': 2, 'МОЛОЧНАЯ ПРОДУКЦИЯ': 3, 'МОРЕПРОДУКТЫ': 3, 'ЯЙЦО': 5, 'МУЧНОЕ': 5,
              'ПЕРЕЦ': 7, 'Пиво': 7, 'Напитки': 7, 'Водка': 10}
COVER_DEFAULT = 7
NORM_GROUPS = ['МЯСО', 'ОВОЩИ', 'ЗЕЛЕНЬ', 'МОЛОЧНАЯ ПРОДУКЦИЯ', 'МОРЕПРОДУКТЫ', 'ЯЙЦО', 'МУЧНОЕ', 'МАСЛО', 'КРУПА',
               'СПЕЦИИ И СОУСЫ', 'Напитки', 'Пиво', 'Водка', 'ДЛЯ КОКТЕЙЛЕЙ', 'ПОЛУФАБРИКАТЫ']

NORM_MIN_DAILY_COST = 2000       # позиции с расходом дешевле этой суммы в день в норму заказа не попадают

# Рутинные ручные проводки бухгалтера — не считаются опасными, пока сумма меньше MANUAL_ENTRY_ALERT × 5
ROUTINE_PAIRS = [set(p) for p in _S.get('routine_pairs', [])]
