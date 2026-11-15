import pytest

from nhlpred.elo import START_RATING, home_win_probability, run_elo


def game(game_id, season, home, away, home_win, neutral_site=0, game_type=2):
    """A completed_games row as a plain dict. run_elo only uses row["field"],
    which works the same on a dict and a sqlite3.Row, so no database is needed.
    neutral_site is an int on purpose: that's what SQLite returns."""
    return {
        "game_id": game_id, "season": season, "game_type": game_type,
        "game_date": f"2025-10-{game_id:02d}", "home_team": home, "away_team": away,
        "neutral_site": neutral_site, "home_win": home_win,
    }


# --- home_win_probability -----------------------------------------------------

def test_equal_teams_without_home_ice_is_a_coin_flip():
    assert home_win_probability(1500, 1500, home_adv=0) == 0.5


def test_400_point_gap_means_10_to_1_odds():
    assert home_win_probability(1900, 1500, home_adv=0) == pytest.approx(10 / 11)
    assert home_win_probability(1500, 1900, home_adv=0) == pytest.approx(1 / 11)


def test_home_ice_counts_as_extra_rating_points():
    assert home_win_probability(1500, 1500, home_adv=50) == pytest.approx(
        home_win_probability(1550, 1500, home_adv=0)
    )


def test_only_the_rating_gap_matters():
    # 1500 is arbitrary; shifting every rating must not change any prediction.
    assert home_win_probability(1600, 1500) == pytest.approx(home_win_probability(2600, 2500))


def test_both_sides_add_up_to_one():
    p = home_win_probability(1530, 1480, home_adv=0)
    q = home_win_probability(1480, 1530, home_adv=0)
    assert p + q == pytest.approx(1)


# --- run_elo: record before update ----------------------------------------------

def test_first_game_starts_both_teams_at_the_start_rating():
    (pred,), _ = run_elo([game(1, 20252026, "TOR", "MTL", 1)], home_adv=28)
    assert pred["home_rating"] == pred["away_rating"] == START_RATING
    assert pred["p_home"] == pytest.approx(home_win_probability(1500, 1500, home_adv=28))


def test_prediction_does_not_depend_on_that_games_result():
    # The lookahead check: if run_elo updated before recording, the recorded
    # probability for game 1 would differ depending on who won game 1.
    won, _ = run_elo([game(1, 20252026, "TOR", "MTL", home_win=1)])
    lost, _ = run_elo([game(1, 20252026, "TOR", "MTL", home_win=0)])
    assert won[0]["p_home"] == lost[0]["p_home"]
    assert won[0]["home_rating"] == lost[0]["home_rating"]


def test_next_game_starts_from_the_previous_games_post_game_rating():
    games = [game(1, 20252026, "TOR", "MTL", 1), game(2, 20252026, "MTL", "TOR", 1)]
    preds, _ = run_elo(games, k=6, home_adv=28)
    change = 6 * (1 - preds[0]["p_home"])
    assert preds[1]["away_rating"] == pytest.approx(START_RATING + change)  # TOR
    assert preds[1]["home_rating"] == pytest.approx(START_RATING - change)  # MTL


# --- run_elo: the update ---------------------------------------------------------

def test_winner_gains_exactly_what_the_loser_loses():
    (pred,), ratings = run_elo([game(1, 20252026, "TOR", "MTL", 1)], k=6)
    change = 6 * (1 - pred["p_home"])
    assert ratings["TOR"] == pytest.approx(START_RATING + change)
    assert ratings["MTL"] == pytest.approx(START_RATING - change)


def test_ratings_stay_centred_on_the_start_rating():
    # Zero-sum updates plus regression toward 1500 keep the average at 1500.
    games = [
        game(1, 20242025, "TOR", "MTL", 1),
        game(2, 20242025, "BOS", "TOR", 0),
        game(3, 20242025, "MTL", "BOS", 1),
        game(4, 20252026, "TOR", "BOS", 0),
        game(5, 20252026, "SEA", "MTL", 1),  # a new team mid-way
    ]
    _, ratings = run_elo(games)
    assert sum(ratings.values()) / len(ratings) == pytest.approx(START_RATING)


def test_an_upset_moves_ratings_more_than_an_expected_win():
    (expected,), r1 = run_elo([game(1, 20252026, "TOR", "MTL", home_win=1)], home_adv=50)
    (upset,), r2 = run_elo([game(1, 20252026, "TOR", "MTL", home_win=0)], home_adv=50)
    assert abs(r2["TOR"] - START_RATING) > abs(r1["TOR"] - START_RATING)


def test_k_controls_the_size_of_the_update():
    _, small = run_elo([game(1, 20252026, "TOR", "MTL", 1)], k=5)
    _, big = run_elo([game(1, 20252026, "TOR", "MTL", 1)], k=20)
    assert big["TOR"] - START_RATING == pytest.approx(4 * (small["TOR"] - START_RATING))


# --- run_elo: seasons, neutral sites, relocation -------------------------------------

def test_ratings_regress_toward_the_start_rating_between_seasons():
    games = [game(1, 20242025, "TOR", "MTL", 1), game(2, 20252026, "TOR", "MTL", 1)]
    preds, _ = run_elo(games, k=20, carry_over=0.5)
    tor_after_game_1 = START_RATING + 20 * (1 - preds[0]["p_home"])
    assert preds[1]["home_rating"] == pytest.approx(
        START_RATING + 0.5 * (tor_after_game_1 - START_RATING)
    )


def test_no_regression_within_a_season():
    games = [game(1, 20252026, "TOR", "MTL", 1), game(2, 20252026, "TOR", "MTL", 1)]
    preds, _ = run_elo(games, k=20, carry_over=0.5)
    assert preds[1]["home_rating"] == pytest.approx(START_RATING + 20 * (1 - preds[0]["p_home"]))


def test_neutral_site_games_get_no_home_bonus():
    (pred,), _ = run_elo([game(1, 20252026, "TOR", "MTL", 1, neutral_site=1)], home_adv=50)
    assert pred["p_home"] == 0.5


def test_home_adv_parameter_is_used():
    (low,), _ = run_elo([game(1, 20252026, "TOR", "MTL", 1)], home_adv=10)
    (high,), _ = run_elo([game(1, 20252026, "TOR", "MTL", 1)], home_adv=60)
    assert high["p_home"] > low["p_home"] > 0.5


def test_utah_inherits_arizonas_rating():
    games = [game(1, 20232024, "ARI", "TOR", 1), game(2, 20242025, "UTA", "TOR", 1)]
    preds, ratings = run_elo(games, k=20, carry_over=0.5)
    ari_after = START_RATING + 20 * (1 - preds[0]["p_home"])
    assert preds[1]["home_rating"] == pytest.approx(START_RATING + 0.5 * (ari_after - START_RATING))
    assert "ARI" not in ratings
    assert preds[0]["home_team"] == "ARI"  # the record keeps the name as played
