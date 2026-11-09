import json
from datetime import date, timedelta
from pathlib import Path

from nhlpred.games import fetch_season, next_cursor, parse_game, season_id

FIXTURE = Path(__file__).parent / "fixtures" / "schedule_week.json"


def load_week() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def games_by_id(payload: dict) -> dict:
    return {
        raw["id"]: (raw, day["date"])
        for day in payload["gameWeek"]
        for raw in day["games"]
    }


# --- parse_game -------------------------------------------------------------

def test_parses_a_finished_regulation_game():
    raw, listed = games_by_id(load_week())[2025020057]
    game = parse_game(raw, listed)

    assert game.game_id == 2025020057
    assert game.season == 20252026
    assert game.game_date == "2025-10-15"
    assert (game.home_team, game.away_team) == ("BUF", "OTT")
    assert (game.home_score, game.away_score) == (8, 4)
    assert game.last_period_type == "REG"
    assert game.venue == "KeyBank Center"
    assert game.neutral_site is False


def test_late_game_keeps_its_listed_date_not_the_utc_date():
    # 7 pm Mountain in Edmonton is 02:00 UTC the next day. Dating it by UTC
    # would turn back-to-backs into rest days and shift the no-lookahead cutoff.
    raw, listed = games_by_id(load_week())[2025020059]
    assert raw["startTimeUTC"].startswith("2025-10-16")  # fixture really crosses midnight UTC
    assert parse_game(raw, listed).game_date == "2025-10-15"


def test_overtime_and_shootout_are_recorded():
    week = games_by_id(load_week())
    assert parse_game(*week[2025020058]).last_period_type == "OT"
    shootout = parse_game(*week[2025020059])
    assert shootout.last_period_type == "SO"
    assert shootout.game_state == "FINAL"
    assert shootout.away_score > shootout.home_score # away team won the shootout


def test_live_game_scores_are_not_trusted():
    raw, listed = games_by_id(load_week())[202502006]
    game = parse_game(raw, listed)
    assert game.game_state == "LIVE"
    assert game.home_score is None and game.away_score is None


def test_preseason_games_are_skipped():
    raw, listed = games_by_id(load_week())[2025020099]
    assert parse_game(raw, listed) is None


# --- next_cursor --------------------------------------------------------------

def test_next_cursor_never_skips_a_day_with_games():
    # The API returned only 6 days but says the next week starts 2 days later.
    payload = {
        "nextStartDate": "2026-11-12",
        "gameWeek": [
            {"date": f"2026-11-{d:02d}", "games": [{"id": d}]} for d in range (5, 11)
        ]
    }
    assert next_cursor(date(2026, 11, 5), payload) == date(2026, 11, 11)


def test_next_cursor_jumps_over_an_empty_week():



# --- fetch_season -------------------------------------------------------------
