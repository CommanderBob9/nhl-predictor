from datetime import date

import pytest

from fakes import FakeSchedule, raw_game
from nhlpred.db import connect
from nhlpred.ingest import current_season_start_year, pull_season, run


@pytest.mark.parametrize("today, start_year", [
    (date(2026, 7, 31), 2025),    # the summer still belongs to the season that just ended
    (date(2026, 8, 1), 2026),     # from August the new season is "current"
    (date(2026, 11, 15), 2026),
    (date(2027, 1, 15), 2026),    # January is the same season as the October before it
])
def test_current_season_start_year(today, start_year):
    assert current_season_start_year(today) == start_year


def one_game_calendar():
    return {date(2025, 10, 8): [
        raw_game(2025020001, 20252026, "2025-10-08T23:00:00Z", "TOR", "MTL", "OFF", (3, 2))]}


def test_pull_season_saves_what_it_fetched():
    conn = connect(":memory:")
    games = pull_season(conn, FakeSchedule(one_game_calendar()), 2025, today=date(2026, 11, 15))

    assert [game.game_id for game in games] == [2025020001]
    assert conn.execute("SELECT COUNT(*) FROM completed_games").fetchone()[0] == 1


def test_a_season_with_no_games_is_an_error_not_a_quiet_success():
    conn = connect(":memory:")
    with pytest.raises(RuntimeError, match="no games for the season starting in 2025"):
        pull_season(conn, FakeSchedule({}), 2025, today=date(2026, 11, 15))


def test_run_accepts_a_fake_client_and_writes_the_database(tmp_path, capsys):
    db_path = tmp_path / "nhl.db"
    total = run(2025, 2025, db_path, client=FakeSchedule(one_game_calendar()))

    assert total == 1
    assert "2025-26:     1 regular season" in capsys.readouterr().out
    conn = connect(db_path)
    assert conn.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 1
    conn.close()
