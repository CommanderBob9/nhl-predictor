from dataclasses import replace

import pytest

from nhlpred.db import connect, upsert_games
from nhlpred.games import Game
from nhlpred.report import SEASON_SUMMARY_SQL, main

FINAL = Game(
    game_id=1, season=20252026, game_type=2, game_date="2025-10-15", start_time_utc="2025-10-15T23:00:00Z",
    home_team="TOR", away_team="MTL", home_team_id=10, away_team_id=8, home_score=3, away_score=2,
    game_state="OFF", schedule_state="OK", last_period_type="OT", neutral_site=False, venue="Scotiabank Arena",
)


def test_the_season_summary_counts_only_regular_season_games_at_a_home_rink():
    conn = connect(":memory:")
    upsert_games(conn, [
        FINAL,
        replace(FINAL, game_id=2, neutral_site=True),     # neutral site: left out
        replace(FINAL, game_id=3, game_type=3),           # playoff: left out
    ])
    (row,) = conn.execute(SEASON_SUMMARY_SQL).fetchall()

    assert (row["games"], row["home_win_rate"], row["past_regulation_rate"]) == (1, 1.0, 1.0)


def test_main_prints_the_summary_and_labels_the_home_rate_as_descriptive(tmp_path, capsys):
    db_path = tmp_path / "nhl.db"
    conn = connect(db_path)
    upsert_games(conn, [FINAL])
    conn.close()

    main(["--db", str(db_path)])
    out = capsys.readouterr().out

    assert "2025-26" in out
    assert "not the evaluation baseline" in out


def test_a_database_path_that_does_not_exist_is_an_error_and_creates_nothing(tmp_path):
    missing = tmp_path / "typo" / "nhl.db"
    with pytest.raises(SystemExit):
        main(["--db", str(missing)])
    assert not missing.exists()
