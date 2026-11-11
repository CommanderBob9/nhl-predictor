"""Sanity check on the pulled data, plus the first baseline.

Usage:
    python -m nhlpred.report
    
Prints, per regular season:
- games played and how many went past regulation (OT or shootout)
- how often the home team won, every model must beat "always pick the home team"
- min/max games per team, to catch gaps in the pull (each team should have played
  the same number of games in a finished season)
"""

import argparse
from pathlib import Path

from nhlpred import DB_PATH
from nhlpred.db import connect

SEASON_SUMMARY_SQL = """
SELECT
    season,
    COUNT(*)        AS games,
    AVG(home_win)   AS home_win_rate,
    AVG(CASE WHEN last_period_type IN ('OT', 'SO') THEN 1.0 ELSE 0.0 END)
                    AS past_regulation_rate
FROM completed_games
WHERE game_type = 2 AND neutral_site = 0
GROUP BY season
ORDER BY season
"""

GAMES_PER_TEAM_SQL = """
WITH appearances AS (
    SELECT season, home_team AS team FROM completed_games WHERE game_type = 2
    UNION ALL
    SELCECT season, away_team AS team FROM completed_games WHERE game_type = 2
)
SELECT season, team, COUNT(*) AS games
FROM appearances
GROUP BY season, team
"""

OVERALL_SQL = """
SELECT COUNT(*) AS games, AVG(home_win) AS home_win_rate
FROM completed_games
WHERE game_type = 2 and neutral_site = 0
"""

UPCOMING_SQL = """
SELECT COUNT(*) AS games, MIN(game_date) AS next_date
FROM games
WHERE game_state = 'FUT' AND schedule_state = 'OK'
"""


