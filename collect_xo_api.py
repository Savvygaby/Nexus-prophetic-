"""Pull XO Sports' public pick history from their open WordPress API (the same feed their Performance Hub page uses).
Writes logs/xo_api/{league}/{date}_{endpoint}.json; skips files already saved (except the last 3 days, which are refreshed)."""
import json, os, time, datetime as dt, urllib.request, urllib.parse
B = 'https://xosports.ai/wp-json/xo-sports/v1/'
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36', 'Accept': 'application/json'}
def get(ep, **q):
    u = B + ep + '?' + urllib.parse.urlencode(q)
    for i in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30) as r: return r.status, r.read().decode()
        except Exception as e: err = str(e); time.sleep(2)
    return 0, json.dumps(dict(error=err))
today = dt.date.today()
SEASONS = {'mlb': (dt.date(2026, 3, 20), today), 'wnba': (dt.date(2026, 5, 10), today), 'nba': (dt.date(2025, 10, 20), dt.date(2026, 6, 30)), 'nfl': (dt.date(2026, 9, 5), today), 'epl': (dt.date(2026, 8, 10), today)}
log = []
for lg, (a, b) in SEASONS.items():
    os.makedirs(f'logs/xo_api/{lg}', exist_ok=True)
    # one-shot range performance (90-day windows)
    s = a
    while s <= b:
        e = min(s + dt.timedelta(days=89), b)
        for conf in (0, 50):
            st, t = get('daily-performance', league=lg, start=s.isoformat(), end=e.isoformat(), confidence=conf)
            open(f'logs/xo_api/{lg}/perf_{s}_{e}_c{conf}.json', 'w').write(t)
        s = e + dt.timedelta(days=1)
    d = a
    while d <= b:
        for ep in ('top-picks', 'top-matches'):
            fn = f'logs/xo_api/{lg}/{d}_{ep}.json'
            if os.path.exists(fn) and (today - d).days > 3: continue
            st, t = get(ep, date=d.isoformat(), league=lg)
            open(fn, 'w').write(t); log.append((lg, str(d), ep, st, len(t))); time.sleep(0.25)
        d += dt.timedelta(days=1)
for ep, q in (('data-settings', {}), ('top-matches-carousel', {'league': 'all'})):
    open(f'logs/xo_api/{ep}.json', 'w').write(get(ep, **q)[1])
json.dump(log, open('logs/xo_api/last_run.json', 'w'))
print(len(log), 'calls')
