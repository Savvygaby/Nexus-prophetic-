"""Odds collector run by GitHub Actions (GitHub's servers can reach the sportsbooks; the analysis workspace cannot).
Saves raw JSON from The Odds API (NFL + MLB: game lines, player props incl. alternates, F5), plus keyless Kalshi and Bovada feeds."""
import json, os, time, glob, urllib.request, urllib.parse, datetime as dt
KEY = (os.environ.get('ODDS_API_KEY') or os.environ.get('ODDSKEY') or os.environ.get('ODDSAPI') or '').strip()
REQ = json.load(open('request.json')) if os.path.exists('request.json') else {}
OUT = 'odds'; os.makedirs(OUT, exist_ok=True)
LOG = {'started': dt.datetime.utcnow().isoformat() + 'Z', 'calls': [], 'errors': [], 'key_present': bool(KEY), 'key_len': len(KEY)}
def get(url, tag, timeout=25):
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=timeout)
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
WANT = ['KXNFLGAME', 'KXNFLSPREAD', 'KXNFLTOTAL', 'KXNFLTD', 'KXNFLANYTD', 'KXNFLREC', 'KXNFLRECYDS', 'KXNFLRSHYDS', 'KXNFLPASSYDS', 'KXNFLPASSTDS', 'KXNFLPASSATT',
        'KXNFLRSHATT', 'KXNFLTEAMTOTAL', 'KXNFLFIRSTTD', 'KXNFL1H', 'KXNFL1HSPREAD', 'KXNFL1HTOTAL',
        'KXMLBGAME', 'KXMLBSPREAD', 'KXMLBTOTAL', 'KXMLBF5', 'KXMLBF5TOTAL', 'KXMLBF5SPREAD', 'KXMLBTEAMTOTAL', 'KXMLBKS', 'KXMLBHIT', 'KXMLBTB', 'KXMLBHR', 'KXMLBHRR',
        'KXMLBRBI', 'KXMLBOUTS', 'KXMLBSB', 'KXMLBWALK', 'KXMLBRFI', 'KXMLBERA', 'KXMLBHA', 'KXMLBWA', 'KXMLBSTAT', 'KXMLBPITCH', 'KXMLBSS', 'KXMLBSERIES']
for ser in WANT:
    time.sleep(0.6)
    k = get(f'https://api.elections.kalshi.com/trade-api/v2/events?series_ticker={ser}&with_nested_markets=true&status=open&limit=200', f'kalshi_{ser}')
    if k is None:
        time.sleep(3); k = get(f'https://api.elections.kalshi.com/trade-api/v2/events?series_ticker={ser}&with_nested_markets=true&status=open&limit=200', f'kalshi_{ser}_retry')
    if k: save(f'kalshi/{ser}.json', k)
# Polymarket (keyless gamma API): sports events with all their markets (moneyline, spreads, totals, props if listed)
for tag in ('nfl', 'mlb'):
    for off in range(0, 1500, 100):
        time.sleep(0.3)
        pm = get(f'https://gamma-api.polymarket.com/events?tag_slug={tag}&active=true&closed=false&limit=100&offset={off}', f'poly_{tag}_{off}')
        if pm: save(f'polymarket/{tag}_{off}.json', pm)
        if not pm or len(pm) < 100: break
for lg, path in (('nfl', 'football/nfl'), ('mlb', 'baseball/mlb')):
    b = get(f'https://www.bovada.lv/services/sports/event/coupon/events/A/description/{path}?marketFilterId=def&preMatchOnly=true&lang=en', f'bovada_{lg}')
    if b: save(f'bovada/{lg}.json', b)
LOG['finished'] = dt.datetime.utcnow().isoformat() + 'Z'
save('manifest.json', LOG)
print(json.dumps({k: (v if k != 'calls' else len(v)) for k, v in LOG.items()}, indent=1)[:3000])

# ---------------- historical props mode (request.json: {"historical": {"sport": ..., "list_dates": [...], "markets": "...", "days": 5}})
HIST = REQ.get('historical')
if HIST and KEY:
    sp = HIST['sport']; mk = HIST['markets']; tag = HIST.get('tag', 'hist')
    for ld in HIST['list_dates']:
        evs = get(f'https://api.the-odds-api.com/v4/historical/sports/{sp}/events?apiKey={KEY}&date={ld}', f'hist_events_{ld}')
        if not evs: continue
        t0 = dt.datetime.strptime(ld, '%Y-%m-%dT%H:%M:%SZ')
        for e in evs.get('data', []):
            ct = dt.datetime.strptime(e['commence_time'], '%Y-%m-%dT%H:%M:%SZ')
            if ct < t0 or ct > t0 + dt.timedelta(days=HIST.get('days', 5)): continue
            snap = (ct - dt.timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%SZ')
            o = get(f"https://api.the-odds-api.com/v4/historical/sports/{sp}/events/{e['id']}/odds?apiKey={KEY}&regions=us&markets={mk}&oddsFormat=decimal&date={snap}", f"hist_{e['id']}")
            if o: save(f"{tag}/{e['id']}.json", o)
    LOG['finished_hist'] = dt.datetime.utcnow().isoformat() + 'Z'; save('manifest.json', LOG)

# ======================= Oct 2 additions =======================
NOW = dt.datetime.utcnow().strftime('%Y%m%dT%H%MZ')
# (1) Pinnacle (sharpest book) via bookmakers=pinnacle: game lines + main props
if KEY and REQ.get('pinnacle', True):
    PIN_PROPS = {'nfl': 'player_pass_yds,player_rush_yds,player_receptions,player_reception_yds,player_anytime_td,player_pass_tds',
                 'mlb': 'batter_hits,batter_total_bases,batter_home_runs,pitcher_strikeouts,pitcher_outs,batter_hits_runs_rbis'}
    for sp, cfg in SPORTS.items():
        if sp not in REQ.get('sports', ['nfl', 'mlb']): continue
        evf = f'{OUT}/{sp}/events.json'
        if not os.path.exists(evf): continue
        lim = dt.datetime.utcnow() + dt.timedelta(days=cfg['days'])
        for e in json.load(open(evf)):
            t = dt.datetime.strptime(e['commence_time'], '%Y-%m-%dT%H:%M:%SZ')
            if t < dt.datetime.utcnow() or t > lim: continue
            g = get(f"{API}/{cfg['key']}/events/{e['id']}/odds?apiKey={KEY}&bookmakers=pinnacle&markets=h2h,spreads,totals&oddsFormat=american", f"pin_game_{e['id']}")
            if g: save(f"{sp}/pin_game_{e['id']}.json", g)
            p = get(f"{API}/{cfg['key']}/events/{e['id']}/odds?apiKey={KEY}&bookmakers=pinnacle&markets={PIN_PROPS[sp]}&oddsFormat=decimal", f"pin_props_{e['id']}")
            if p: save(f"{sp}/pin_props_{e['id']}.json", p)
# (2) line-movement snapshots: compact copy of every game line this run
snap = {}
for sp in ('nfl', 'mlb'):
    for f in glob.glob(f'{OUT}/{sp}/game_*.json') + glob.glob(f'{OUT}/{sp}/pin_game_*.json'):
        try: snap[os.path.basename(f)] = json.load(open(f))
        except Exception: pass
if snap: save(f'snapshots/{NOW}_games.json', snap)
# (3) hourly weather (Open-Meteo, keyless) for venues listed in request.json
for v in REQ.get('weather', []):
    w = get(f"https://api.open-meteo.com/v1/forecast?latitude={v['lat']}&longitude={v['lon']}&hourly=temperature_2m,relative_humidity_2m,precipitation_probability,wind_speed_10m,wind_direction_10m,wind_gusts_10m,surface_pressure&wind_speed_unit=mph&temperature_unit=fahrenheit&timezone=America%2FNew_York&forecast_days=5", f"wx_{v['id']}")
    if w: save(f"weather/{v['id']}.json", w)
# (4) MLB bullpen usage: StatsAPI box scores for the last 4 days
if REQ.get('mlb_bullpen', True):
    d0 = (dt.datetime.utcnow() - dt.timedelta(days=4)).strftime('%Y-%m-%d'); d1 = dt.datetime.utcnow().strftime('%Y-%m-%d')
    sch = get(f'https://statsapi.mlb.com/api/v1/schedule?sportId=1&startDate={d0}&endDate={d1}', 'mlb_schedule')
    bp = []
    for dd in (sch or {}).get('dates', []):
        for gm in dd.get('games', []):
            if gm.get('status', {}).get('abstractGameState') != 'Final': continue
            bx = get(f"https://statsapi.mlb.com/api/v1/game/{gm['gamePk']}/boxscore", f"box_{gm['gamePk']}")
            if not bx: continue
            for side in ('away', 'home'):
                t = bx['teams'][side]
                for pid in t.get('pitchers', []):
                    pl = t['players'].get(f'ID{pid}', {}); st = pl.get('stats', {}).get('pitching', {})
                    bp.append(dict(date=dd['date'], game=gm['gamePk'], team=t['team'].get('abbreviation') or t['team'].get('name'), pitcher=pl.get('person', {}).get('fullName'),
                                   pitches=st.get('numberOfPitches') or st.get('pitchesThrown'), outs=st.get('outs'), first=pid == t.get('pitchers', [None])[0]))
    save('mlb/bullpen_last4d.json', bp)
# (5) Baseball Savant bat-tracking leaderboards (one-off, request.json 'bat_tracking': true)
if REQ.get('bat_tracking'):
    for yr in (2024, 2025, 2026):
        for url in (f'https://baseballsavant.mlb.com/leaderboard/bat-tracking?attackZone=&batSide=&contactType=&count=&dateStart={yr}-03-01&dateEnd={yr}-11-30&gameType=R&isHardHit=&minSwings=50&minGroupSwings=1&pitchHand=&pitchType=&seasonStart=&seasonEnd=&team=&type=batter&csv=true',
                    f'https://baseballsavant.mlb.com/leaderboard/bat-tracking?type=batter&seasonStart={yr}&seasonEnd={yr}&minSwings=50&csv=true'):
            try:
                r = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=60).read().decode('utf-8', 'ignore')
                if r.count('\n') > 20 and ',' in r[:300]:
                    os.makedirs(f'{OUT}/savant', exist_ok=True); open(f'{OUT}/savant/bat_tracking_{yr}.csv', 'w').write(r); LOG['calls'].append(dict(tag=f'bat_{yr}', status=200)); break
            except Exception as ex: LOG['errors'].append(dict(tag=f'bat_{yr}', err=str(ex)[:150]))
save('manifest.json', LOG)

# ======================= MLB fresh data (request.json 'mlb_fresh': true) =======================
if REQ.get('mlb_fresh'):
    # MLB StatsAPI: probable pitchers + posted lineups for the next 4 days
    d0 = dt.datetime.utcnow().strftime('%Y-%m-%d'); d1 = (dt.datetime.utcnow() + dt.timedelta(days=4)).strftime('%Y-%m-%d')
    sch = get(f'https://statsapi.mlb.com/api/v1/schedule?sportId=1&startDate={d0}&endDate={d1}&hydrate=probablePitcher,lineups,officials,weather,venue', 'mlb_sched_fwd')
    if sch: save('mlb/schedule_forward.json', sch)
    # pybaseball: Statcast pitch-level since our sportsdataverse copy ends (fills the ~3-week lag), + sprint speed
    try:
        import subprocess; subprocess.run(['pip', 'install', '-q', 'pybaseball'], check=False)
        import pybaseball as pb; pb.cache.enable()
        sc = pb.statcast(start_dt=REQ.get('statcast_start', '2026-09-01'), end_dt=d0)
        keep = [c for c in ['game_date', 'game_pk', 'at_bat_number', 'pitch_number', 'batter', 'pitcher', 'events', 'description', 'pitch_type', 'release_speed', 'plate_x', 'plate_z',
                            'sz_top', 'sz_bot', 'balls', 'strikes', 'launch_speed', 'launch_angle', 'bat_speed', 'swing_length', 'home_team', 'away_team', 'inning_topbot', 'game_type'] if c in sc.columns]
        os.makedirs(f'{OUT}/mlb', exist_ok=True); sc[keep].to_csv(f'{OUT}/mlb/statcast_recent.csv.gz', index=False, compression='gzip'); LOG['calls'].append(dict(tag='statcast', rows=len(sc)))
    except Exception as ex: LOG['errors'].append(dict(tag='pybaseball', err=str(ex)[:200]))
    save('manifest.json', LOG)


# ======================= StatsAPI schedule for a date range (maps game_pk <-> teams for backtests) =======================
if REQ.get('mlb_sched_range'):
    a, b = REQ['mlb_sched_range']
    s_ = get(f'https://statsapi.mlb.com/api/v1/schedule?sportId=1&startDate={a}&endDate={b}', 'mlb_sched_range')
    if s_: save(f'mlb/schedule_{a}_{b}.json', s_)
    save('manifest.json', LOG)


# ======================= Baseball Savant leaderboards (request.json 'savant_extra': true) =======================
if REQ.get('savant_extra'):
    SV = {'xstats_bat': 'https://baseballsavant.mlb.com/leaderboard/expected_statistics?type=batter&year={y}&position=&team=&filterType=bip&min=25&csv=true',
          'xstats_pit': 'https://baseballsavant.mlb.com/leaderboard/expected_statistics?type=pitcher&year={y}&position=&team=&filterType=bip&min=25&csv=true',
          'statcast_bat': 'https://baseballsavant.mlb.com/leaderboard/statcast?type=batter&year={y}&position=&team=&min=25&csv=true',
          'framing': 'https://baseballsavant.mlb.com/leaderboard/catcher-framing?type=catcher&seasonStart={y}&seasonEnd={y}&team=&min=1&sortColumn=rv_tot&sortDirection=desc&csv=true',
          'framing2': 'https://baseballsavant.mlb.com/catcher_framing?year={y}&team=&min=1&type=catcher&sort=4,1&csv=true'}
    os.makedirs(f'{OUT}/savant', exist_ok=True)
    for name, u in SV.items():
        for yr in (2023, 2024, 2025, 2026):
            try:
                r = urllib.request.urlopen(urllib.request.Request(u.format(y=yr), headers={'User-Agent': 'Mozilla/5.0'}), timeout=60).read().decode('utf-8', 'ignore')
                if r.count('\n') > 10 and ',' in r[:300]: open(f'{OUT}/savant/{name}_{yr}.csv', 'w').write(r); LOG['calls'].append(dict(tag=f'{name}_{yr}', status=200, lines=r.count('\n')))
                else: LOG['errors'].append(dict(tag=f'{name}_{yr}', err='not csv: ' + r[:120]))
            except Exception as ex: LOG['errors'].append(dict(tag=f'{name}_{yr}', err=str(ex)[:150]))
            time.sleep(1)
    save('manifest.json', LOG)


# ======================= Statcast catcher per PA (request.json 'statcast_catchers': [[start, end], ...]) =======================
if REQ.get('statcast_catchers'):
    try:
        import subprocess; subprocess.run(['pip', 'install', '-q', 'pybaseball'], check=False)
        import pybaseball as pb; pb.cache.enable()
        os.makedirs(f'{OUT}/mlb', exist_ok=True)
        for a, b in REQ['statcast_catchers']:
            t0 = time.time(); sc = pb.statcast(start_dt=a, end_dt=b)
            pa = sc[sc.events.notna()][['game_pk', 'game_date', 'at_bat_number', 'pitcher', 'batter', 'fielder_2', 'events', 'game_type', 'home_team', 'away_team', 'inning_topbot']]
            pa.to_csv(f'{OUT}/mlb/catchers_{a[:4]}.csv.gz', index=False, compression='gzip'); LOG['calls'].append(dict(tag=f'catchers_{a[:4]}', rows=len(pa), sec=round(time.time() - t0)))
            save('manifest.json', LOG)
    except Exception as ex: LOG['errors'].append(dict(tag='statcast_catchers', err=str(ex)[:200]))
    save('manifest.json', LOG)

# ======================= Reddit via PRAW + VADER (needs secrets REDDITID / REDDITSECRET / REDDITAGENT) =======================
RD = REQ.get('reddit')
if RD:
    rid, rsec, rag = os.environ.get('REDDITID', '').strip(), os.environ.get('REDDITSECRET', '').strip(), os.environ.get('REDDITAGENT', 'sports-model').strip()
    LOG['reddit_creds'] = bool(rid and rsec)
    if rid and rsec:
        try:
            import subprocess; subprocess.run(['pip', 'install', '-q', 'praw', 'vaderSentiment'], check=False)
            import praw
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
            sia = SentimentIntensityAnalyzer()
            # sports slang the base lexicon misreads (positive in sports context)
            sia.lexicon.update({'beast': 2.0, 'cooking': 1.5, 'sleeper': 1.0, 'smash': 1.5, 'stud': 2.0, 'locked': 1.0, 'nuke': 1.5, 'bust': -2.0, 'dud': -2.0, 'questionable': -0.8, 'limited': -0.8, 'dnp': -1.5})
            reddit = praw.Reddit(client_id=rid, client_secret=rsec, user_agent=rag)
            out = {}
            for grp in RD.get('groups', []):
                names = [l.strip() for l in open(grp['names_file']) if l.strip()][:grp.get('max', 300)]
                for nm in names:
                    last = nm.split()[-1]; rows = []
                    for sub in grp['subs']:
                        try:
                            for post in reddit.subreddit(sub).search(f'"{nm}"', sort='new', time_filter=RD.get('time_filter', 'month'), limit=RD.get('limit', 40)):
                                txt = (post.title or '') + ' ' + (post.selftext or '')[:1500]
                                rows.append(dict(t=int(post.created_utc), sub=sub, score=post.score, ncom=post.num_comments, kind='post',
                                                 s=sia.polarity_scores(txt)['compound'], inj=int(any(w in txt.lower() for w in ('injur', 'hamstring', 'ankle', 'knee', 'questionable', 'out for', 'ruled out', 'limited', 'dnp', 'il '))),
                                                 title=(post.title or '')[:140]))
                                post.comment_sort = 'top'; post.comments.replace_more(limit=0)
                                for c in post.comments[:15]:
                                    b = c.body or ''
                                    if last.lower() in b.lower():          # only comments about THIS player (avoid opponent/other-player sentiment)
                                        rows.append(dict(t=int(c.created_utc), sub=sub, score=c.score, kind='comment', s=sia.polarity_scores(b[:800])['compound'],
                                                         inj=int(any(w in b.lower() for w in ('injur', 'hamstring', 'questionable', 'ruled out', 'limited')))))
                            time.sleep(0.7)
                        except Exception as ex: LOG['errors'].append(dict(tag=f'reddit_{sub}_{nm}', err=str(ex)[:120]))
                    out[nm] = rows
            save('sentiment/reddit_vader.json', out); LOG['calls'].append(dict(tag='reddit', players=len(out)))
        except Exception as ex: LOG['errors'].append(dict(tag='reddit', err=str(ex)[:200]))
    save('manifest.json', LOG)

# ======================= sentiment / attention (request.json 'sentiment': {...}) =======================
SEN = REQ.get('sentiment')
if SEN:
    names = [l.strip() for l in open('players.txt') if l.strip()][:SEN.get('max', 500)]
    s0, s1 = SEN['start'], SEN['end']          # YYYYMMDDHHMMSS
    t_start = time.time()
    for i, nm in enumerate(names):
        if time.time() - t_start > SEN.get('budget_min', 50) * 60: LOG['errors'].append(dict(tag='gdelt_budget', err=f'stopped after {i} players')); break
        q = urllib.parse.quote(f'"{nm}"')
        for mode in SEN.get('modes', ['timelinevolraw', 'timelinetone']):
            time.sleep(5.5)
            extra = '&maxrecords=250&sort=datedesc' if mode == 'artlist' else ''
            d = get(f'https://api.gdeltproject.org/api/v2/doc/doc?query={q}%20sourcelang:english&mode={mode}&startdatetime={s0}&enddatetime={s1}&format=json{extra}', f'gdelt_{mode}_{i}', timeout=20)
            if d: save(f'sentiment/gdelt/{mode}/{nm.replace(" ", "_").replace("/", "")}.json', d)
    # Google Trends (unofficial, may be rate-limited from cloud IPs) - small probe
    try:
        if not SEN.get('trends', True): raise RuntimeError('trends off')
        import subprocess; subprocess.run(['pip', 'install', '-q', 'pytrends'], check=False)
        from pytrends.request import TrendReq
        tr = TrendReq(hl='en-US', tz=240); res = {}
        for j in range(0, min(len(names), SEN.get('trends_max', 60)), 5):
            kw = names[j:j + 5]
            try:
                tr.build_payload(kw, timeframe=SEN.get('trends_tf', 'today 3-m'), geo='US'); df_ = tr.interest_over_time()
                res.update({k: df_[k].reset_index().astype(str).values.tolist() for k in kw if k in df_})
            except Exception as ex: LOG['errors'].append(dict(tag=f'trends_{j}', err=str(ex)[:150])); break
            time.sleep(8)
        save('sentiment/google_trends.json', res)
    except Exception as ex: LOG['errors'].append(dict(tag='trends', err=str(ex)[:150]))
    # Reddit public search JSON (often blocked for cloud IPs) - probe
    rr = get('https://www.reddit.com/r/fantasyfootball/search.json?q=injury&restrict_sr=1&sort=new&limit=25', 'reddit_probe')
    if rr: save('sentiment/reddit_probe.json', rr)
    save('manifest.json', LOG)

# ======================= VADER on GDELT headlines (artlist), separates injury news from tone =======================
if SEN and 'artlist' in SEN.get('modes', []):
    try:
        import subprocess; subprocess.run(['pip', 'install', '-q', 'vaderSentiment'], check=False)
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        sia = SentimentIntensityAnalyzer(); agg = {}
        for f in glob.glob(f'{OUT}/sentiment/gdelt/artlist/*.json'):
            d = json.load(open(f)); nm = os.path.basename(f)[:-5].replace('_', ' ')
            agg[nm] = [dict(t=a.get('seendate'), s=sia.polarity_scores(a.get('title', ''))['compound'],
                            inj=int(any(w in (a.get('title', '').lower()) for w in ('injur', 'hamstring', 'ankle', 'knee', 'questionable', 'ruled out', 'limited', 'surgery', 'concussion'))),
                            dom=a.get('domain')) for a in d.get('articles', [])]
        save('sentiment/gdelt_vader.json', agg)
    except Exception as ex: LOG['errors'].append(dict(tag='vader_gdelt', err=str(ex)[:150]))
    save('manifest.json', LOG)

