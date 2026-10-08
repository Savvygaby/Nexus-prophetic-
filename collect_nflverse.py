"""One-time pull of nflverse play-by-play 2018-2024 (trimmed columns) + officials, for player/coach/referee agents. Keyless."""
import pandas as pd, os, urllib.request, io
os.makedirs('nflverse', exist_ok=True)
COLS = ['game_id', 'play_id', 'season', 'week', 'season_type', 'home_team', 'away_team', 'posteam', 'defteam', 'play_type', 'pass_attempt', 'rush_attempt', 'complete_pass',
        'passer_player_id', 'passer_player_name', 'receiver_player_id', 'receiver_player_name', 'rusher_player_id', 'rusher_player_name', 'yards_gained', 'air_yards',
        'yards_after_catch', 'sack', 'qb_hit', 'interception', 'qb_scramble', 'penalty', 'penalty_type', 'penalty_yards', 'penalty_team', 'down', 'ydstogo', 'yardline_100',
        'score_differential', 'qtr', 'game_seconds_remaining', 'wp', 'epa', 'pass_oe', 'xpass', 'shotgun', 'no_huddle', 'touchdown', 'pass_touchdown', 'rush_touchdown',
        'cpoe', 'xyac_mean_yardage', 'pass_location', 'pass_length', 'run_location', 'run_gap']
for yr in range(2018, 2025):
    u = f'https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{yr}.parquet'
    try:
        d = pd.read_parquet(io.BytesIO(urllib.request.urlopen(u, timeout=120).read()))
        d[[c for c in COLS if c in d.columns]].to_parquet(f'nflverse/pbp_{yr}.parquet', index=False, compression='zstd'); print(yr, len(d))
    except Exception as e: print(yr, 'ERR', e)
for name, u in [('officials', 'https://github.com/nflverse/nflverse-data/releases/download/officials/officials.parquet'),
                ('participation_2026', 'https://github.com/nflverse/nflverse-data/releases/download/pbp_participation/pbp_participation_2026.parquet'),
                ('ftn_2024', 'https://github.com/nflverse/nflverse-data/releases/download/ftn_charting/ftn_charting_2024.parquet'),
                ('ftn_2023', 'https://github.com/nflverse/nflverse-data/releases/download/ftn_charting/ftn_charting_2023.parquet'),
                ('pfr_def_2024', 'https://github.com/nflverse/nflverse-data/releases/download/pfr_advstats/advstats_week_def_2024.parquet'),
                ('pfr_def_2023', 'https://github.com/nflverse/nflverse-data/releases/download/pfr_advstats/advstats_week_def_2023.parquet'),
                ('pfr_pass_2024', 'https://github.com/nflverse/nflverse-data/releases/download/pfr_advstats/advstats_week_pass_2024.parquet'),
                ('pfr_pass_2023', 'https://github.com/nflverse/nflverse-data/releases/download/pfr_advstats/advstats_week_pass_2023.parquet')]:
    try:
        d = pd.read_parquet(io.BytesIO(urllib.request.urlopen(u, timeout=120).read())); d.to_parquet(f'nflverse/{name}.parquet', index=False, compression='zstd'); print(name, len(d))
    except Exception as e: print(name, 'ERR', e)
