"""PROPOSED collector mode 'live_nfl' for Savvygaby/nexus-prophetic- (separate file; collect.py untouched).
Runs in GitHub Actions (ESPN is reachable there, not from the analysis sandbox). Polls the ESPN site API every
poll_secs for up to max_hours, writes parsed game state and pushes a commit whenever the state changes.

live_request.json:
  {"live_nfl": {"away": "ATL", "home": "NO", "date": "20261005", "game_id": "2026_04_ATL_NO",
                "poll_secs": 60, "max_hours": 4, "start_after": "2026-10-06T00:05:00Z"}}
Outputs (repo):
  live/<game_id>/state_latest.json   parsed state (espn_live.parse)            -- every change
  live/<game_id>/states.jsonl        one line per poll (compact, no player list)
  live/<game_id>/summary_latest.json raw summary, heavy keys stripped           -- every `raw_every` polls
  live/<game_id>/manifest.json       poll count, errors, last update
"""
import json, os, time, subprocess, datetime as dt, traceback
import espn_live as E                      # copy ghtests/live/espn_live.py next to this file

REQ = json.load(open('live_request.json')).get('live_nfl', {})
AWAY, HOME, DATE = REQ.get('away', 'ATL'), REQ.get('home', 'NO'), REQ.get('date', '20261005')
GID = REQ.get('game_id', f'live_{AWAY}_{HOME}')
POLL = int(REQ.get('poll_secs', 60)); MAX_H = float(REQ.get('max_hours', 4)); RAW_EVERY = int(REQ.get('raw_every', 5))
OUT = f'live/{GID}'; os.makedirs(OUT, exist_ok=True)
DROP = ('news', 'videos', 'article', 'standings', 'broadcasts', 'gameInfo', 'leaders', 'againstTheSpread', 'meta')
MAN = dict(started=dt.datetime.utcnow().isoformat() + 'Z', polls=0, commits=0, errors=[], event_id=None)


def sh(*a):
    return subprocess.run(list(a), capture_output=True, text=True)


def push(msg):
    sh('git', 'add', '-A', 'live')
    if sh('git', 'diff', '--cached', '--quiet').returncode == 0: return
    sh('git', 'commit', '-q', '-m', msg)
    for _ in range(5):
        if sh('git', 'pull', '--rebase', '-X', 'theirs', '-q').returncode == 0 and sh('git', 'push', '-q').returncode == 0:
            MAN['commits'] += 1; return
        time.sleep(5)
    MAN['errors'].append(dict(t=time.time(), err='push failed'))


sa = REQ.get('start_after')
if sa:
    t0 = dt.datetime.strptime(sa, '%Y-%m-%dT%H:%M:%SZ')
    wait = (t0 - dt.datetime.utcnow()).total_seconds()
    if 0 < wait < 3 * 3600: print(f'sleeping {wait:.0f}s until {sa}', flush=True); time.sleep(wait)
end_t = time.time() + MAX_H * 3600
last_key, eid, comp = None, None, None
while time.time() < end_t:
    t_poll = time.time()
    try:
        if not eid:
            eid, comp = E.find_event(E.scoreboard(DATE), AWAY, HOME); MAN['event_id'] = eid
        sb_comp = None
        if MAN['polls'] % 5 == 0:                  # scoreboard carries `situation` even when summary omits it
            _, sb_comp = E.find_event(E.scoreboard(DATE), AWAY, HOME)
        sm = E.summary(eid)
        st = E.parse(sm, sb_comp)
        st['fetched_utc'] = dt.datetime.utcnow().isoformat() + 'Z'
        MAN['polls'] += 1
        key = (st['home_score'], st['away_score'], st['quarter'], st['display_clock'], st['possession'], st['down'], st['distance'], st['yardline_100'], st['n_plays'])
        with open(f'{OUT}/states.jsonl', 'a') as f:
            f.write(json.dumps({k: v for k, v in st.items() if k not in ('players', 'injuries')}) + '\n')
        if key != last_key:
            json.dump(st, open(f'{OUT}/state_latest.json', 'w'), indent=0)
            if MAN['polls'] % RAW_EVERY == 1 or st['completed']:
                json.dump({k: v for k, v in sm.items() if k not in DROP}, open(f'{OUT}/summary_latest.json', 'w'))
            MAN['last'] = st['fetched_utc']; json.dump(MAN, open(f'{OUT}/manifest.json', 'w'))
            push(f"live {GID} Q{st['quarter']} {st['display_clock']} {st['away']} {st['away_score']}-{st['home']} {st['home_score']}")
            last_key = key
        print(st['status'], key, flush=True)
        if st['completed']:
            break
        if st['state'] == 'pre':
            time.sleep(max(POLL, 120) - (time.time() - t_poll)); continue
    except Exception as e:
        MAN['errors'].append(dict(t=dt.datetime.utcnow().isoformat(), err=str(e)[:200])); traceback.print_exc()
    time.sleep(max(5, POLL - (time.time() - t_poll)))
MAN['finished'] = dt.datetime.utcnow().isoformat() + 'Z'
json.dump(MAN, open(f'{OUT}/manifest.json', 'w')); push(f'live {GID} final')
