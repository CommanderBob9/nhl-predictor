"""Thin client for the NHL's public web API (https://api-web.nhle.com).
   The API is free but unofficial so the client is written defensively:
   - every request has a timeout and retries temporary failures (429 / 5xx)
   - there's a short pause between calls so we don't overload the server
   - finished weeks are cached to disk as raw JSON so re-running the pull is fast
     and we keep an untouched copy of what the API returned
"""

import json
import time
from datetime import date, timedelta
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://api-web.nhle.com/v1"

# A week is cached once its last day is at least this many days in the past.
# Before that, it may include games that haven't been played or marked final yet.
SETTLED_AFTER_DAYS = 3


def make_session() -> requests.Session:
    """A requests session that retries transient errors with backoff."""
    
    retry = Retry(
        total=5,
        backoff_factor=1.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers["User-Agent"] = "nhl-predictor (personal research project)"
    return session


class NHLClient:
    """Fetches league schedule weeks, caching the ones that are finished"""
    def __init__(
        self,
        cache_dir: Path | None = None,
        delay_seconds: float = 0.3,
        session: requests.Session | None = None,
        today: date | None = None,
    ):
        self.cache_dir = cache_dir
        self.delay_seconds = delay_seconds
        self.session = session or make_session()
        self._today = today

    @property
    def today(self) -> date:
        return self._today or date.today()

    # Return true if week's last day is 3 or more days in the past
    def _is_settled(self, start: date) -> bool:
        last_day = start + timedelta(days=6)
        return last_day <= self.today - timedelta(days=SETTLED_AFTER_DAYS)

    # Define path for a week of data
    def _cache_path(self, start: date) -> Path | None:
        if self.cache_dir is None:
            return None
        return self.cache_dir / f"schedule_{start.isoformat()}.json"

    # Read data for one week and return as dictionary
    def _read_cache(self, start: date) -> dict | None:
        path = self._cache_path(start)
        if path is None or not path.exists() or not self._is_settled(start):
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    # Writes API dictionary into json
    def _write_cache(self, start: date, payload: dict) -> None:
        path = self._cache_path(start)
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")

    # Calls API and saves a week of data starting from start date
    def schedule_week(self, start: date) -> dict:
        """League wide schedule for the 7 days starting on 'start'
        
           Served from the cache if the week is settled and already saved,
           otherwise fetched and saved only if the week is settled.
           
           Response shape:
                {"nextStartDate": "2025-10-22", "previousStartDate": "...",
                 "gameWeek": [{"date": "2025-10-15", "numberOfGames": 4,
                               "games": [{...game...}, ...]}, ...]}    
        """
        cached = self._read_cache(start)
        if cached is not None:
            return cached

        url = f"{BASE_URL}/schedule/{start.isoformat()}"
        response = self.session.get(url, timeout=20)
        response.raise_for_status()
        payload = response.json()

        if self._is_settled(start):
            self._write_cache(start, payload)
        time.sleep(self.delay_seconds)
        return payload
