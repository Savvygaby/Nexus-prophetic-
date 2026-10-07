"""Kickoff-time capture: for every NFL/MLB event starting in the next 20-75 minutes (after inactives / lineups), save prices for the
derivative markets the engine prices (FanDuel + all US books). One capture per event. These are our closing prices for CLV.
Cost ~1 credit per market returned per event (~10/NFL game, ~8/MLB game). The /events list call is free."""
import json, os, datetime as dt, urllib.request
KEY = os.environ.get('ODDSAPI', '').strip(); API = 'https://api.the-odds-api.com/v4/sports'
NOW = dt.datetime.now(dt.timezone.utc)
MK = {'americanfootball_nfl': ['player_receptions', 'player_reception_yds', 'player_rush_yds', 'player_pass_yds', 'player_reception_longest',
                               'player_reception_longest_alternate', 'player_rush_longest', 'player_pass_longest_completion', 'player_rush_reception_yds',
                               'player_pass_rush_yds', 'player_receptions_alternate', 'player_reception_yds_alternate', 'player_anytime_td'],
      'baseball_mlb': ['pitcher_strikeouts', 'pitcher_outs', 'pitcher_strikeouts_alternate', 'batter_hits', 'batter_total_bases', 'batter_home_runs',
                       'batter_total_bases_alternate', 'batter_hits_alternate']}
def get(u):
    try:
        with urllib.request.urlopen(u, timeout=30) as r: return json.loads(r.read()), r.headers.get('x-requests-remaining')
    except Exception as e: print('ERR', str(e)[:150]); return None, None
log = []
for sp, mks in MK.items():
    ev, _ = get(f'{API}/{sp}/events?apiKey={KEY}')
    for e in ev or []:
        t = dt.datetime.fromisoformat(e['commence_time'].replace('Z', '+00:00')); mins = (t - NOW).total_seconds() / 60
        fn = f"odds/close/{sp.split('_')[1]}/{e['id']}.json"
        if not (20 <= mins <= 75) or os.path.exists(fn): continue
        o, rem = get(f"{API}/{sp}/events/{e['id']}/odds?apiKey={KEY}&regions=us&markets={','.join(mks)}&oddsFormat=american&includeLinks=true&includeSids=true")
        if o:
            o['captured_at'] = NOW.isoformat(); o['minutes_before'] = round(mins)
            os.makedirs(os.path.dirname(fn), exist_ok=True); json.dump(o, open(fn, 'w'))
            log.append(dict(event=e['id'], game=f"{e['away_team']} @ {e['home_team']}", mins=round(mins), remaining=rem))
print(json.dumps(log, indent=1))
