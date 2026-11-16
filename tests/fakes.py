"""Stand-ins for the network and the clock, shared by the ingest, daily-job and API tests."""

from datetime import date, datetime, timedelta, timezone


def raw_game(game_id, season, start_utc, home, away, state="FUT", score=None,
             game_type=2, neutral=False, schedule_state="OK"):
    """One game the way the schedule API lists it. `score` is (home, away) for a final game."""
    raw = {
        "id": game_id, "season": season, "gameType": game_type, "gameState": state,
        "gameScheduleState": schedule_state, "startTimeUTC": start_utc, "neutralSite": neutral,
        "homeTeam": {"abbrev": home}, "awayTeam": {"abbrev": away},
    }
    if score is not None:
        raw["homeTeam"]["score"], raw["awayTeam"]["score"] = score
        raw["gameOutcome"] = {"lastPeriodType": "REG"}
    return raw


class FakeSchedule:
    """Stands in for NHLClient: serves a fake league calendar from memory.

    `games_by_date` maps the Eastern calendar date a game is listed under to its games.
    """

    def __init__(self, games_by_date: dict[date, list[dict]]):
        self.games_by_date = games_by_date
        self.requested: list[date] = []

    def schedule_week(self, start: date) -> dict:
        self.requested.append(start)
        days = [start + timedelta(days=i) for i in range(7)]
        week = [{"date": d.isoformat(), "games": self.games_by_date.get(d, [])} for d in days]
        future = sorted(d for d in self.games_by_date if d > days[-1])
        return {"gameWeek": week, "nextStartDate": future[0].isoformat() if future else None}


def fixed_clock(year, month, day, hour, minute=0):
    """A clock that always says the same UTC time. Tests never read the real one."""
    moment = datetime(year, month, day, hour, minute, tzinfo=timezone.utc)
    return lambda: moment
