"""Score win probabilities against real results, next to the always pick home baseline.

Usage:
    from nhlpred.evaluate import VALIDATION_SEASONS, evaluate, format_results
    
    result = evaluate(predictions, games, *VALIDATION_SEASONS)
    print(format_results("Validation", {"elo": result}))
"""

import math
from nhlpred.games import REGULAR_SEASON, season_label

VALIDATION_SEASONS = (20212022, 20222023) # settings chosen on these seasons
TEST_SEASONS = (20232024, 20252026)       # settings are frozen and season is scored once

# Probabilities are kept this far away from 0 and 1, so log(0) can never happen.
EPSILON = 1e-15


def is_scored(game) -> bool:
    """Leave out playoff and neutral site games since home baseline is not a fair comparison"""
    return game["game_type"] == REGULAR_SEASON and not game["neutral_site"]


def in_seasons(game, first_season: int, last_season: int) -> bool:
    return first_season <= game["season"] <= last_season


def scored_pairs(predictions: list[dict], games: list, first_season: int, last_season: int
                 ) -> list[tuple[float, int]]:
    """(p_home, home_win) for every scored game in the season range that was predicted.
       p_home comes from a model and home_win (result) comes from games.
    """
    p_by_game: dict[int, float] = {}
    for prediction in predictions:
        if prediction["game_id"] in p_by_game:
            raise ValueError(f"more than one prediction for game {prediction['game_id']}")
        p_by_game[prediction["game_id"]] = prediction["p_home"]

    pairs = []
    for game in games:
        if not (in_seasons(game, first_season, last_season) and is_scored(game)):
            continue
        if game["game_id"] in p_by_game:
            pairs.append((p_by_game[game["game_id"]], game["home_win"]))
    return pairs


def home_win_rate_before(games: list, season: int) -> tuple[float, int]:
    """Home win rate over scored games in previous seasons.

    Returns the constant probability the baseline predicts using earlier seasons.
    """
    wins = [game["home_win"] for game in games if game["season"] < season and is_scored(game)]
    if not wins:
        raise ValueError(f"no scored games before {season} to take the baseline from")
    return sum(wins) / len(wins), len(wins)


def metrics(pairs: list[tuple[float, int]]) -> dict:
    """Accuracy, log loss and Brier score for (probability, outcome) pairs.
    
    Accuracy asks whether the favourite won. Log loss and Brier score also ask
    whether the probability was right, lower is better for both.
    Log loss punishes confident misses the hardest; a coin flip scores ln 2 = 0.6931
    on log loss and 0.25 on Brier.
    """
    if not pairs:
        return {"accuracy": None, "log_loss": None, "brier": None}

    correct = 0
    log_loss_sum = 0.0
    brier_sum = 0.0
    for p_home, home_win in pairs:
        p_home = min(max(p_home, EPSILON), 1 - EPSILON)
        picked_home = p_home > 0.5
        if picked_home == (home_win == 1):
            correct += 1
        # The probability the model gave to what actually happened.
        p_of_result = p_home if home_win == 1 else 1 - p_home
        log_loss_sum += -math.log(p_of_result)
        brier_sum += (p_home - home_win) ** 2

    n = len(pairs)
    return {"accuracy": correct / n, "log_loss": log_loss_sum / n, "brier": brier_sum / n}

