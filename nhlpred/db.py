"""SQLite storage for games.

One row per game, keyed by the NHL's game id. Writes are upserts, so running
the pull twice never creates duplicates, and a game that was 'FUT' (future)
yesterday gets its final score filled in today.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from nhlpred.games import Game

SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
    game_id          INTEGER PRIMARY KEY,
    season           INTEGER NOT NULL,  -- e.g. 20252026
    game_type        INTEGER NOT NULL,  -- 2 = regular season, 3 = playoffs
    game_date        TEXT    NOT NULL,  -- league (Eastern) calendar date, YYYY-MM-DD
    start_time_utc   TEXT,
    home_team        TEXT    NOT NULL,  -- three-letter abbreviation, e.g. TOR
    away_team        TEXT    NOT NULL,
    home_team_id     INTEGER,
    away_team_id     INTEGER,
    home_score       INTEGER,           -- NULL until the game is final
    away_score       INTEGER,
    game_state       TEXT,              -- FUT, PRE, LIVE, CRIT, FINAL, OFF
    schedule_state   TEXT,              -- OK, PPD (postponed), CNCL (cancelled)
    last_period_type TEXT,              -- REG, OT or SO once final
    neutral_site     INTEGER NOT NULL DEFAULT 0,
    venue            TEXT,
    updated_at       TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_games_date   ON games (game_date);
CREATE INDEX IF NOT EXISTS idx_games_season ON games (season, game_type);

-- Finished games only
-- Shootout winners are credited one goal in the final score, so
-- home_score > away_score is the winner in every case
CREATE VIEW IF NOT EXISTS completed_games AS
SELECT
    *,
    CASE WHEN home_score > away_score THEN 1 ELSE 0 END AS home_win
FROM games
WHERE game_state IN ('OFF', 'FINAL')
  AND home_score IS NOT NULL
  AND away_score IS NOT NULL;
"""

COLUMNS = (
    "game_id", "season", "game_type", "game_date", "start_time_utc",
    "home_team", "away_team", "home_team_id", "away_team_id",
    "home_score", "away_score", "game_state", "schedule_state",
    "last_period_type", "neutral_site", "venue", "updated_at",
)

UPSERT_SQL = f"""
INSERT INTO games ({", ".join(COLUMNS)})
VALUES ({", ".join("?" for _ in COLUMNS)})
ON CONFLICT (game_id) DO UPDATE SET
    {", ".join(f"{c} = excluded.{c}" for c in COLUMNS if c != "game_id")}
"""


# Opens the database return a connection object
def connect(db_path: Path | str) -> sqlite3.Connection:
    if str(db_path) != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


# Writes each game into database
def upsert_games(conn: sqlite3.Connection, games: Iterable[Game]) -> int:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows = [
        (
            g.game_id, g.season, g.game_type, g.game_date, g.start_time_utc,
            g.home_team, g.away_team, g.home_team_id, g.away_team_id,
            g.home_score, g.away_score, g.game_state, g.schedule_state,
            g.last_period_type, int(g.neutral_site), g.venue, now,
        )
        for g in games
    ]
    with conn: # one transaction, all changes made or no changes made
        conn.executemany(UPSERT_SQL, rows)
    return len(rows)
