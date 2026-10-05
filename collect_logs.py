"""Market & news logger (runs on a schedule in GitHub Actions). Saves raw, timestamped snapshots so we can backtest later:
- DraftKings Network public betting splits page (NFL), raw HTML (gzip) -> logs/splits/
- ESPN NFL injuries + news JSON (timestamped statuses, hours before nflverse) -> logs/espn/
- Sleeper player injury statuses (once a day) -> logs/sleeper/
Raw pages are kept on purpose: parsing happens later, offline, so a page-layout change never loses a day."""
import gzip, json, os, time, datetime as dt, urllib.request
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36',
      'Accept': 'text/html,application/json;q=0.9,*/*;q=0.8'}
now = dt.datetime.utcnow(); stamp = now.strftime('%Y%m%dT%H%MZ')
def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=40) as r: return r.read()
def save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with gzip.open(path, 'wb') as f: f.write(data)
log = {'t': stamp, 'ok': [], 'err': []}
for p in range(1, 5):
    url = f'https://dknetwork.draftkings.com/draftkings-sportsbook-betting-splits/?tb_eg=88808&tb_edate=n7days&tb_emt=0&tb_page={p}'
    try:
        b = get(url); save(f'logs/splits/{stamp}_p{p}.html.gz', b); log['ok'].append(f'splits p{p} {len(b)}')
        if b.count(b'tb-se ') < 2: break
    except Exception as e: log['err'].append(f'splits p{p}: {e}'); break
for name, url in (('injuries', 'https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries'),
                  ('injuries_cdn', 'https://cdn.espn.com/core/nfl/injuries?xhr=1'),
                  ('news', 'https://site.api.espn.com/apis/site/v2/sports/football/nfl/news?limit=100')):
    try:
        b = get(url); save(f'logs/espn/{name}_{stamp}.json.gz', b); log['ok'].append(f'{name} {len(b)}')
    except Exception as e: log['err'].append(f'{name}: {e}')
if now.hour in (14, 15) or os.environ.get('FORCE_SLEEPER'):
    try:
        b = get('https://api.sleeper.app/v1/players/nfl'); d = json.loads(b)
        slim = {k: {x: v.get(x) for x in ('full_name', 'team', 'position', 'injury_status', 'injury_body_part', 'injury_start_date', 'practice_participation', 'news_updated', 'gsis_id')}
                for k, v in d.items() if v.get('team') and v.get('position') in ('QB', 'RB', 'WR', 'TE', 'K')}
        save(f'logs/sleeper/{stamp}.json.gz', json.dumps(slim).encode()); log['ok'].append(f'sleeper {len(slim)}')
    except Exception as e: log['err'].append(f'sleeper: {e}')
os.makedirs('logs', exist_ok=True)
with open('logs/runs.jsonl', 'a') as f: f.write(json.dumps(log) + '\n')
print(log)
