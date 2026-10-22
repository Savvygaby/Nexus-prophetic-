"""ESPN NBA box scores for given dates -> nba_results.csv (player, team, min, pts, reb, ast, 3pm, game)."""
import json, urllib.request, csv, sys
H = {'User-Agent': 'Mozilla/5.0'}
dates = sys.argv[1:] or ['20261021']
rows = []
for d in dates:
    sb = json.loads(urllib.request.urlopen(urllib.request.Request(f'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={d}', headers=H), timeout=30).read())
    for ev in sb.get('events', []):
        s = json.loads(urllib.request.urlopen(urllib.request.Request(f'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event={ev["id"]}', headers=H), timeout=30).read())
        comp = ev['competitions'][0]; tm = {c['team']['abbreviation']: c.get('score') for c in comp['competitors']}
        for t in s.get('boxscore', {}).get('players', []):
            ab = t['team']['abbreviation']
            for st in t.get('statistics', []):
                keys = st.get('keys') or st.get('names') or []
                for a in st.get('athletes', []):
                    v = dict(zip(keys, a.get('stats', [])))
                    rows.append(dict(date=d, game=ev.get('shortName'), team=ab, player=a['athlete']['displayName'], dnp=a.get('didNotPlay', False),
                                     min=v.get('minutes'), pts=v.get('points'), reb=v.get('rebounds'), ast=v.get('assists'),
                                     fg3=v.get('threePointFieldGoalsMade-threePointFieldGoalsAttempted'), score=json.dumps(tm)))
with open('nba_results.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print(len(rows))
