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
    SELECT season, away_team AS team FROM completed_games WHERE game_type = 2
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


def fmt_season(season: int) -> str:
    s = str(season)
    return f"{s[:4]}-{s[6:]}"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Sanity-check the games database.")
    parser.add_argument("--db", type=Path, default=DB_PATH)
    args = parser.parse_args(argv)

    conn = connect(args.db)
    #Check how many games each team played in a season (should be 82)
    per_team: dict[int: list[int]] = {}
    for row in conn.execute(GAMES_PER_TEAM_SQL):
        per_team.setdefault(row["season"], []).append(row["games"])

    #Get season summary
    rows = conn.execute(SEASON_SUMMARY_SQL).fetchall()
    if not rows:
        print("No completed games yet. Run 'python -m nhlpred.ingest' first.")
        return

    #Print season summary
    print(f"{'season':<9}{'games':>7}{'home win':>10}{'OT/SO':>8}{'games/team':>13}")
    for row in rows:
        counts = per_team.get(row['season'], [0])
        spread = f"{min(counts)}-{max(counts)}" if min(counts) != max(counts) else str(min(counts))
        print(
            f"{fmt_season(row['season']):<9}"
            f"{row['games']:>7,}"
            f"{row['home_win_rate']:>10.1%}"
            f"{row['past_regulation_rate']:>8.1%}"
            f"{spread:>13}"
        )


    overall = conn.execute(OVERALL_SQL).fetchone()
    print(
        f"\nBaseline (always pick the home team): {overall['home_win_rate']:.1%} "
        f"accuracy over {overall['games']:,} regular-season games"
    )

    upcoming = conn.execute(UPCOMING_SQL).fetchone()
    if upcoming['games']:
        print(f"Upcoming scheduled games: {upcoming['games']:,} (next on {upcoming['next_date']})")
    print(
        "\nNote: games per team should be 82 for finished seasons, except"
        " 2019-20 (cut short by COVID) . It also varies in the season in progress."
    )
    conn.close()


if __name__ == "__main__":
    main()