"""Клиент iikoServer: OLAP, документы, события, смены, остатки."""
import hashlib, json, time, datetime as dt, xml.etree.ElementTree as ET
import requests, pandas as pd
from .config import *

class Iiko:
    def __init__(self):
        self.base = IIKO_URL; self.key = None; self._cache = {}

    def __enter__(self):
        pw = hashlib.sha1(IIKO_PASSWORD.encode()).hexdigest()
        for a in range(3):
            r = requests.get(f'{self.base}/resto/api/auth', params={'login': IIKO_LOGIN, 'pass': pw}, timeout=60)
            if r.status_code == 200: self.key = r.text.strip(); return self
            time.sleep(2)
        raise RuntimeError(f'iiko auth {r.status_code}: {r.text[:200]}')

    def __exit__(self, *a):
        try: requests.get(f'{self.base}/resto/api/logout', params={'key': self.key}, timeout=20)
        except Exception: pass

    def get(self, path, timeout=600, **params):
        params['key'] = self.key
        for a in range(3):
            try: r = requests.get(self.base + path, params=params, timeout=timeout)
            except (requests.ConnectionError, requests.exceptions.ChunkedEncodingError, requests.Timeout):
                if a == 2: raise
                time.sleep(5); continue
            if r.status_code == 200: return r.text
            if r.status_code in (500, 502, 503, 504): time.sleep(3); continue
            raise RuntimeError(f'iiko {path} → {r.status_code}: {r.text[:200]}')
        raise RuntimeError(f'iiko {path} → {r.status_code}')

    # ---------- справочники ----------
    def employees(self):
        if 'emp' not in self._cache:
            root = ET.fromstring(self.get('/resto/api/employees'))
            self._cache['emp'] = {e.findtext('id'): e.findtext('name') for e in root.iter('employee')}
        return self._cache['emp']
    def suppliers(self):
        if 'sup' not in self._cache:
            root = ET.fromstring(self.get('/resto/api/suppliers'))
            self._cache['sup'] = {e.findtext('id'): e.findtext('name') for e in root.iter('employee')}
        return self._cache['sup']
    def stores(self):
        if 'st' not in self._cache:
            root = ET.fromstring(self.get('/resto/api/corporation/stores'))
            self._cache['st'] = {e.findtext('id'): e.findtext('name') for e in root.iter('corporateItemDto')}
        return self._cache['st']
    def products(self):
        if 'pr' not in self._cache:
            data = json.loads(self.get('/resto/api/v2/entities/products/list', includeDeleted='true'))
            grp = {g['id']: g['name'] for g in json.loads(self.get('/resto/api/v2/entities/products/group/list', includeDeleted='true'))}
            units = {u['id']: u['name'] for u in json.loads(self.get('/resto/api/v2/entities/list', rootType='MeasureUnit', includeDeleted='true'))}
            df = pd.DataFrame(data)[['id', 'name', 'parent', 'type', 'mainUnit', 'defaultSalePrice', 'deleted']]
            df['group'] = df.parent.map(grp); df['unit'] = df.mainUnit.map(units)
            self._cache['pr'] = df.rename(columns={'id': 'product', 'name': 'pname'})
        return self._cache['pr']
    def accounts(self):
        if 'acc' not in self._cache:
            self._cache['acc'] = {a['id']: a['name'] for a in json.loads(self.get('/resto/api/v2/entities/list', rootType='Account', includeDeleted='true'))}
        return self._cache['acc']

    # ---------- OLAP ----------
    def olap(self, report, rows, aggs, d0, d1, date_field=None, extra=None):
        """d0 включительно, d1 не включительно (date)."""
        date_field = date_field or ('OpenDate.Typed' if report == 'SALES' else 'DateTime.Typed')
        f = {date_field: {'filterType': 'DateRange', 'periodType': 'CUSTOM', 'from': str(d0), 'to': str(d1), 'includeLow': True, 'includeHigh': False}}
        if extra: f.update(extra)
        body = {'reportType': report, 'buildSummary': 'false', 'groupByRowFields': rows, 'aggregateFields': aggs, 'filters': f}
        for a in range(3):
            r = requests.post(f'{self.base}/resto/api/v2/reports/olap', params={'key': self.key}, json=body, timeout=900)
            if r.status_code == 200: break
            if r.status_code >= 500: time.sleep(3); continue
            raise RuntimeError(f'OLAP {report}: {r.status_code} {r.text[:300]}')
        df = pd.DataFrame(r.json().get('data', []))
        for c in df.columns:
            if c in aggs: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        return df

    # ---------- документы ----------
    def incoming(self, d0, d1):
        """Приходные накладные [d0, d1] включительно → строки."""
        root = ET.fromstring(self.get('/resto/api/documents/export/incomingInvoice', **{'from': str(d0), 'to': str(d1)}))
        sup, st, pr = self.suppliers(), self.stores(), self.products().set_index('product')
        def T(e, t):
            x = e.find(t); return x.text if x is not None else None
        rows = []
        for d in root.iter('document'):
            for it in d.iter('item'):
                pid = T(it, 'product')
                rows.append(dict(docid=T(d, 'id'), doc=T(d, 'documentNumber'), date=(T(d, 'dateIncoming') or T(d, 'incomingDate')), status=T(d, 'status'),
                                 supplier=sup.get(T(d, 'supplier'), T(d, 'supplier')), store=st.get(T(it, 'store'), T(it, 'store')),
                                 product=pid, pname=pr['pname'].get(pid, pid), group=pr['group'].get(pid) if pid in pr.index else None,
                                 unit=pr['unit'].get(pid) if pid in pr.index else None,
                                 amount=float(T(it, 'amount') or 0), price=float(T(it, 'price') or 0), sum=float(T(it, 'sum') or 0)))
        df = pd.DataFrame(rows)
        if len(df): df['date'] = pd.to_datetime(df.date.str[:10])
        return df

    def writeoffs(self, d0, d1):
        js = json.loads(self.get('/resto/api/v2/documents/writeoff', dateFrom=str(d0), dateTo=str(d1)))
        st, pr, acc = self.stores(), self.products().set_index('product'), self.accounts()
        rows = []
        for d in js.get('response', []):
            for it in d['items']:
                rows.append(dict(doc=d['documentNumber'], date=d['dateIncoming'], status=d['status'], store=st.get(d['storeId']), account=acc.get(d['accountId'], d['accountId']),
                                 pname=pr['pname'].get(it['productId'], it['productId']), amount=it['amount'], cost=it['cost'], comment=d.get('comment')))
        return pd.DataFrame(rows)

    def cashshifts(self, d0, d1):
        js = json.loads(self.get('/resto/api/v2/cashshifts/list', openDateFrom=str(d0), openDateTo=str(d1), status='ANY'))
        emp = self.employees(); df = pd.DataFrame(js)
        if len(df):
            for c in ('openDate', 'closeDate', 'acceptDate'): df[c] = pd.to_datetime(df[c], errors='coerce', format='ISO8601')
            df['cashier'] = df.managerId.map(emp)
        return df

    def balance(self, ts=None):
        ts = ts or dt.datetime.now(TZ).strftime('%Y-%m-%dT%H:%M:%S')
        js = json.loads(self.get('/resto/api/v2/reports/balance/stores', timestamp=ts))
        st, pr = self.stores(), self.products().set_index('product')
        df = pd.DataFrame(js); df['store'] = df.store.map(st); df['pname'] = df['product'].map(pr['pname']); df['group'] = df['product'].map(pr['group']); df['unit'] = df['product'].map(pr['unit'])
        return df

    # ---------- журнал событий ----------
    SKIP = {'addItemToOrder', 'frontLogout', 'dishServed', 'pinAuthorization', 'serviceChequeForDishesPrinted', 'cardAuthorization',
            'stopListItemAdded', 'stopListItemRemoved', 'orderOpened', 'fiscalChequePrinted', 'attendanceEntryMerged', 'backLogin', 'backLogout'}
    def events(self, t0, t1, skip=True):
        """t0/t1 — datetime (с tz)."""
        f = lambda x: x.strftime('%Y-%m-%dT%H:%M:%S.000')
        try: xml = self.get('/resto/api/events', from_time=f(t0), to_time=f(t1), timeout=900)
        except RuntimeError as e:
            if '403' in str(e): return pd.DataFrame()
            raise
        emp = self.employees(); rows = []
        for e in ET.fromstring(xml).iter('event'):
            ty = e.findtext('type')
            if skip and ty in self.SKIP: continue
            rec = {'id': e.findtext('id'), 'date': e.findtext('date'), 'type': ty}
            for a in e.findall('attribute'): rec[a.findtext('name')] = a.findtext('value')
            rows.append(rec)
        cols = ['id', 'date', 'type', 'user', 'documentType', 'documentNumber', 'sum', 'account', 'corrAccount', 'tableNum', 'dishes', 'success', 'permissionName',
                'permissionCode', 'permissionState', 'userName', 'userId', 'comment', 'name', 'orderSumAfterDiscount', 'priceOld', 'price', 'productId', 'waiter', 'orderNum']
        df = pd.DataFrame(rows)
        for c in cols:
            if c not in df: df[c] = None
        if len(df):
            df['dt'] = pd.to_datetime(df.date.str[:19], errors='coerce'); df['who'] = df['user'].map(emp).fillna(df['user'])
        else: df['dt'] = pd.NaT; df['who'] = None
        return df
