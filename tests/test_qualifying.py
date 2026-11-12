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
