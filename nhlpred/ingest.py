"""Pull NHL schedules and results into the local SQLite database.

Usage (from the project root):
    python -m nhlpred.ingest                # 2015-16 through the current season
    python -m nhlpred.ingest --first 2020   # 2020-21 through the current season
    python -m nhlpred.ingest --current      # just the season in progress (daily update)

Safe to re-run any time: finished weeks come from the local cache and every write is an upsert.
"""

import argparse
from collections import Counter
from datetime import date
from pathlib import Path

from nhlpred import DB_PATH, RAW_DIR
from nhlpred.db import connect, upsert_games
from nhlpred.games import PLAYOFFS, REGULAR_SEASON, fetch_season
from nhlpred.nhl_api import NHLClient

DEFAULT_FIRST_SEASON = 2015


def current_season_start_year(today: date | None = None) -> int:
    """Season start in the fall; in Oct 2026 the season is 2026-27,
    in March 2027 it's still 2026-27."""
    today = today or date.today()
    return today.year if today.month >= 8 else today.year - 1


def run(first: int, last: int, db_path: Path, use_cache: bool = True) -> int:
    client = NHLClient(cache_dir=RAW_DIR if use_cache else None)
    conn = connect(db_path)
    total = 0
    try:
        for start_year in range(first, last + 1):
            games = fetch_season(client, start_year)
            saved = upsert_games(conn, games)
            total += saved
            types = Counter(g.game_type for g in games)
            final = sum(g.home_score is not None for g in games)
            print(
                f"{start_year}-{str(start_year + 1)[2:]}:"
                f"{types[REGULAR_SEASON]:>5,} regular season, "
                f"{types[PLAYOFFS]:>3} playoff, "
                f"{final:>5,} final   ->   {saved:,} saved"
            )
    finally:
        conn.close()
    print(f"Done. {total:,} games written to {db_path}")
    return total


def main(argv: list[str] | None = None) -> None:
    current = current_season_start_year()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--first", type=int, default=DEFAULT_FIRST_SEASON,
                        help="first season's start year, e.g. 2015 for 2015-16")
    parser.add_argument("--last", type=int, default=current,
                        help="last season's start year (default: current season)")
    parser.add_argument("--current", action="store_true", 
                        help="only pull the season in progress")
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--no-cache", action="store_true", 
                        help="ignore cached raw responses and refetch everything")
    args = parser.parse_args(argv)

    first = current if args.current else args.first
    last = current if args.current else args.last
    if first > last:
        parser.error("--first must be <= --last")
    run(first, last, args.db, use_cache=not args.no_cache)    


if __name__ == "__main__":
    main()