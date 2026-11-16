from datetime import date

import pytest

from nhlpred.nhl_api import NHLClient


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


class CountingSession:
    """Records every URL requested instead of touching the network."""

    def __init__(self):
        self.urls = []

    def get(self, url, timeout):
        self.urls.append(url)
        return FakeResponse({"gameWeek": [], "nextStartDate": None})


def make_client(tmp_path, today):
    session = CountingSession()
    client = NHLClient(cache_dir=tmp_path, delay_seconds=0, session=session, today=today)
    return client, session


def test_requests_the_right_url(tmp_path):
    client, session = make_client(tmp_path, today=date(2026, 10, 29))
    client.schedule_week(date(2025, 10, 15))
    assert session.urls == ["https://api-web.nhle.com/v1/schedule/2025-10-15"]


def test_finished_weeks_are_served_from_cache(tmp_path):
    client, session = make_client(tmp_path, today=date(2026, 10, 29))
    client.schedule_week(date(2025, 10, 15))
    client.schedule_week(date(2025, 10, 15))
    assert len(session.urls) == 1
    assert (tmp_path / "schedule_2025-10-15.json").exists()


def test_recent_weeks_are_always_refetched(tmp_path):
    # This week isn't over yet, so it must never be cached.
    client, session = make_client(tmp_path, today=date(2026, 10, 29))
    client.schedule_week(date(2026, 10, 27))
    client.schedule_week(date(2026, 10, 27))
    assert len(session.urls) == 2
    assert not list(tmp_path.iterdir())


def test_a_week_is_cached_from_exactly_three_days_after_its_last_day(tmp_path):
    # The week starting Oct 20 ends Oct 26. Three days later is Oct 29.
    client, _ = make_client(tmp_path, today=date(2026, 10, 28))
    client.schedule_week(date(2026, 10, 20))
    assert not list(tmp_path.iterdir())          # two days after: not settled yet

    client, _ = make_client(tmp_path, today=date(2026, 10, 29))
    client.schedule_week(date(2026, 10, 20))
    assert [p.name for p in tmp_path.iterdir()] == ["schedule_2026-10-20.json"]


class UnexpectedBodySession:
    """An API that answers 200 with something that is not a schedule."""

    def get(self, url, timeout):
        return FakeResponse({"message": "schema changed"})


def test_an_unexpected_response_is_an_error_and_is_never_cached(tmp_path):
    client = NHLClient(cache_dir=tmp_path, delay_seconds=0, session=UnexpectedBodySession(),
                       today=date(2026, 10, 29))
    with pytest.raises(ValueError, match="unexpected schedule response"):
        client.schedule_week(date(2025, 10, 15))
    assert not list(tmp_path.iterdir())


class ErrorResponse:
    def raise_for_status(self):
        raise RuntimeError("503 from the API")


class FailingSession:
    def get(self, url, timeout):
        return ErrorResponse()


def test_an_http_error_is_passed_on_and_nothing_is_cached(tmp_path):
    client = NHLClient(cache_dir=tmp_path, delay_seconds=0, session=FailingSession(),
                       today=date(2026, 10, 29))
    with pytest.raises(RuntimeError, match="503"):
        client.schedule_week(date(2025, 10, 15))
    assert not list(tmp_path.iterdir())


def test_the_cache_write_leaves_no_temporary_file_behind(tmp_path):
    client, _ = make_client(tmp_path, today=date(2026, 10, 29))
    client.schedule_week(date(2025, 10, 15))
    assert [p.suffix for p in tmp_path.iterdir()] == [".json"]