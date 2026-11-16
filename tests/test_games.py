import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from nhlpred.games import fetch_season, next_cursor, parse_game, season_id, season_label

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
    raw, listed = games_by_id(load_week())[2025020060]
    game = parse_game(raw, listed)
    assert game.game_state == "LIVE"
    assert game.home_score is None and game.away_score is None


def test_preseason_games_are_skipped():
    raw, listed = games_by_id(load_week())[2025010099]
    assert parse_game(raw, listed) is None


# --- next_cursor --------------------------------------------------------------

def test_next_cursor_never_skips_a_day_with_games():
    # The API returned only 6 days but says the next week starts 2 days later.
    payload = {
        "nextStartDate": "2026-11-12",
        "gameWeek": [
            {"date": f"2026-11-{d:02d}", "games": [{"id": d}]} for d in range(5, 11)
        ]
    }
    assert next_cursor(date(2026, 11, 5), payload) == date(2026, 11, 11)


def test_next_cursor_jumps_over_an_empty_week():
    payload = {"nextStartDate": "2026-02-25", "gameWeek": [{"date": "2026-02-10", "games": []}]}
    assert next_cursor(date(2026, 2, 10), payload) == date(2026, 2, 25)


def test_next_cursor_always_moves_forward():
    payload = {"nextStartDate": "2020-01-01", "gameWeek": []}  # nonsense date in the past
    assert next_cursor(date(2026, 1, 1), payload) == date(2026, 1, 2)


# --- fetch_season -------------------------------------------------------------

def make_game(game_id, season, game_type=2, state="OFF", home="TOR", away="MTL"):
    raw = {
        "id": game_id, "season": season, "gameType": game_type, "gameState": state,
        "gameScheduleState": "OK", "homeTeam": {"abbrev": home}, "awayTeam": {"abbrev": away},
    }
    if state == "OFF":
        raw["homeTeam"]["score"], raw["awayTeam"]["score"] = 3, 2
        raw["gameOutcome"] = {"lastPeriodType": "REG"}
    return raw


class FakeSchedule:
    """Stands in for NHLClient: serves a fake league calendar from memory."""

    def __init__(self, games_by_date: dict[date, list[dict]]):
        self.games_by_date = games_by_date
        self.requested: list[date] = []

    def schedule_week(self, start: date) -> dict:
        self.requested.append(start)
        days = [start + timedelta(days=i) for i in range(7)]
        week = [
            {"date": d.isoformat(), "games": self.games_by_date.get(d, [])} for d in days
        ]
        future = sorted(d for d in self.games_by_date if d > days[-1])
        return {
            "gameWeek": week,
            "nextStartDate": future[0].isoformat() if future else None,
        }


def test_fetch_season_collects_only_that_season_and_stops_at_the_next():
    calendar = {
        date(2025, 9, 20): [make_game(2025010001, 20252026, game_type=1)],  # preseason
        date(2025, 10, 8): [make_game(2025020001, 20252026)],
        date(2026, 1, 15): [make_game(2025020500, 20252026)],
        date(2026, 5, 1): [make_game(2025030111, 20252026, game_type=3)],    # playoffs
        date(2026, 9, 25): [make_game(2026010001, 20262027, game_type=1)],  # next season
        date(2026, 10, 10): [make_game(2026020001, 20262027)],
    }
    client = FakeSchedule(calendar)

    games = fetch_season(client, 2025)

    assert [g.game_id for g in games] == [2025020001, 2025020500, 2025030111]
    assert all(g.season == 20252026 for g in games)
    # stopped as soon as next season showed up, didn't walk to the hard stop
    assert max(client.requested) < date(2026, 10, 1)


def test_fetch_season_skips_last_seasons_games_in_a_late_start_year():
    # 2020-21 started in January while 2019-20 playoffs ran into September.
    calendar = {
        date(2020, 9, 20): [make_game(2019030415, 20192020, game_type=3)],
        date(2021, 1, 13): [make_game(2020020001, 20202021)],
        date(2021, 9, 26): [make_game(2021010001, 20212022, game_type=1)],
    }
    games = fetch_season(FakeSchedule(calendar), 2020)
    assert [g.game_id for g in games] == [2020020001]


def test_season_in_progress_stops_at_end_of_published_schedule():
    # Playoffs aren't scheduled yet, so nothing exists after mid-April.
    calendar = {
        date(2026, 10, 10): [make_game(2026020001, 20262027)],
        date(2026, 11, 20): [make_game(2026020300, 20262027, state="FUT")],
        date(2027, 4, 15): [make_game(2026021344, 20262027, state="FUT")],
    }
    client = FakeSchedule(calendar)
    games = fetch_season(client, 2026, today=date(2026, 10, 29))
    assert len(games) == 3
    assert max(client.requested) < date(2027, 5, 1)  # didn't walk on to Oct 2027


def test_rescheduled_game_keeps_its_latest_listing():
    postponed = make_game(2025020300, 20252026, state="FUT")
    postponed["gameScheduleState"] = "PPD"
    calendar = {
        date(2025, 12, 1): [postponed],
        date(2026, 2, 20): [make_game(2025020300, 20252026, state="OFF")],
        date(2026, 9, 25): [make_game(2026010001, 20262027, game_type=1)],
    }
    (game,) = fetch_season(FakeSchedule(calendar), 2025)
    assert game.game_date == "2026-02-20"
    assert game.game_state == "OFF"
    assert game.home_score == 3


def test_a_final_listing_is_not_replaced_by_a_later_listing_without_a_score():
    # The mirror image of the test above: the final listing comes first, and a stale
    # unplayed listing of the same game follows. The final score must survive.
    calendar = {
        date(2025, 11, 20): [make_game(2025020300, 20252026, state="OFF")],
        date(2025, 12, 1): [make_game(2025020300, 20252026, state="FUT")],
        date(2026, 9, 25): [make_game(2026010001, 20262027, game_type=1)],
    }
    (game,) = fetch_season(FakeSchedule(calendar), 2025)
    assert game.game_date == "2025-11-20"
    assert game.home_score == 3


def test_a_listing_without_a_season_does_not_stop_the_walk():
    no_season = make_game(2025020002, 20252026)
    del no_season["season"]
    calendar = {
        date(2025, 10, 8): [make_game(2025020001, 20252026), no_season],
        date(2026, 9, 25): [make_game(2026010001, 20262027, game_type=1)],
    }
    games = fetch_season(FakeSchedule(calendar), 2025)
    assert [g.game_id for g in games] == [2025020001]


def test_a_malformed_game_fails_with_the_game_id_and_date():
    broken = make_game(2025020001, 20252026)
    del broken["homeTeam"]["abbrev"]
    calendar = {date(2025, 10, 8): [broken]}
    with pytest.raises(ValueError, match="game 2025020001 on 2025-10-08 has no 'abbrev'"):
        fetch_season(FakeSchedule(calendar), 2025)


def test_neutral_site_is_read_for_a_regular_season_game():
    raw = make_game(2025020400, 20252026)
    raw["neutralSite"] = True
    assert parse_game(raw, "2025-11-14").neutral_site is True


def test_season_label_is_the_inverse_of_season_id():
    assert season_label(season_id(2025)) == "2025-26"