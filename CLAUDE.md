# NHL Predictor

Pre-game win probabilities for NHL games. The goal is a model that's evaluated honestly against simple baselines, makes live predictions before games through the 2026-27 season, and is served by a small deployed web app.

## Status

- **Done (step 0):** schedule and results ingestion into SQLite, tests, CI.
- **Next:** Elo baseline → rolling team features → logistic regression and LightGBM → daily prediction job → API + React front end, deployed.

Keep the roadmap checkboxes in `README.md` up to date as steps finish.

## Commands (Windows, PowerShell)

```powershell
.venv\Scripts\Activate.ps1
pytest                              # run all tests (no network needed)
python -m nhlpred.ingest            # pull 2015-16 through the current season
python -m nhlpred.ingest --current  # refresh only the season in progress
python -m nhlpred.report            # data checks + home-team baseline
```

## Layout

```
nhlpred/nhl_api.py   HTTP client for api-web.nhle.com: retries, timeout, polite delay, disk cache
nhlpred/games.py     Game dataclass, parse_game(), fetch_season() (walks the schedule week by week)
nhlpred/db.py        SQLite schema, `games` table, `completed_games` view (adds home_win), upserts
nhlpred/ingest.py    CLI for pulling seasons
nhlpred/report.py    per-season checks and the home-team baseline
tests/               pytest; fixtures in tests/fixtures/ modelled on real API responses
data/                local only (gitignored): nhl.db and raw/ cached JSON
```

## Rules that keep results honest

These matter more than anything else in the project. Flag any code that breaks them.

- **No lookahead.** Features for a game may only use games played on earlier dates. Ratings like Elo must record the pre-game probability *before* updating on that game's result.
- **Time-based splits only.** Train on earlier seasons and test on later ones. Never use random train/test splits or shuffled k-fold on games.
- **Always compare to baselines.** Report results next to "always pick home team" and Elo. Use log loss and Brier score along with accuracy, and check calibration. Single-game NHL prediction tops out around 62% accuracy, so be skeptical of anything above that.
- **Trust only final scores.** `games` stores scores only when `game_state` is `OFF`/`FINAL`. Use `completed_games` for training labels.

## Data notes

- `game_date` is the league's Eastern calendar date (from the schedule), not the UTC start time.
- Key teams by abbreviation, not numeric id. Arizona (ARI) became Utah (UTA) in 2024-25, and Utah's id changed with its 2025-26 rename.
- 2019-20 was cut short by COVID (uneven games per team). 2020-21 had 56 games and started in January. 2026-27 is the first 84-game season.
- The NHL API is unofficial and undocumented. If a field is missing or renamed, fix the parser and add a fixture-based test for that case.

## Conventions

- Python 3.10+, type hints, small functions. Docstrings should explain *why*, not restate the code.
- Tests must not hit the network: use fixtures or fake clients (see `tests/test_games.py`).
- Add dependencies to `requirements.txt` only when code actually uses them.
- Run `pytest` before saying a change is done.
- `CLAUDE.local.md` holds personal notes and must stay out of git. If it isn't listed in `.gitignore`, add it.
