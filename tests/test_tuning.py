import pytest

import config
from schemas import WeightSnapshot, WeightsFile
from tuning import append_snapshot, tune_weights

BOUNDS = {"a": (0.05, 0.5), "b": (0.05, 0.5)}
BASE = {"a": 0.2, "b": 0.2}


def target(w):
    """Syntetyczny błąd: najlepiej a=0,5 i b=0,05."""
    return (w["a"] - 0.5) ** 2 + (w["b"] - 0.05) ** 2


def test_returns_base_below_three_rounds():
    assert tune_weights(BASE, BOUNDS, set(), rounds_played=2, evaluate=target) == BASE


def test_moves_toward_predictive_factor_only_by_a_fraction():
    rounds = config.TUNING_K          # lambda = 0,5
    tuned = tune_weights(BASE, BOUNDS, set(), rounds_played=rounds, evaluate=target)
    assert tuned["a"] == pytest.approx(0.2 + 0.5 * (0.5 - 0.2))
    assert tuned["b"] == pytest.approx(0.2 + 0.5 * (0.05 - 0.2))


def test_more_rounds_move_further():
    few = tune_weights(BASE, BOUNDS, set(), rounds_played=3, evaluate=target)
    many = tune_weights(BASE, BOUNDS, set(), rounds_played=24, evaluate=target)
    assert few["a"] < many["a"] < 0.5


def test_weights_stay_inside_bounds():
    tuned = tune_weights(BASE, BOUNDS, set(), rounds_played=50, evaluate=lambda w: -(w["a"] + w["b"]))
    assert all(lo <= tuned[k] <= hi for k, (lo, hi) in BOUNDS.items())


def test_locked_weights_untouched():
    tuned = tune_weights(BASE, BOUNDS, {"a"}, rounds_played=24, evaluate=target)
    assert tuned["a"] == BASE["a"] and tuned["b"] != BASE["b"]


def test_flat_objective_keeps_base():
    assert tune_weights(BASE, BOUNDS, set(), rounds_played=24, evaluate=lambda w: 1.0) == BASE


def test_history_appended_each_round_without_duplicates():
    first = append_snapshot(None, {"a": 0.3}, round=4)
    assert [s.round for s in first.history] == [4] and first.weights == {"a": 0.3}
    second = append_snapshot(first, {"a": 0.35}, round=5)
    assert [s.round for s in second.history] == [4, 5]
    again = append_snapshot(second, {"a": 0.36}, round=5)       # ta sama runda: zastępuje wpis
    assert [s.round for s in again.history] == [4, 5] and again.history[-1].weights == {"a": 0.36}
