import pytest

from helpers import hist_race
from ratings import Ratings, build_ratings, finished, new_season, update_race


def test_finished_recognises_finishers_and_lapped_cars_only():
    for ok in ("Finished", "Lapped", "+1 Lap", "+2 Laps"):
        assert finished(ok)
    for bad in ("Retired", "Engine", "Collision", "Disqualified", "Did not start", ""):
        assert not finished(bad)


def test_strength_defaults_to_zero_for_unknown_ids():
    r = Ratings(car={"t1": 0.5}, driver={"d1": 0.25})
    assert r.strength("d1", "t1") == pytest.approx(0.75)
    assert r.strength("new", "new_team") == 0.0


def test_winning_raises_and_losing_lowers_the_car_rating():
    r = Ratings(car={}, driver={})
    for _ in range(5):
        update_race(r, [("a1", "fast"), ("a2", "fast"), ("b1", "slow"), ("b2", "slow")], 0.2, 0.1)
    assert r.car["fast"] > 0 > r.car["slow"]


def test_better_driver_in_the_same_car_gets_a_positive_offset_and_the_car_stays_near_the_middle():
    r = Ratings(car={}, driver={})
    for _ in range(8):
        update_race(r, [("star", "t"), ("other_team_driver", "u"), ("mate", "t"), ("u2", "u")], 0.2, 0.2)
    assert r.driver["star"] > r.driver["mate"]
    assert abs(r.car["t"]) < abs(r.driver["star"] - r.driver["mate"]) + 0.5


def test_fewer_than_two_drivers_changes_nothing():
    r = Ratings(car={"t": 0.3}, driver={"d": 0.1})
    update_race(r, [("d", "t")], 0.5, 0.5)
    update_race(r, [], 0.5, 0.5)
    assert r.car == {"t": 0.3} and r.driver == {"d": 0.1}


def test_new_season_shrinks_ratings_towards_zero():
    r = Ratings(car={"t": 1.0}, driver={"d": -0.5})
    new_season(r, car_keep=0.5, driver_keep=0.8)
    assert r.car["t"] == pytest.approx(0.5) and r.driver["d"] == pytest.approx(-0.4)


def race(season, rnd, rows):
    return hist_race(season, rnd, rows)


def test_retiring_driver_does_not_change_his_skill_rating():
    ordered = [("a", "t1", 1), ("b", "t2", 2), ("c", "t3", 3)]
    clean = build_ratings([race(2026, 1, ordered)], 0.2, 0.2, 1.0, 1.0)
    with_dnf = build_ratings([race(2026, 1, ordered + [("dnf", "t4", None)])], 0.2, 0.2, 1.0, 1.0)
    assert "dnf" not in with_dnf.driver or with_dnf.driver["dnf"] == 0.0
    assert with_dnf.driver["a"] == pytest.approx(clean.driver["a"]) and with_dnf.car["t1"] == pytest.approx(clean.car["t1"])


def test_build_ratings_replays_in_order_and_applies_the_season_boundary():
    rows = [("a", "t1", 1), ("b", "t2", 2)]
    r1 = build_ratings([race(2025, 1, rows)], 0.3, 0.3, 0.5, 0.5)
    r2 = build_ratings([race(2025, 1, rows), race(2026, 1, [("a", "t1", 2), ("b", "t2", 1)])], 0.3, 0.3, 0.5, 0.5)
    assert r1.car["t1"] > 0 > r1.car["t2"]
    assert r2.car["t1"] < r1.car["t1"]                     # po zmianie sezonu ściągnięte i przegrany wyścig


def test_build_ratings_is_independent_of_the_input_order():
    rows = [("a", "t1", 1), ("b", "t2", 2), ("c", "t3", 3)]
    races = [race(2025, 1, rows), race(2025, 2, rows[::-1] and [("c", "t3", 1), ("b", "t2", 2), ("a", "t1", 3)])]
    forward = build_ratings(races, 0.2, 0.2, 0.7, 0.9)
    backward = build_ratings(races[::-1], 0.2, 0.2, 0.7, 0.9)
    assert forward.car == pytest.approx(backward.car)
