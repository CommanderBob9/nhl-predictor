from datetime import date

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