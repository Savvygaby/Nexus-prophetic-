"""Free closing lines: ESPN scoreboard per date (DraftKings open/close moneyline, spread, total + final scores).
Writes logs/espn_close/{league}/{yyyymmdd}.json; skips dates already saved more than 3 days ago."""
import json, os, time, datetime as dt, urllib.request
P = {'mlb': 'baseball/mlb', 'wnba': 'basketball/wnba', 'nba': 'basketball/nba'}
R = {'mlb': (dt.date(2026, 3, 20), dt.date.today()), 'wnba': (dt.date(2026, 5, 10), dt.date.today()), 'nba': (dt.date(2025, 10, 20), dt.date(2026, 6, 30))}
UA = {'User-Agent': 'Mozilla/5.0'}
n = 0
for lg, (a, b) in R.items():
    os.makedirs(f'logs/espn_close/{lg}', exist_ok=True); d = a
    while d <= b:
        fn = f'logs/espn_close/{lg}/{d:%Y%m%d}.json'
        if not (os.path.exists(fn) and (dt.date.today() - d).days > 3):
            u = f'https://site.api.espn.com/apis/site/v2/sports/{P[lg]}/scoreboard?dates={d:%Y%m%d}&limit=50'
            for i in range(3):
                try:
                    t = urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30).read().decode()
                    j = json.loads(t); out = []
                    for e in j.get('events', []):
                        c = e['competitions'][0]; tm = {x['homeAway']: x for x in c['competitors']}
                        out.append(dict(id=e['id'], date=e['date'], status=c['status']['type']['name'],
                                        home=tm['home']['team']['abbreviation'], away=tm['away']['team']['abbreviation'],
                                        home_name=tm['home']['team']['displayName'], away_name=tm['away']['team']['displayName'],
                                        hs=tm['home'].get('score'), as_=tm['away'].get('score'), odds=c.get('odds', [])))
                    json.dump(out, open(fn, 'w')); n += 1; break
                except Exception as ex: time.sleep(2)
            time.sleep(0.2)
        d += dt.timedelta(days=1)
print(n, 'dates')
