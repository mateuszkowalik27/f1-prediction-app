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


# --- poziomy oceny (model v3, etap 1) ---
from dataclasses import replace  # noqa: E402

from evaluation import RaceLevels, _predict_case, evaluate_levels  # noqa: E402

QUALI = {"d1": 1, "d2": 2, "d3": 3, "d4": 4}


def only(factor):
    return {**{k: 0.0 for k in weights()}, factor: 1.0, f"q_{factor}": 1.0, "grid_base_weight": config.GRID_BASE_WEIGHT,
            "race_noise_base": config.RACE_NOISE_BASE, "quali_noise": config.QUALIFYING_NOISE}


def test_prepare_rounds_stores_the_actual_qualifying_order():
    cases = prepare_rounds(2027, clients(grid=QUALI))
    assert all(c.actual_quali == QUALI for c in cases)
    assert all(c.actual_quali is None for c in prepare_rounds(2027, clients()))      # brak danych kwalifikacji


def test_unknown_grid_changes_the_race_prediction():
    case = prepare_rounds(2027, clients())[0]
    known = _predict_case(case, weights(), 400)
    unknown = _predict_case(case, weights(), 400, grid_known=False)
    assert [p.win for p in known] != [p.win for p in unknown]


def test_levels_cover_pre_post_and_qualifying():
    case = prepare_rounds(2027, clients(grid=QUALI))[0]
    (levels,) = evaluate_levels([case], weights(), n=300)
    assert isinstance(levels, RaceLevels) and levels.round == case.round
    assert 0 <= levels.rps_pre <= 1 and 0 <= levels.rps_post <= 1 and 0 <= levels.rps_quali <= 1


def test_levels_skip_qualifying_without_data():
    case = prepare_rounds(2027, clients())[0]
    (levels,) = evaluate_levels([case], weights(), n=300)
    assert levels.rps_quali is None and levels.rps_pre is not None


def test_a_strength_that_matches_the_real_qualifying_scores_better():
    base = prepare_rounds(2027, clients(grid=QUALI))[0]
    right = replace(base, factor_scores={"car_pace": {"d1": 3.0, "d2": 1.0, "d3": -1.0, "d4": -3.0}})
    wrong = replace(base, factor_scores={"car_pace": {"d1": -3.0, "d2": -1.0, "d3": 1.0, "d4": 3.0}})
    good = evaluate_levels([right], only("car_pace"), n=500)[0].rps_quali
    bad = evaluate_levels([wrong], only("car_pace"), n=500)[0].rps_quali
    assert good < bad


# --- osobne siły kwalifikacyjna i wyścigowa (model v3, etap 2) ---
QG = {"d1": 3.0, "d2": 1.0, "d3": -1.0, "d4": -3.0}                      # czynnik zgodny z faktycznymi kwalifikacjami


def quali_gap_case():
    base = prepare_rounds(2027, clients(grid=QUALI))[0]
    return replace(base, factor_scores={"quali_gap": QG})


def quali_weights(q=1.0, race=0.0, noise=0.8):
    return {**{k: 0.0 for k in weights()}, "quali_gap": race, "q_quali_gap": q, "quali_noise": noise,
            "grid_base_weight": config.GRID_BASE_WEIGHT, "race_noise_base": config.RACE_NOISE_BASE}


def test_separate_qualifying_strength_uses_its_own_weights():
    case = quali_gap_case()
    split = evaluate_levels([case], quali_weights(q=1.0, race=0.0), n=500)[0].rps_quali
    no_signal = evaluate_levels([case], quali_weights(q=0.0, race=0.0), n=500)[0].rps_quali
    assert split < no_signal                           # waga q_quali_gap działa na kwalifikacje mimo wagi wyścigowej 0


def test_shared_mode_reproduces_the_old_behaviour():
    case = quali_gap_case()
    shared = evaluate_levels([case], quali_weights(q=0.0, race=0.0), n=500, separate=False)[0].rps_quali
    no_signal = evaluate_levels([case], quali_weights(q=0.0, race=0.0), n=500)[0].rps_quali
    assert shared < no_signal                          # stary tryb: quali_gap (waga 0,10) zasilał też kwalifikacje


def test_qualifying_noise_from_the_weights_is_used():
    case = quali_gap_case()
    sharp = evaluate_levels([case], quali_weights(noise=0.1), n=800)[0].rps_quali
    blurry = evaluate_levels([case], quali_weights(noise=1.5), n=800)[0].rps_quali
    assert sharp < blurry


def test_unknown_grid_prediction_uses_the_qualifying_strength():
    case = quali_gap_case()
    case = replace(case, factor_scores={**case.factor_scores, "car_pace": {d: 0.0 for d in QG}})     # neutralna siła wyścigowa
    w = {**quali_weights(q=1.0, race=0.0), "car_pace": 1.0}
    split = _predict_case(case, w, 600, grid_known=False)
    shared = _predict_case(case, w, 600, grid_known=False, separate=False)
    assert [p.win for p in split] != [p.win for p in shared]


def test_backtest_context_carries_a_long_history_with_older_seasons_but_no_future():
    cases = prepare_rounds(2027, clients())
    for case in cases:
        seasons = {h.season for h in case.ctx.long_history}
        assert 2026 in seasons or case.ctx.long_history == [] or 2027 in seasons
        assert all((h.season, h.round) < (2027, case.round) for h in case.ctx.long_history)
    assert any(h.season == 2026 for h in cases[0].ctx.long_history)               # starsze niż `history` (tam tylko poprzedni sezon)


# --- wspólny wstrząs i chaos w ocenie (model v3, etap 4) ---
def test_noise_parameters_in_the_weights_change_the_evaluation_and_zero_means_off():
    case = prepare_rounds(2027, clients(grid=QUALI))[0]
    off = {**weights(), "team_noise_share": 0.0, "chaos_base": 0.0, "chaos_sc": 0.0, "chaos_rain": 0.0}
    plain = evaluate_levels([case], off, n=400)[0]
    other_mult = evaluate_levels([case], {**off, "chaos_mult": 7.0}, n=400)[0]
    wild = evaluate_levels([case], {**off, "team_noise_share": 0.6, "chaos_base": 0.5, "chaos_mult": 4.0}, n=400)[0]
    assert plain == other_mult                                        # bez chaosu mnożnik nic nie zmienia
    assert (wild.rps_pre, wild.rps_post, wild.rps_quali) != (plain.rps_pre, plain.rps_post, plain.rps_quali)
