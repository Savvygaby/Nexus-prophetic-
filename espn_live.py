"""ESPN live NFL game-state parser.

Fetches the public site API (scoreboard -> event id, summary -> state + box score) and returns a flat state dict:
score, quarter, clock, possession, down, distance, yardline_100, timeouts, per-player box score so far, injury flags.

Field sources (reference: sportsdataverse-py nfl_pbp.py / pseudo-r Public-ESPN-API docs):
  header.competitions[0]           -> teams, scores, status (period, clock, state)
  situation (summary) or scoreboard competitions[0].situation -> down, distance, yardLine, possession, timeouts
  drives.current / drives.previous -> fallback for down/distance/yardsToEndzone and first possession
  boxscore.players[*].statistics   -> passing / rushing / receiving lines (indexed by `keys`)
  injuries[*].injuries             -> pregame/in-game status; play text "... injured" -> in-game flags

NOTE: site.api.espn.com is blocked from the analysis sandbox (proxy 403). Run fetches inside GitHub Actions
(see collector_proposal/) and parse the committed JSON locally with `--file`.

CLI:
  python espn_live.py --teams ATL NO --date 20261005           # fetch live (Actions / unblocked hosts only)
  python espn_live.py --file summary.json [--scoreboard sb.json] # parse a saved payload
"""
import json, re, sys, argparse, urllib.request

SITE = 'https://site.api.espn.com/apis/site/v2/sports/football/nfl'
# ESPN abbreviations that differ from nflverse
ESPN2NFLV = {'WSH': 'WAS', 'JAX': 'JAX', 'LAR': 'LA', 'LV': 'LV'}


def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def scoreboard(date=None):
    return fetch(f"{SITE}/scoreboard" + (f"?dates={date}" if date else ''))


def find_event(sb, away, home):
    """Return (event_id, competition) for away@home in a scoreboard payload."""
    for e in sb.get('events', []):
        c = e['competitions'][0]
        ab = {x['homeAway']: _abbr(x['team']['abbreviation']) for x in c['competitors']}
        if ab.get('home') == home and ab.get('away') == away:
            return e['id'], c
    return None, None


def summary(event_id):
    return fetch(f"{SITE}/summary?event={event_id}")


def _abbr(a):
    return ESPN2NFLV.get(a, a)


def _num(x, default=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _clock_secs(status):
    c = status.get('clock')
    if c is not None and _num(c) is not None:
        return float(c)
    dc = status.get('displayClock') or '15:00'
    m = re.match(r'(\d+):(\d+)', dc)
    return int(m.group(1)) * 60 + int(m.group(2)) if m else 900.0


def norm_name(s):
    s = re.sub(r"[^a-z ]", '', (s or '').lower().replace('-', ' '))
    s = re.sub(r'\b(jr|sr|ii|iii|iv|v)\b', '', s)
    return ' '.join(s.split())


def parse_box(sm, id2abbr):
    """Per-player box score so far. Keys follow pbp_sim stat names."""
    out = {}
    for tb in sm.get('boxscore', {}).get('players', []):
        team = _abbr(tb['team']['abbreviation'])
        for cat in tb.get('statistics', []):
            keys = cat.get('keys') or []
            for a in cat.get('athletes', []):
                ath = a['athlete']; st = dict(zip(keys, a.get('stats', [])))
                p = out.setdefault(ath['id'], dict(espn_id=ath['id'], name=ath.get('displayName'), key=norm_name(ath.get('displayName')),
                                                    team=team, pass_att=0, pass_cmp=0, pass_yds=0, pass_tds=0, ints=0, carries=0, rush_yds=0,
                                                    receptions=0, targets=0, rec_yds=0, tds=0))
                if cat['name'] == 'passing':
                    ca = st.get('completions/passingAttempts', '0/0').split('/')
                    p['pass_cmp'], p['pass_att'] = int(_num(ca[0], 0)), int(_num(ca[-1], 0))
                    p['pass_yds'] = _num(st.get('passingYards'), 0); p['pass_tds'] = int(_num(st.get('passingTouchdowns'), 0))
                    p['ints'] = int(_num(st.get('interceptions'), 0))
                elif cat['name'] == 'rushing':
                    p['carries'] = int(_num(st.get('rushingAttempts'), 0)); p['rush_yds'] = _num(st.get('rushingYards'), 0)
                    p['tds'] += int(_num(st.get('rushingTouchdowns'), 0))
                elif cat['name'] == 'receiving':
                    p['receptions'] = int(_num(st.get('receptions'), 0)); p['rec_yds'] = _num(st.get('receivingYards'), 0)
                    p['targets'] = int(_num(st.get('receivingTargets'), p['receptions']))
                    p['tds'] += int(_num(st.get('receivingTouchdowns'), 0))
    return out


INJ_RE = re.compile(r"([A-Z][\w.'\-]*\.?\s?[A-Z][\w'\-]+)[^.]{0,40}?\b(?:was|is|has been)\s+(?:injured|ruled out|declared out|carted)", re.I)
OUT_RE = re.compile(r"([A-Z][\w.'\-]*\.?\s?[A-Z][\w'\-]+)[^.]{0,60}?\b(?:ruled out|declared out|will not return|is out)", re.I)


def parse_injuries(sm, plays):
    pre = []
    for t in sm.get('injuries', []) or []:
        team = _abbr(t.get('team', {}).get('abbreviation', ''))
        for i in t.get('injuries', []):
            a = i.get('athlete', {})
            pre.append(dict(team=team, name=a.get('displayName'), key=norm_name(a.get('displayName')), status=i.get('status'),
                            pos=(a.get('position') or {}).get('abbreviation')))
    out_status = {'out', 'doubtful', 'injured reserve', 'ir', 'suspension', 'pup'}
    flagged_out = [p for p in pre if (p['status'] or '').lower() in out_status]
    ingame, ruled_out, returned = [], [], set()
    RET_RE = re.compile(r"([A-Z]{2,3}-[A-Z][\w.'\-]+)\s+has returned", re.I)
    for pl in plays:
        txt = pl.get('text') or ''
        for m in INJ_RE.finditer(txt):
            ingame.append(dict(name=m.group(1), period=pl.get('period', {}).get('number'), clock=pl.get('clock', {}).get('displayValue'), text=txt[:160]))
        for m in OUT_RE.finditer(txt):
            ruled_out.append(m.group(1))
        for m in RET_RE.finditer(txt):
            returned.add(m.group(1))
    still = sorted({i['name'] for i in ingame} - returned)
    return dict(report=pre, out=flagged_out, in_game_injured=ingame, returned=sorted(returned), in_game_still_out=still, in_game_out=sorted(set(ruled_out)))


def all_plays(sm):
    d = sm.get('drives') or {}
    drives = list(d.get('previous') or [])
    if d.get('current'):
        cur = d['current']
        if not drives or drives[-1].get('id') != cur.get('id'):
            drives.append(cur)
    plays = []
    for dr in drives:
        for p in dr.get('plays', []):
            p = dict(p); p['_drive_team'] = (dr.get('team') or {}).get('id'); plays.append(p)
    return drives, plays


def count_timeouts(plays, id2abbr, period):
    """Fallback: timeouts used this half per team from play text/type ('Timeout #2 by NO at 03:12')."""
    half = 1 if period <= 2 else 2
    used = {}
    for p in plays:
        pp = p.get('period', {}).get('number', 0)
        if (1 if pp <= 2 else 2) != half or pp > 4: continue
        if 'timeout' in ((p.get('type') or {}).get('text') or '').lower() and 'official' not in (p.get('text') or '').lower():
            m = re.search(r'by\s+([A-Z]{2,3})', p.get('text') or '')
            if m: used[_abbr(m.group(1))] = used.get(_abbr(m.group(1)), 0) + 1
    return {t: max(0, 3 - used.get(t, 0)) for t in id2abbr.values()}


def parse(sm, sb_comp=None):
    hdr = sm['header']; comp = hdr['competitions'][0]
    teams = {x['homeAway']: x for x in comp['competitors']}
    id2abbr = {x['team']['id']: _abbr(x['team']['abbreviation']) for x in comp['competitors']}
    home, away = _abbr(teams['home']['team']['abbreviation']), _abbr(teams['away']['team']['abbreviation'])
    status = comp.get('status') or (sb_comp or {}).get('status') or {}
    stype = status.get('type', {})
    period = int(status.get('period') or 0)
    clock = _clock_secs(status)
    if not period and stype.get('state') == 'post':
        period, clock = 4, 0.0
    st = dict(event_id=hdr.get('id'), home=home, away=away, state=stype.get('state'), status=stype.get('detail') or stype.get('description'),
              completed=bool(stype.get('completed')), quarter=period, clock=clock, display_clock=status.get('displayClock'),
              home_score=int(_num(teams['home'].get('score'), 0)), away_score=int(_num(teams['away'].get('score'), 0)))
    if period <= 4:
        st['game_seconds_remaining'] = max(0, (4 - max(period, 1)) * 900 + (clock if period >= 1 else 900))
    else:
        st['game_seconds_remaining'] = clock          # overtime: seconds left in OT period
    st['halftime'] = 'half' in (stype.get('detail') or '').lower() or stype.get('name') == 'STATUS_HALFTIME'
    drives, plays = all_plays(sm)
    st['first_possession'] = id2abbr.get((drives[0].get('team') or {}).get('id')) if drives else None
    sit = sm.get('situation') or (sb_comp or {}).get('situation') or {}
    last = sit.get('lastPlay') or {}
    pos_id = (sit.get('possession') if isinstance(sit.get('possession'), str) else (sit.get('possession') or {}).get('id')) if sit else None
    down, dist, yl100 = sit.get('down'), sit.get('distance'), None
    if last.get('end', {}).get('yardsToEndzone') is not None and (last.get('end', {}).get('team') or {}).get('id') in (pos_id, None):
        yl100 = last['end']['yardsToEndzone']
    if yl100 is None and sit.get('possessionText') and pos_id:
        m = re.match(r'([A-Z]{2,3})\s+(\d+)', sit['possessionText'])
        if m:
            n = int(m.group(2)); yl100 = 100 - n if _abbr(m.group(1)) == id2abbr.get(pos_id) else n
        elif sit['possessionText'].strip().endswith('50'):
            yl100 = 50
    src = 'situation' if sit else 'drives'
    # fallback / no situation block: last real play's end state
    real = [p for p in plays if (p.get('type') or {}).get('text') not in ('End Period', 'End of Half', 'End of Game', 'Timeout', 'Official Timeout')]
    lp = real[-1] if real else None
    if (down is None or yl100 is None or pos_id is None) and lp:
        e = lp.get('end') or {}
        pos_id = pos_id or (e.get('team') or {}).get('id') or lp.get('_drive_team')
        down = down if down is not None else e.get('down')
        dist = dist if dist is not None else e.get('distance')
        yl100 = yl100 if yl100 is not None else e.get('yardsToEndzone')
    st['possession'] = id2abbr.get(pos_id)
    st['down'] = int(down) if down not in (None, 0, -1) else None
    st['distance'] = int(dist) if dist not in (None, -1) else None
    st['yardline_100'] = int(yl100) if yl100 not in (None,) else None
    st['down_distance_text'] = sit.get('downDistanceText') or (lp or {}).get('end', {}).get('downDistanceText')
    # pending kickoff: last play was a score / start of half -> receiving team gets ball at own 30 (yl 70 sim convention)
    lp_txt = ((lp or {}).get('type') or {}).get('text', '')
    st['pending_kickoff'] = bool(lp and (lp.get('scoringPlay') or 'Kickoff' in lp_txt) and not st['down'])
    if sit and sit.get('homeTimeouts') is not None:
        st['home_timeouts'], st['away_timeouts'] = int(sit['homeTimeouts']), int(sit['awayTimeouts'])
    else:
        to = count_timeouts(plays, id2abbr, period or 1)
        st['home_timeouts'], st['away_timeouts'] = to.get(home, 3), to.get(away, 3)
    st['situation_source'] = src
    st['players'] = list(parse_box(sm, id2abbr).values())
    st['injuries'] = parse_injuries(sm, plays)
    st['n_plays'] = len(plays)
    st['last_play'] = (lp or {}).get('text')
    return st


def get_state(away='ATL', home='NO', date='20261005', event_id=None):
    sb_comp = None
    if not event_id:
        sb = scoreboard(date)
        event_id, sb_comp = find_event(sb, away, home)
        if not event_id:
            raise SystemExit(f'event {away}@{home} not on scoreboard {date}')
    sm = summary(event_id)
    return parse(sm, sb_comp), sm


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--teams', nargs=2, metavar=('AWAY', 'HOME'), default=['ATL', 'NO'])
    ap.add_argument('--date', default='20261005')
    ap.add_argument('--event')
    ap.add_argument('--file', help='saved summary JSON')
    ap.add_argument('--scoreboard', help='saved scoreboard JSON (for situation fallback)')
    ap.add_argument('--out')
    a = ap.parse_args()
    if a.file:
        sm = json.load(open(a.file)); comp = None
        if a.scoreboard:
            _, comp = find_event(json.load(open(a.scoreboard)), *a.teams)
        st = parse(sm, comp)
    else:
        st, _ = get_state(a.teams[0], a.teams[1], a.date, a.event)
    s = json.dumps(st, indent=1, default=str)
    if a.out: open(a.out, 'w').write(s)
    print(s if not a.out else f"wrote {a.out}: {st['away']} {st['away_score']} @ {st['home']} {st['home_score']} Q{st['quarter']} {st['display_clock']} "
          f"pos={st['possession']} {st['down']}&{st['distance']} yl100={st['yardline_100']} TO h{st['home_timeouts']}/a{st['away_timeouts']} players={len(st['players'])}")
