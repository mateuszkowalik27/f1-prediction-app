import pytest

from schemas import DriverProbability
from scoring import actual_distribution, ranking_rps, rps


def test_perfect_forecast_scores_zero():
    assert rps([1, 0, 0], [1, 0, 0]) == 0


def test_worst_forecast_scores_one():
    assert rps([1, 0, 0], [0, 0, 1]) == 1


def test_a_near_miss_is_punished_less_than_a_far_miss():
    near = rps([0, 1, 0], [1, 0, 0])
    far = rps([0, 0, 1], [1, 0, 0])
    assert near == pytest.approx(0.5) and far == pytest.approx(1.0) and near < far


def test_unclassified_driver_is_spread_over_the_last_places():
    assert actual_distribution(None, 5, 3) == [0, 0, 0, 0.5, 0.5]
    assert actual_distribution(2, 4, 4) == [0, 1, 0, 0]


def prob(driver, dist):
    return DriverProbability(driver_id=driver, win=dist[0], podium=sum(dist[:3]), points=0, expected_points=0,
                             position_distribution=dist)


def test_ranking_rps_averages_over_drivers_present_in_both():
    prediction = [prob("a", [1, 0, 0]), prob("b", [0, 1, 0]), prob("ghost", [0, 0, 1])]
    actual = {"a": 1, "b": 2, "c": 3}                      # "ghost" nie jedzie, "c" nie ma prognozy: pomijani
    assert ranking_rps(prediction, actual) == 0


def test_ranking_rps_treats_none_as_a_late_finish():
    prediction = [prob("a", [1, 0, 0]), prob("b", [0, 1, 0]), prob("c", [0, 0, 1])]
    good = ranking_rps(prediction, {"a": 1, "b": 2, "c": None})       # c nieklasyfikowany: i tak ostatni
    bad = ranking_rps(prediction, {"a": None, "b": 2, "c": 1})        # prognoza odwrotna do wyniku
    assert good == 0 and bad > 0.3
