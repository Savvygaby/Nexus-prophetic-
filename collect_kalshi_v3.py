"""Kalshi settled player-prop history (keyless public API) with hourly price candles, for backtests.
Writes kalshi_hist/<SERIES>.jsonl.gz: one line per settled market: ticker, event, title, subtitle, strike, close/expiration time, result, candles [[ts, yes_bid_close, yes_ask_close, price_close, volume]]."""
import json, gzip, os, time, urllib.request, urllib.parse
API = 'https://api.elections.kalshi.com/trade-api/v2'
SERIES = os.environ.get('SERIES', 'KXMLBGAME,KXMLBTOTAL,KXMLBSPREAD,KXMLBF5,KXMLBF5TOTAL,KXMLBTEAMTOTAL,KXMLBRFI,KXNFLGAME,KXNFLSPREAD,KXNFLTOTAL,KXNFLTD,KXNFLFIRSTTD').split(',')
MAXM = int(os.environ.get('MAXM', 30000))
os.makedirs('kalshi_hist', exist_ok=True)
def get(path, **q):
    u = f"{API}{path}?{urllib.parse.urlencode(q)}"
    for i in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers={'Accept': 'application/json'}), timeout=30) as r: return json.loads(r.read())
        except Exception as e:
            time.sleep(1.5 * (i + 1)); err = str(e)
    print('FAIL', u[:140], err); return None

def px(d, k):
    """Kalshi renamed price fields to *_dollars (strings, 0-1). Return cents (0-100) from either form."""
    if not isinstance(d, dict): return None
    v = d.get(k)
    if v is None and d.get(k + '_dollars') is not None:
        try: return round(float(d[k + '_dollars']) * 100, 2)
        except Exception: return None
    if isinstance(v, dict): return px(v, 'close')
    return v
SAMPLE = {}
summary = {}
for s in SERIES:
    t0 = time.time(); n = 0; cursor = None
    with gzip.open(f'kalshi_hist/{s}.jsonl.gz', 'wt') as fo:
        while n < MAXM:
            q = dict(series_ticker=s, status='settled', limit=1000)
            if cursor: q['cursor'] = cursor
            page = get('/markets', **q)
            if not page or not page.get('markets'): break
            for m in page['markets']:
                if n >= MAXM: break
                ct = m.get('close_time') or m.get('expected_expiration_time'); ot = m.get('open_time')
                try:
                    import datetime as dt
                    e = int(dt.datetime.fromisoformat(ct.replace('Z', '+00:00')).timestamp()); st = max(int(dt.datetime.fromisoformat(ot.replace('Z', '+00:00')).timestamp()), e - 4 * 86400)
                except Exception: continue
                c = get(f"/series/{s}/markets/{m['ticker']}/candlesticks", start_ts=st, end_ts=e, period_interval=60)
                cs = []
                for k in (c or {}).get('candlesticks', []):
                    if s not in SAMPLE: SAMPLE[s] = k
                    cs.append([k.get('end_period_ts'), px(k.get('yes_bid') or {}, 'close'), px(k.get('yes_ask') or {}, 'close'), px(k.get('price') or {}, 'close'),
                               k.get('volume') if k.get('volume') is not None else k.get('volume_fp')])
                fo.write(json.dumps(dict(ticker=m['ticker'], event=m.get('event_ticker'), title=m.get('title'), sub=m.get('yes_sub_title') or m.get('subtitle'),
                                         strike=m.get('floor_strike') if m.get('floor_strike') is not None else m.get('cap_strike'), close=ct, exp=m.get('expected_expiration_time'),
                                         result=m.get('result'), volume=m.get('volume') if m.get('volume') is not None else m.get('volume_fp'), last=px(m, 'last_price'), candles=cs)) + '\n')
                n += 1; time.sleep(0.12)
            cursor = page.get('cursor')
            if not cursor: break
    summary[s] = dict(markets=n, sec=round(time.time() - t0)); print(s, summary[s], flush=True)
json.dump(summary, open(f'kalshi_hist/_summary_{SERIES[0]}.json', 'w'), indent=1); json.dump(SAMPLE, open(f'kalshi_hist/_sample_{SERIES[0]}.json', 'w'), indent=1)
# v2
