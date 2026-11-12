import math

import pytest

import config
from evaluation import backtest, evaluate, evaluate_season, prepare_rounds
from fakes import clients
from schemas import DriverProbability


def prob(driver, win, position, count=4, podium=None):
    dist = [0.0] * count
    dist[position] = 1.0
    return DriverProbability(driver_id=driver, win=win, podium=win if podium is None else podium, points=1.0,
                             expected_points=0.0, position_distribution=dist)


PERFECT = [prob("a", 1.0, 0), prob("b", 0.0, 1), prob("c", 0.0, 2), prob("d", 0.0, 3)]


def test_perfect_prediction_zero_error_and_top3_true():
    e = evaluate(7, PERFECT, {"a": 1, "b": 2, "c": 3, "d": 4})
    assert e.round == 7 and e.winner_prob == 1.0 and e.winner_in_top3 is True
    assert e.mean_abs_position_error == 0.0 and e.brier_win == 0.0


def test_winner_with_zero_probability_has_high_brier():
    rows = [prob("x", 0.6, 0, count=5), prob("y", 0.2, 1, count=5), prob("z", 0.1, 2, count=5),
            prob("w", 0.1, 3, count=5), prob("v", 0.0, 4, count=5)]
    e = evaluate(1, rows, {"v": 1, "x": 2, "y": 3, "z": 4, "w": 5})
    assert e.winner_prob == 0.0 and e.winner_in_top3 is False
    assert e.brier_win == pytest.approx((0.36 + 0.04 + 0.01 + 0.01 + 1.0) / 5)


def test_dnf_excluded_from_position_error():
    e = evaluate(1, PERFECT, {"a": 1, "c": 2, "b": 3, "d": None})   # b i c zamienione, d nie dojechał
    assert e.mean_abs_position_error == pytest.approx(2 / 3)        # a: 0, b: |2-3|, c: |3-2|; d pominięty


def test_winner_missing_from_prediction_counts_as_zero_probability():
    e = evaluate(1, PERFECT, {"ghost": 1, "a": 2})
    assert e.winner_prob == 0.0 and e.winner_in_top3 is False


def weights():
    return config.default_weights()


def test_backtest_never_uses_data_from_predicted_round():
    cases = prepare_rounds(2027, clients())
    assert [c.round for c in cases] == [1, 2]
    for case in cases:
        for h in case.ctx.history + case.ctx.circuit_history:
            assert (h.season, h.round) < (2027, case.round)
    assert not any((h.season, h.round) == (2027, 2) for h in cases[0].ctx.history)   # przyszłość niewidoczna


def test_backtest_returns_one_evaluation_per_completed_round():
    evaluations = backtest(2027, clients(), weights(), n=300)
    assert [e.round for e in evaluations] == [1, 2]
    assert all(math.isfinite(e.brier_win) and 0 <= e.winner_prob <= 1 for e in evaluations)


def test_round_without_results_is_skipped():
    assert [c.round for c in prepare_rounds(2027, clients(empty_round=3))] == [1, 2]


def test_evaluate_season_returns_empty_when_jolpica_fails():
    assert evaluate_season(2027, clients(fail=True), weights(), n=100) == []


# --- agregaty w teście wstecznym i wiele sezonów (model v2) ---
from evaluation import prepare_seasons   # noqa: E402
from helpers import make_agg             # noqa: E402


def test_prepare_rounds_passes_aggregates_to_context_without_the_round_itself_or_later():
    aggs = [make_agg(2027, 1), make_agg(2027, 2), make_agg(2027, 5)]
    cases = {c.round: c for c in prepare_rounds(2027, clients(), aggregates=aggs)}
    assert cases[1].ctx.aggregates == []
    assert [(a.season, a.round) for a in cases[2].ctx.aggregates] == [(2027, 1)]


def test_prepare_seasons_returns_cases_per_season():
    by_season = prepare_seasons([2026, 2027], clients(), [])
    assert sorted(by_season) == [2026, 2027]
    assert [c.round for c in by_season[2027]] == [1, 2] and [c.round for c in by_season[2026]] == [23, 24]


def test_prepare_seasons_skips_season_without_results():
    assert sorted(prepare_seasons([2020, 2027], clients(), [])) == [2027]


def test_predict_rounds_returns_predictions_with_actual_finish():
    from evaluation import predict_rounds
    cases = prepare_rounds(2027, clients())
    out = predict_rounds(cases, weights(), n=200)
    assert len(out) == len(cases)
    rows, actual = out[0]
    assert abs(sum(r.win for r in rows) - 1.0) < 0.05 and actual and 1 in actual.values()   # w nielicznych symulacjach wszyscy odpadają


def test_backtest_uses_the_races_own_air_temperature_as_a_stand_in_for_the_forecast():
    aggs = [make_agg(2027, 1), make_agg(2027, 2, air_temp_c=21.0)]
    cases = {c.round: c for c in prepare_rounds(2027, clients(), aggregates=aggs)}
    assert cases[2].ctx.weather.start_temperature_c == 21.0
    assert cases[2].ctx.weather.rain_probability == 0.0         # bez deszczu: nie włącza umiejętności deszczowej
    assert cases[1].ctx.weather is None                         # runda bez temperatury w agregacie
