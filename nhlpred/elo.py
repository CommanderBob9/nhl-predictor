"""Elo ratings: a pre-game home win probability for every game, using only past results."""

START_RATING = 1500
K = 6
HOME_ADV = 28
CARRY_OVER = 2 / 3
TEAM_ALIASES = {"ARI": "UTA"}


def home_win_probability(home_rating: float, away_rating: float, home_adv=HOME_ADV) -> float:
    """Chance the home team wins, before the game. No home bonus at neutral sites."""
    diff = home_rating + home_adv - away_rating
    # 400 is a constant representing the elo difference to achieve 10 to 1 win odds
    # K and HOME_ADV tuned relative to 400 (constant)
    p = 1 / (1 + 10 ** (-diff / 400))
    return p


def run_elo(games: list, k=K, carry_over=CARRY_OVER, home_adv=HOME_ADV) -> tuple[list[dict], dict[str, float]]:
    """Walk games in date order. For each, record the pre-game ratings and
    probability, then update the ratings. Regress towards 1500 at each new season."""
    ratings = {}
    predictions = []
    prev_season = None

    for game in games:
        home = TEAM_ALIASES.get(game["home_team"], game["home_team"])
        away = TEAM_ALIASES.get(game["away_team"], game["away_team"])

        # Season check, regress ratings
        if game["season"] != prev_season and prev_season is not None:
            for team in ratings:
                ratings[team] = carry_over * (ratings[team] - START_RATING) + START_RATING
        prev_season = game["season"]

        home_rating = ratings.get(home, START_RATING)
        away_rating = ratings.get(away, START_RATING)

        p = home_win_probability(home_rating, away_rating, 0 if game["neutral_site"] else home_adv)
        predictions.append({
            "game_id": game["game_id"],
            "season": game["season"],
            "game_type": game["game_type"],
            "game_date": game["game_date"],
            "home_team": game["home_team"],
            "away_team": game["away_team"],
            "neutral_site": game["neutral_site"],
            "home_rating": home_rating,
            "away_rating": away_rating,
            "p_home": p,
            "home_win": game["home_win"],
        })

        change = k * (game["home_win"] - p)
        ratings[home] = home_rating + change
        ratings[away] = away_rating - change

    return predictions, ratings


def evaluate(predictions: list[dict], from_season: int = 20232024) -> dict:
    """Accuracy and log loss for regular-season games from 'from_season' onward."""


def main() -> None:
    """Load completed_games, run Elo, print Elo vs. the home baseline."""