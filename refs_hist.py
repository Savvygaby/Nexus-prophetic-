"""Fetch ESPN game summaries for NBA game ids -> officials + team fouls/FTA. Writes refs_hist.csv"""
import json, urllib.request, csv, concurrent.futures as cf, time
ids = [l.strip() for l in open('nba_game_ids.txt') if l.strip()]
H = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36'}
def one(g):
    for t in range(3):
        try:
            j = json.loads(urllib.request.urlopen(urllib.request.Request(f'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={g}', headers=H), timeout=20).read())
            offs = [o.get('displayName') or o.get('fullName') for o in j.get('gameInfo', {}).get('officials', [])]
            st = {}
            for tm in j.get('boxscore', {}).get('teams', []):
                ha = tm.get('homeAway');
                for s in tm.get('statistics', []):
                    if s.get('name') in ('fouls', 'totalTechnicalFouls', 'freeThrowsMade-freeThrowsAttempted', 'flagrantFouls'):
                        st[f"{ha}_{s['name']}"] = s.get('displayValue')
            return dict(game_id=g, officials='|'.join([o for o in offs if o]), **st)
        except Exception as e:
            time.sleep(1 + t)
    return dict(game_id=g, officials='')
rows = []
with cf.ThreadPoolExecutor(8) as ex:
    for r in ex.map(one, ids): rows.append(r)
keys = sorted({k for r in rows for k in r})
with open('refs_hist.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(rows)
print('games', len(rows), 'with officials', sum(1 for r in rows if r.get('officials')))
