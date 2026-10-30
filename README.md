# NHL Predictor

Pre-game win probabilities for NHL games, evaluated honestly against simple baselines and tracked live through the 2026-27 season.

**Status:** work in progress. Step 0 (data pipeline) is done; see the roadmap below.

## Quickstart

Requires Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python -m nhlpred.ingest           # pull 2015-16 through the current season (~5 min the first time)
python -m nhlpred.report           # sanity checks + the home-team baseline
pytest                             # run the tests
```

To refresh the current season (this becomes the daily job):

```bash
python -m nhlpred.ingest --current
```

## How it works

```
NHL web API  ──>  nhl_api.py  ──>  data/raw/*.json   (cached raw responses)
(api-web.nhle.com)    │
                      v
                  games.py     parse + filter (regular season & playoffs only)
                      │
                      v
                   db.py       SQLite: `games` table + `completed_games` view
                      │
                      v
                 report.py     data checks, home-team baseline
```

| File | What it does |
|---|---|
| `nhlpred/nhl_api.py` | HTTP client: timeouts, retries with backoff, polite delay, disk cache for finished weeks |
| `nhlpred/games.py` | Walks a season week by week and turns raw JSON into `Game` records |
| `nhlpred/db.py` | SQLite schema and idempotent upserts |
| `nhlpred/ingest.py` | Command line entry point for pulling seasons |
| `nhlpred/report.py` | Per-season checks and the first baseline |
| `tests/` | Unit tests against a sample API response; no network needed |

## Design notes

- **Raw data is kept separately from clean data.** Every finished week's API response is saved untouched in `data/raw/`. If parsing logic changes, the database can be rebuilt without re-downloading anything.
- **Only settled weeks are cached.** A week is cached once its last day is 3+ days old. Anything more recent is refetched, because scores and postponements can still change.
- **Writes are upserts keyed on game id.** Re-running the pull never duplicates games. A game stored as `FUT` gets its score filled in once it's final.
- **Scores are only stored for final games.** Live games have partial scores. Storing them would risk training on unfinished results.
- **Game date = the league's (Eastern) calendar date,** not the UTC start time. A 10pm ET game is already the next day in UTC, which would break rest-day features.
- **The season walk never skips a day.** The schedule endpoint returns about a week at a time. The next request starts the day after the last listed date. It only jumps ahead (to `nextStartDate`) over weeks with no games.

## Data quirks worth knowing

- **2019-20** was cut short by COVID, so teams played different numbers of games, and the playoffs ran into September.
- **2020-21** started in January, had 56-game seasons and used temporary divisions.
- **2026-27** is the first 84-game season.
- **Arizona → Utah:** the Coyotes (ARI) stopped playing after 2023-24, and Utah (UTA) started in 2024-25. Utah's numeric team id changed again with its 2025-26 rename, so teams are keyed by abbreviation.
- **Expansion teams:** Vegas (VGK) joined in 2017-18 and Seattle (SEA) in 2021-22.
- **Shootout scoring:** the shootout winner is credited one goal in the final score, so `home_score > away_score` always identifies the winner.
- **Unofficial API:** the API is free but undocumented and could change without notice. The tests pin down the response format this code expects.

## Roadmap

- [x] **Step 0:** schedule and results ingestion, tests, CI
- [ ] Elo rating baseline (updated strictly in date order, no lookahead)
- [ ] Rolling team features: goal differential, shots, rest days, back-to-backs
- [ ] Logistic regression → LightGBM with time-based validation; report log loss, Brier score, calibration
- [ ] Daily job: predict today's games before puck drop, grade yesterday's
- [ ] API + React front end, deployed
