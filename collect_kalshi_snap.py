"""Every few hours: snapshot all OPEN Kalshi player-prop and game markets (NFL + MLB) with bid/ask/last/volume. Free, keyless.
Builds a news -> price-move -> outcome timeline. Writes logs/kalshi_snap/YYYYMMDD/HHMM_<series>.json.gz"""
import json, gzip, os, time, datetime as dt, urllib.request, urllib.parse
API = 'https://api.elections.kalshi.com/trade-api/v2'
SER = ['KXNFLRECYDS', 'KXNFLRSHYDS', 'KXNFLPASSYDS', 'KXNFLREC', 'KXNFLANYTD', 'KXNFLPASSTDS', 'KXNFLGAME', 'KXNFLSPREAD', 'KXNFLTOTAL',
       'KXMLBKS', 'KXMLBHIT', 'KXMLBTB', 'KXMLBHR', 'KXMLBHRR', 'KXMLBOUTS', 'KXMLBGAME', 'KXMLBTOTAL', 'KXMLBSPREAD']
now = dt.datetime.utcnow(); d = f"logs/kalshi_snap/{now:%Y%m%d}"; os.makedirs(d, exist_ok=True)
for s in SER:
    out, cur = [], None
    for _ in range(10):
        q = dict(series_ticker=s, status='open', limit=1000); q.update(cursor=cur) if cur else None
        try:
            with urllib.request.urlopen(f"{API}/markets?{urllib.parse.urlencode(q)}", timeout=30) as r: j = json.loads(r.read())
        except Exception as e: print(s, e); break
        for m in j.get('markets', []):
            out.append([m['ticker'], m.get('yes_sub_title') or m.get('subtitle'), m.get('floor_strike'), m.get('yes_bid'), m.get('yes_ask'), m.get('last_price'), m.get('volume'), m.get('open_interest'), m.get('close_time')])
        cur = j.get('cursor')
        if not cur: break
        time.sleep(0.3)
    if out:
        with gzip.open(f"{d}/{now:%H%M}_{s}.json.gz", 'wt') as f: json.dump(dict(ts=now.isoformat(), series=s, cols=['ticker', 'sub', 'strike', 'bid', 'ask', 'last', 'vol', 'oi', 'close'], rows=out), f)
    print(s, len(out))
