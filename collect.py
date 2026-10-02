"""Odds collector run by GitHub Actions (GitHub's servers can reach the sportsbooks; the analysis workspace cannot).
Saves raw JSON from The Odds API (NFL + MLB: game lines, player props incl. alternates, F5), plus keyless Kalshi and Bovada feeds."""
import json, os, time, urllib.request, urllib.parse, datetime as dt
KEY = os.environ.get('ODDS_API_KEY', '')
REQ = json.load(open('request.json')) if os.path.exists('request.json') else {}
OUT = 'odds'; os.makedirs(OUT, exist_ok=True)
LOG = {'started': dt.datetime.utcnow().isoformat() + 'Z', 'calls': [], 'errors': []}
def get(url, tag):
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=40)
        body = r.read(); LOG['calls'].append(dict(tag=tag, status=r.status, remaining=r.headers.get('x-requests-remaining'), used=r.headers.get('x-requests-used')))
        return json.loads(body)
    except Exception as e:
        LOG['errors'].append(dict(tag=tag, err=str(e)[:200])); return None
def save(name, obj):
    os.makedirs(os.path.dirname(f'{OUT}/{name}'), exist_ok=True); json.dump(obj, open(f'{OUT}/{name}', 'w'))
API = 'https://api.the-odds-api.com/v4/sports'
SPORTS = {
  'nfl': dict(key='americanfootball_nfl', days=REQ.get('nfl_days', 7), props=['player_pass_yds', 'player_pass_tds', 'player_pass_attempts', 'player_rush_yds', 'player_receptions',
           'player_reception_yds', 'player_anytime_td', 'player_pass_yds_alternate', 'player_rush_yds_alternate', 'player_reception_yds_alternate', 'player_receptions_alternate']),
  'mlb': dict(key='baseball_mlb', days=REQ.get('mlb_days', 4), props=['batter_hits', 'batter_total_bases', 'batter_home_runs', 'batter_rbis', 'batter_runs_scored', 'batter_hits_runs_rbis',
           'batter_singles', 'batter_doubles', 'batter_walks', 'batter_stolen_bases', 'pitcher_strikeouts', 'pitcher_outs', 'pitcher_hits_allowed', 'pitcher_earned_runs', 'pitcher_walks',
           'batter_hits_alternate', 'batter_total_bases_alternate', 'batter_home_runs_alternate', 'pitcher_strikeouts_alternate'], extra=['h2h_1st_5_innings', 'totals_1st_5_innings']),
}
now = dt.datetime.utcnow()
for sp, cfg in SPORTS.items():
    if sp not in REQ.get('sports', ['nfl', 'mlb']) or not KEY: continue
    ev = get(f"{API}/{cfg['key']}/events?apiKey={KEY}", f'{sp}_events')
    if not ev: continue
    save(f'{sp}/events.json', ev)
    lim = now + dt.timedelta(days=cfg['days'])
    for e in ev:
        t = dt.datetime.strptime(e['commence_time'], '%Y-%m-%dT%H:%M:%SZ')
        if t < now or t > lim: continue
        eid = e['id']
        g = get(f"{API}/{cfg['key']}/events/{eid}/odds?apiKey={KEY}&regions=us&markets=h2h,spreads,totals&oddsFormat=american", f'{sp}_game_{eid}')
        if g: save(f'{sp}/game_{eid}.json', g)
        if cfg.get('extra'):
            x = get(f"{API}/{cfg['key']}/events/{eid}/odds?apiKey={KEY}&regions=us&markets={','.join(cfg['extra'])}&oddsFormat=american", f'{sp}_f5_{eid}')
            if x: save(f'{sp}/f5_{eid}.json', x)
        for i in range(0, len(cfg['props']), 6):
            mk = ','.join(cfg['props'][i:i + 6])
            p = get(f"{API}/{cfg['key']}/events/{eid}/odds?apiKey={KEY}&regions=us&markets={mk}&oddsFormat=decimal", f'{sp}_props_{eid}_{i}')
            if p: save(f'{sp}/props_{eid}_{i}.json', p)
# keyless: Kalshi game markets, Bovada coupons
ser_list = get('https://api.elections.kalshi.com/trade-api/v2/series?category=Sports&limit=1000', 'kalshi_series')
if ser_list: save('kalshi/series.json', ser_list)
WANT = ['KXNFLGAME', 'KXMLBGAME']
for s_ in (ser_list or {}).get('series', []):
    t = s_.get('ticker', '')
    if (t.startswith('KXNFL') or t.startswith('KXMLB')) and t not in WANT: WANT.append(t)
for ser in WANT[:60]:
    k = get(f'https://api.elections.kalshi.com/trade-api/v2/events?series_ticker={ser}&with_nested_markets=true&status=open&limit=200', f'kalshi_{ser}')
    if k: save(f'kalshi/{ser}.json', k)
for lg, path in (('nfl', 'football/nfl'), ('mlb', 'baseball/mlb')):
    b = get(f'https://www.bovada.lv/services/sports/event/coupon/events/A/description/{path}?marketFilterId=def&preMatchOnly=true&lang=en', f'bovada_{lg}')
    if b: save(f'bovada/{lg}.json', b)
LOG['finished'] = dt.datetime.utcnow().isoformat() + 'Z'
save('manifest.json', LOG)
print(json.dumps({k: (v if k != 'calls' else len(v)) for k, v in LOG.items()}, indent=1)[:3000])
