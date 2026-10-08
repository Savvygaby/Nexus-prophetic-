"""Full nflverse pull for the digital-stadium agents (keyless). Writes nflverse/*.parquet (zstd), pushed to the 'data' branch."""
import pandas as pd, os, urllib.request, io, json
os.makedirs('nflverse', exist_ok=True)
R = 'https://github.com/nflverse/nflverse-data/releases/download/'
PBP_COLS = ['game_id', 'play_id', 'season', 'week', 'season_type', 'game_date', 'home_team', 'away_team', 'posteam', 'defteam', 'play_type', 'pass_attempt', 'rush_attempt',
            'complete_pass', 'incomplete_pass', 'passer_player_id', 'passer_player_name', 'receiver_player_id', 'receiver_player_name', 'rusher_player_id', 'rusher_player_name',
            'yards_gained', 'air_yards', 'yards_after_catch', 'sack', 'qb_hit', 'interception', 'fumble_lost', 'qb_scramble', 'penalty', 'penalty_type', 'penalty_yards',
            'penalty_team', 'down', 'ydstogo', 'yardline_100', 'score_differential', 'qtr', 'game_seconds_remaining', 'half_seconds_remaining', 'wp', 'vegas_wp', 'epa',
            'success', 'pass_oe', 'xpass', 'shotgun', 'no_huddle', 'touchdown', 'pass_touchdown', 'rush_touchdown', 'td_player_id', 'cpoe', 'xyac_mean_yardage', 'pass_location',
            'pass_length', 'run_location', 'run_gap', 'field_goal_result', 'kick_distance', 'kicker_player_id', 'kicker_player_name', 'extra_point_result',
            'two_point_conv_result', 'punt_returner_player_id', 'kickoff_returner_player_id', 'return_yards', 'fourth_down_converted', 'fourth_down_failed', 'timeout',
            'roof', 'surface', 'temp', 'wind', 'stadium', 'spread_line', 'total_line', 'home_coach', 'away_coach', 'drive', 'fixed_drive_result', 'qb_dropback', 'first_down']
log = {}
def get(u):
    return pd.read_parquet(io.BytesIO(urllib.request.urlopen(u, timeout=180).read()))
def save(name, d):
    d.to_parquet(f'nflverse/{name}.parquet', index=False, compression='zstd'); log[name] = len(d); print(name, len(d), flush=True)
for yr in range(1999, 2025):
    try: d = get(f'{R}pbp/play_by_play_{yr}.parquet'); save(f'pbp_{yr}', d[[c for c in PBP_COLS if c in d.columns]])
    except Exception as e: log[f'pbp_{yr}'] = f'ERR {e}'
for yr in range(2016, 2026):
    try: save(f'participation_{yr}', get(f'{R}pbp_participation/pbp_participation_{yr}.parquet'))
    except Exception as e: log[f'participation_{yr}'] = f'ERR {e}'
for yr in range(2022, 2027):
    try: save(f'ftn_{yr}', get(f'{R}ftn_charting/ftn_charting_{yr}.parquet'))
    except Exception as e: log[f'ftn_{yr}'] = f'ERR {e}'
for k in ('passing', 'receiving', 'rushing'):
    try: save(f'ngs_{k}', get(f'{R}nextgen_stats/ngs_{k}.parquet'))
    except Exception as e: log[f'ngs_{k}'] = f'ERR {e}'
for yr in range(2018, 2027):
    for k in ('def', 'pass', 'rec', 'rush'):
        try: save(f'pfr_{k}_{yr}', get(f'{R}pfr_advstats/advstats_week_{k}_{yr}.parquet'))
        except Exception as e: log[f'pfr_{k}_{yr}'] = f'ERR {e}'
for yr in range(2012, 2027):
    for k, path in (('snaps', f'snap_counts/snap_counts_{yr}.parquet'), ('injuries', f'injuries/injuries_{yr}.parquet'), ('depth', f'depth_charts/depth_charts_{yr}.parquet')):
        try: save(f'{k}_{yr}', get(R + path))
        except Exception as e: log[f'{k}_{yr}'] = f'ERR {e}'
for name, path in (('officials', 'officials/officials.parquet'), ('players', 'players/players.parquet'), ('rosters_weekly_2026', 'weekly_rosters/roster_weekly_2026.parquet'),
                   ('rosters_weekly_2025', 'weekly_rosters/roster_weekly_2025.parquet')):
    try: save(name, get(R + path))
    except Exception as e: log[name] = f'ERR {e}'
json.dump(log, open('nflverse/_log.json', 'w'), indent=1)
