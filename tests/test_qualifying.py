import pytest

from simulate.qualifying import predict_qualifying

STRENGTH = {"a": 2.0, "b": 1.0, "c": 0.0, "d": -1.0}


def test_strongest_driver_highest_pole_probability():
    result = predict_qualifying(STRENGTH, n=2000)
    pole = {p.driver_id: p.win for p in result.probabilities}
    assert pole["a"] == max(pole.values())
    assert pole["a"] > pole["b"] > pole["d"]


def test_same_seed_same_result():
    one = predict_qualifying(STRENGTH, n=1000, seed=7)
    two = predict_qualifying(STRENGTH, n=1000, seed=7)
    assert one == two
    assert one != predict_qualifying(STRENGTH, n=1000, seed=8)


def test_pole_probabilities_sum_to_one():
    result = predict_qualifying(STRENGTH, n=1000)
    assert sum(p.win for p in result.probabilities) == pytest.approx(1.0)


def test_each_position_distribution_sums_to_one():
    for p in predict_qualifying(STRENGTH, n=1000).probabilities:
        assert len(p.position_distribution) == len(STRENGTH)
        assert sum(p.position_distribution) == pytest.approx(1.0)
        assert p.points == 0 and p.expected_points == 0


def test_predicted_grid_is_permutation():
    grid = predict_qualifying(STRENGTH, n=1000).predicted_grid
    assert sorted(grid.values()) == [1, 2, 3, 4]
    assert grid["a"] == 1


# --- wspólny wstrząs i chaos w kwalifikacjach (model v3, etap 4) ---
from simulate.qualifying import predict_qualifying as pq  # noqa: E402

Q_TEAMS = {"a": "t1", "b": "t1", "c": "t2", "d": "t2"}
Q_STRENGTH = {"a": 2.0, "b": 0.0, "c": 0.0, "d": 0.0}


def test_zero_noise_parameters_reproduce_the_old_qualifying_result():
    plain = pq(Q_STRENGTH, n=500, seed=2)
    zero = pq(Q_STRENGTH, n=500, seed=2, teams=Q_TEAMS, team_share=0.0, chaos_prob=0.0, chaos_mult=4.0)
    assert plain.probabilities == zero.probabilities and plain.predicted_grid == zero.predicted_grid


def test_chaos_flattens_the_pole_chance_of_the_favourite():
    calm = pq(Q_STRENGTH, n=6000, seed=4).probabilities
    wild = pq(Q_STRENGTH, n=6000, seed=4, chaos_prob=0.5, chaos_mult=4.0).probabilities
    pole = lambda rows: next(p.win for p in rows if p.driver_id == "a")
    assert pole(wild) < pole(calm)


def test_shared_team_noise_keeps_probabilities_normalised():
    rows = pq(Q_STRENGTH, n=3000, seed=1, teams=Q_TEAMS, team_share=0.7, chaos_prob=0.2, chaos_mult=3.0).probabilities
    assert sum(p.win for p in rows) == pytest.approx(1.0)
