"""Turning raw NHL API schedule responses into clean Game records."""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Protocol

REGULAR_SEASON = 2
PLAYOFFS = 3
KEPT_GAME_TYPES = {REGULAR_SEASON, PLAYOFFS}
FINAL_STATES = {"OFF", "FINAL"}


@dataclass(frozen=True)
class Game:
    game_id: int
    season: int
    game_type: int
    game_date: str
    start_time_utc: str | None
    home_team: str
    away_team: str
    home_team_id: int | None
    away_team_id: int | None
    home_score: int | None
    away_score: int | None
    game_state: str | None
    schedule_state: str | None
    last_period_type: str | None
    neutral_site: bool
    venue: str | None


def season_id(start_year: int) -> int:
    """Convert season's start year into NHL API format 2025 -> 20252026"""
    return int(f"{start_year}{start_year + 1}")


def parse_game(raw: dict, listed_date: str) -> Game | None:
    """Convert one game object from the API into a Game, or None to skip it.
    
    'listed_date' is the gameWeek date the game appears under. Using instead of UTC,
    which would date late games (ex 10pm) as the next day, throwing off rest-day features.
    """
    if raw.get("gameType") not in KEPT_GAME_TYPES:
        return None

    home, away = raw["homeTeam"], raw["awayTeam"]
    state = raw.get("gameState")
    is_final = state in FINAL_STATES

    return Game(
        game_id=raw["id"],
        season=raw["season"],
        game_type=raw["gameType"],
        game_date=listed_date,
        start_time_utc=raw.get("startTimeUTC"),
        home_team=home["abbrev"],
        away_team=away["abbrev"],
        home_team_id=home.get("id"),
        away_team_id=away.get("id"),
        # Live games have partial scores; only trust scores once final.
        home_score=home.get("score") if is_final else None,
        away_score=away.get("score") if is_final else None,
        game_state=state,
        schedule_state=raw.get("gameScheduleState"),
        last_period_type=(raw.get("gameOutcome") or {}).get("lastPeriodType"),
        neutral_site=bool(raw.get("neutralSite", False)),
        venue=(raw.get("venue") or {}).get("default"),
    )


class ScheduleSource(Protocol):
    def schedule_week(self, start: date) -> dict: ...


def fetch_season(
        client: ScheduleSource, start_year: int, today: date | None = None
) -> list[Game]:
    """All regular season and playoff games for one season.

    Walks the league schedule one week at a time from Sept 1 until the API
    starts returning the next season's games. Starting early and filtering
    by season id handles odd seasons like 2020-21, beginning in January.
    """
    target = season_id(start_year)
    today = today or date.today()
    cursor = date(start_year, 9, 1)
    hard_stop = date(start_year + 1, 10, 31)
    found: dict[int, Game] = {}

    while cursor <= hard_stop:
        payload = client.schedule_week(cursor)
        if cursor > today and _nothing_scheduled_after(payload):
            break # reached the end of the published schedule
        seasons_seen: set[int] = set()

        for day in payload.get("gameWeek") or []:
            for raw in day.get("games") or []:
                seasons_seen.add(raw.get("season"))
                if raw.get("season") != target:
                    continue
                game = parse_game(raw, day["date"])
                if game is not None:
                    found[game.game_id] = game

        if seasons_seen and min(seasons_seen) > target:
            break
        cursor = next_cursor(cursor, payload)

    return sorted(found.values(), key=lambda g: (g.game_date, g.game_id))


def _nothing_scheduled_after(payload: dict) -> bool:
    week = payload.get("gameWeek") or []
    week_is_empty = not any(day.get("games") for day in week)
    no_later_weeks = not payload.get("nextStartDate")
    return week_is_empty and no_later_weeks


def next_cursor(cursor: date, payload: dict) -> date:
    """Where to start the next weekly request without ever skipping a day.
    
    If the week had games, continue from the day after the last listed date.
    If it was empty (off-season, break), jump to nextStartDate.
    """
    week = payload.get("gameWeek") or []
    had_games = any(day.get("games") for day in week)

    if had_games:
        last_listed = max(date.fromisoformat(day["date"]) for day in week)
        candidate = last_listed + timedelta(days=1)
    elif payload.get("nextStartDate"):
        candidate = date.fromisoformat(payload["nextStartDate"])
    else:
        candidate = cursor + timedelta(days=7)
    return max(candidate, cursor + timedelta(days=1))