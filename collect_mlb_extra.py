"""MLB edge data for testing props/game picks (all free, public):
 - Statcast pitch-by-pitch (Baseball Savant via pybaseball): pitch type/velo/movement, swing/whiff, exit velo, xwOBA -> pitch-mix matchups, Stuff-style grades
 - MLB Stats API box scores: home-plate umpire + full crew, weather (temp, sky), wind (speed + direction vs field), venue, starters, final score, linescore
Writes into OUT (default mlbx/): statcast/<YYYY-MM>.parquet, games/<season>.csv (one row per game).
MODE=backfill  -> SEASONS (default 2024,2025,2026) in full
MODE=daily     -> current + previous month Statcast, last DAYS days of games (merged into the season csv)."""
import os, json, time, datetime as dt, urllib.request, pandas as pd
OUT = os.environ.get('OUT', 'mlbx'); MODE = os.environ.get('MODE', 'backfill')
SEASONS = [int(s) for s in os.environ.get('SEASONS', '2024,2025,2026').split(',')]; DAYS = int(os.environ.get('DAYS', 4))
os.makedirs(f'{OUT}/statcast', exist_ok=True); os.makedirs(f'{OUT}/games', exist_ok=True)
SC_COLS = ['game_date', 'game_pk', 'game_type', 'home_team', 'away_team', 'inning', 'inning_topbot', 'at_bat_number', 'pitch_number', 'pitcher', 'batter',
           'player_name', 'stand', 'p_throws', 'pitch_type', 'release_speed', 'release_spin_rate', 'release_extension', 'pfx_x', 'pfx_z', 'plate_x', 'plate_z', 'zone',
           'balls', 'strikes', 'outs_when_up', 'on_1b', 'on_2b', 'on_3b', 'description', 'type', 'events', 'bb_type', 'launch_speed', 'launch_angle', 'hit_distance_sc',
           'estimated_ba_using_speedangle', 'estimated_woba_using_speedangle', 'woba_value', 'woba_denom', 'delta_run_exp', 'home_score', 'away_score', 'sz_top', 'sz_bot']
def get(u):
    for i in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'research-collector'}), timeout=60) as r: return json.loads(r.read())
        except Exception as e: err = e; time.sleep(2 * (i + 1))
    print('FAIL', u, err); return None
def statcast_month(y, m):
    from pybaseball import statcast
    s = dt.date(y, m, 1); e = (dt.date(y + (m == 12), m % 12 + 1, 1) - dt.timedelta(days=1)); e = min(e, dt.date.today())
    if s > dt.date.today(): return
    try: d = statcast(start_dt=str(s), end_dt=str(e), verbose=False, parallel=True)
    except Exception as ex: print('statcast fail', y, m, ex); return
    if d is None or d.empty: print('statcast empty', y, m); return
    d = d[[c for c in SC_COLS if c in d.columns]]
    for c in ('on_1b', 'on_2b', 'on_3b'): d[c] = d[c].notna().astype('int8')
    d.to_parquet(f'{OUT}/statcast/{y}-{m:02d}.parquet', index=False); print('statcast', y, m, len(d))
def games(start, end):
    sch = get(f'https://statsapi.mlb.com/api/v1/schedule?sportId=1&startDate={start}&endDate={end}&gameType=R,F,D,L,W')
    rows = []
    for day in (sch or {}).get('dates', []):
        for g in day['games']:
            if g['status'].get('abstractGameState') != 'Final': continue
            pk = g['gamePk']; b = get(f'https://statsapi.mlb.com/api/v1/game/{pk}/boxscore'); ls = get(f'https://statsapi.mlb.com/api/v1/game/{pk}/linescore')
            if not b: continue
            info = {i.get('label'): i.get('value', '') for i in b.get('info', [])}
            offs = {o['officialType']: o['official']['fullName'] for o in b.get('officials', [])}
            st = {s: (b['teams'][s].get('pitchers') or [None])[0] for s in ('home', 'away')}
            inn = (ls or {}).get('innings', [])
            rows.append(dict(game_pk=pk, date=day['date'], game_type=g['gameType'], season=int(g['season']), venue=g['venue']['name'],
                             home=g['teams']['home']['team']['name'], away=g['teams']['away']['team']['name'],
                             home_runs=g['teams']['home'].get('score'), away_runs=g['teams']['away'].get('score'),
                             home_sp=st['home'], away_sp=st['away'], ump_hp=offs.get('Home Plate'), ump_1b=offs.get('First Base'),
                             weather=info.get('Weather'), wind=info.get('Wind'), first_pitch=info.get('First pitch'), att=info.get('Att'),
                             innings=len(inn), f1_home=inn[0]['home'].get('runs') if inn else None, f1_away=inn[0]['away'].get('runs') if inn else None,
                             f5_home=sum(i['home'].get('runs', 0) or 0 for i in inn[:5]), f5_away=sum(i['away'].get('runs', 0) or 0 for i in inn[:5])))
            time.sleep(.05)
    return pd.DataFrame(rows)
if MODE == 'backfill':
    for y in SEASONS:
        for m in range(3, 12): statcast_month(y, m)
        g = pd.concat([games(f'{y}-{a}', f'{y}-{b}') for a, b in (('03-01', '04-30'), ('05-01', '06-30'), ('07-01', '08-31'), ('09-01', '11-30'))])
        g.to_csv(f'{OUT}/games/{y}.csv', index=False); print('games', y, len(g))
else:
    t = dt.date.today(); p = t.replace(day=1) - dt.timedelta(days=1)
    statcast_month(t.year, t.month)
    if t.day <= 4: statcast_month(p.year, p.month)
    g = games(str(t - dt.timedelta(days=DAYS)), str(t))
    f = f'{OUT}/games/{t.year}.csv'
    if os.path.exists(f): g = pd.concat([pd.read_csv(f), g]).drop_duplicates('game_pk', keep='last')
    g.to_csv(f, index=False); print('games now', len(g))
