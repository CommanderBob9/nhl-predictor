from dataclasses import replace

import pytest

from nhlpred.db import connect, upsert_games
from nhlpred.games import Game


@pytest.fixture
def conn():
    connection = connect(":memory:")
    yield connection
    connection.close()


def future_game(**overrides) -> Game:
    base = Game(
        game_id=2025020061, season=20252026, game_type=2, game_date="2025-10-16",
        start_time_utc="2025-10-17T00:00:00Z", home_team="WPG", away_team="VAN",
        home_team_id=52, away_team_id=23, home_score=None, away_score=None,
        game_state="FUT", schedule_state="OK", last_period_type=None,
        neutral_site=False, venue="Canada Life Centre",
    )
    return replace(base, **overrides)


def test_upsert_is_idempotent(conn):
    upsert_games(conn, [future_game()])
    upsert_games(conn, [future_game()])
    assert conn.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 1


def test_upsert_fills_in_the_final_score(conn):
    upsert_games(conn, [future_game()])
    assert conn.execute("SELECT COUNT(*) FROM completed_games").fetchone()[0] == 0
    upsert_games(conn, [future_game(game_state="OFF", home_score=2, away_score=5, last_period_type="REG")])

    row = conn.execute("SELECT * FROM completed_games").fetchone()
    assert (row["home_score"], row["away_score"]) == (2, 5)
    assert row["home_win"] == 0


def test_completed_games_labels_home_wins(conn):
    upsert_games(conn, [
        future_game(game_id=1, game_state="OFF", home_score=4, away_score=1),
        future_game(game_id=2, game_state="FINAL", home_score=2, away_score=3),
        future_game(game_id=3),  # not played yet, excluded
    ])
    labels = dict(conn.execute("SELECT game_id, home_win FROM completed_games"))
    assert labels == {1: 1, 2: 0}