import json

import pytest

import oos
from evaluation import RoundCase
from helpers import make_ctx, make_entries, make_track
from oos import factor_gate, keep_rule, walk_forward, write_oos
from schemas import SeasonScore

DRIVERS = ["d1", "d2", "d3", "d4"]
BASE = {"signal": 0.5, "noise": 0.5, "grid_base_weight": 0.9, "race_noise_base": 0.5}
BOUNDS = {"signal": (0.0, 1.0), "noise": (0.0, 1.0)}


def case(round_no, winner):
    """Wyścig, w którym czynnik `signal` wskazuje zwycięzcę, a `noise` zawsze faworyzuje d4 (myli: d4 kończy zwykle ostatni; faworyzowanie d1 byłoby przy ocenie całej kolejności nieszkodliwe, bo d1 zwykle jest w czołówce)."""
    entries = make_entries(*[(d, "t") for d in DRIVERS])
    ctx = make_ctx(entries=entries, grid={d: i + 1 for i, d in enumerate(DRIVERS)})
    finish = {d: (1 if d == winner else 2 + i) for i, d in enumerate(d for d in DRIVERS if d != winner)}
    finish[winner] = 1
    return RoundCase(
        round=round_no, ctx=ctx,
        factor_scores={"signal": {d: (5.0 if d == winner else 0.0) for d in DRIVERS},
                       "noise": {d: (5.0 if d == "d4" else 0.0) for d in DRIVERS}},
        dnf={d: 0.0 for d in DRIVERS}, sim_track=make_track(0.0), stops=2, actual_finish=finish,
    )


def season_cases(n=8):
    return [case(i + 1, DRIVERS[i % 4]) for i in range(n)]


CASES = {2023: season_cases(), 2024: season_cases(), 2025: season_cases()}


def test_tuning_never_sees_the_test_season(monkeypatch):
    seen = []
    monkeypatch.setattr(oos, "tune_weights", lambda base, bounds, locked, rounds_played, evaluate: seen.append(rounds_played) or base)
    walk_forward({2023: season_cases(3), 2024: season_cases(3), 2025: season_cases(3)}, [2024, 2025], BASE, BOUNDS, set(), n=100)
    assert seen == [3, 6]                              # sezon 2024 widzi tylko 2023, sezon 2025 widzi 2023-2024


def test_walk_forward_returns_a_finite_brier_per_test_season():
    scores = walk_forward(CASES, [2024, 2025], BASE, BOUNDS, set(), n=300)
    assert sorted(scores) == [2024, 2025] and all(0 <= v <= 1 for v in scores.values())


def test_walk_forward_skips_test_season_without_cases():
    assert sorted(walk_forward(CASES, [2024, 2030], BASE, BOUNDS, set(), n=200)) == [2024]


@pytest.mark.parametrize("with_s, without_s, expected", [
    ({2024: .02, 2025: .02, 2026: .02}, {2024: .03, 2025: .03, 2026: .03}, True),
    ({2024: .01, 2025: .01, 2026: .035}, {2024: .03, 2025: .03, 2026: .03}, True),      # gorszy w jednym sezonie: nadal OK
    ({2024: .01, 2025: .035, 2026: .035}, {2024: .03, 2025: .03, 2026: .03}, False),    # średnio lepszy, ale gorszy w dwóch
    ({2024: .03, 2025: .03, 2026: .03}, {2024: .03, 2025: .03, 2026: .03}, False),      # remis nie wystarcza
    ({2024: .04, 2025: .04, 2026: .04}, {2024: .03, 2025: .03, 2026: .03}, False),
    ({2024: .01}, {2030: .03}, False),                                                  # brak wspólnych sezonów
])
def test_keep_rule(with_s, without_s, expected):
    assert keep_rule(with_s, without_s) is expected


def test_gate_keeps_informative_factor():
    result = factor_gate(CASES, "signal", [2024, 2025], BASE, BOUNDS, set(), n=300)
    assert result.keep is True
    assert all(result.with_scores[s] < result.without_scores[s] for s in (2024, 2025))


def test_gate_drops_pure_noise_factor():
    result = factor_gate(CASES, "noise", [2024, 2025], BASE, BOUNDS, set(), n=300)
    assert result.keep is False
    assert all(result.with_scores[s] > result.without_scores[s] for s in (2024, 2025))


def test_write_oos_roundtrip(tmp_path):
    path = tmp_path / "oos.json"
    write_oos(path, {2024: 0.0251, 2025: 0.0243})
    rows = [SeasonScore(**r) for r in json.loads(path.read_text())]
    assert [(r.season, r.brier) for r in rows] == [(2024, 0.0251), (2025, 0.0243)]


# --- poziomy oceny, przedziały i nowa bramka (model v3, etap 1) ---
from evaluation import RaceLevels  # noqa: E402
from oos import gate_verdict, level_report, walk_forward_levels  # noqa: E402
from scoring import Diff  # noqa: E402


def lv(pre, post, quali=None):
    return RaceLevels(round=1, rps_pre=pre, rps_post=post, rps_quali=quali, brier_win_post=0.0)


def test_gate_verdict_keeps_a_clear_improvement_on_both_levels():
    base = [lv(0.20 + 0.01 * i, 0.18 + 0.01 * i) for i in range(10)]
    better = [lv(x.rps_pre - 0.03, x.rps_post - 0.03) for x in base]
    verdict, diffs = gate_verdict(better, base)
    assert verdict == "keep" and diffs["pre"].hi < 0 and diffs["post"].hi < 0


def test_gate_verdict_drops_a_clear_worsening():
    base = [lv(0.20 + 0.01 * i, 0.18 + 0.01 * i) for i in range(10)]
    worse = [lv(x.rps_pre + 0.03, x.rps_post + 0.03) for x in base]
    assert gate_verdict(worse, base)[0] == "drop"


def test_gate_verdict_is_inconclusive_when_the_difference_is_noise():
    base = [lv(0.2, 0.2) for _ in range(8)]
    noisy = [lv(0.2 + (0.05 if i % 2 else -0.05), 0.2 + (0.05 if i % 2 else -0.05)) for i in range(8)]
    assert gate_verdict(noisy, base)[0] == "inconclusive"


def test_gate_verdict_drops_when_one_level_gets_clearly_worse_even_if_the_other_improves():
    base = [lv(0.20 + 0.01 * i, 0.20 + 0.01 * i) for i in range(10)]
    mixed = [lv(x.rps_pre - 0.03, x.rps_post + 0.03) for x in base]
    assert gate_verdict(mixed, base)[0] == "drop"


def test_walk_forward_levels_gives_race_levels_per_test_season():
    out = walk_forward_levels(CASES, [2024, 2025], BASE, BOUNDS, set(), n=300)
    assert sorted(out) == [2024, 2025] and all(len(v) == 8 for v in out.values())
    assert all(isinstance(x, RaceLevels) and x.rps_quali is None for v in out.values() for x in v)


def test_level_report_compares_base_tuned_and_grid_only():
    informative = {**BASE, "signal": 1.0, "noise": 0.0}                       # bazowe wagi dobrego czynnika
    report = level_report(CASES, [2024, 2025], informative, BOUNDS, {"noise"}, n=300)
    assert set(report["levels"]) == {"base", "tuned", "grid_only", "shared"}
    assert all(len(v) == 16 for v in report["levels"].values())
    assert report["diffs"]["base_vs_grid_only"]["post"].mean < 0       # siła z czynników pomaga względem samej siatki
    assert isinstance(report["diffs"]["tuned_vs_base"]["pre"], Diff)


def test_write_oos_stores_the_new_level_means(tmp_path):
    path = tmp_path / "oos.json"
    write_oos(path, {2024: 0.025}, levels={2024: [lv(0.2, 0.1, 0.3), lv(0.4, 0.3, None)]})
    row = json.loads(path.read_text())[0]
    assert row["rps_pre"] == pytest.approx(0.3) and row["rps_post"] == pytest.approx(0.2) and row["rps_quali"] == pytest.approx(0.3)


# --- szum kwalifikacji i porównanie osobne vs wspólne (model v3, etap 2) ---
from oos import quali_noise_scan  # noqa: E402


def test_quali_noise_scan_prefers_less_noise_when_the_strength_is_right():
    qcase = case(1, "d1")
    from dataclasses import replace
    qcase = replace(qcase, factor_scores={"signal": {d: 5.0 - 3 * i for i, d in enumerate(DRIVERS)}},
                    actual_quali={d: i + 1 for i, d in enumerate(DRIVERS)})
    weights = {"q_signal": 1.0, "quali_noise": 0.8, "grid_base_weight": 0.9, "race_noise_base": 0.5}
    scan = quali_noise_scan([qcase], weights, [0.1, 0.8, 1.5], n=600)
    assert sorted(scan) == [0.1, 0.8, 1.5] and scan[0.1] < scan[1.5]


def test_level_report_also_compares_separate_with_shared_strengths():
    report = level_report(CASES, [2024], {**BASE, "q_signal": 1.0}, BOUNDS, {"noise"}, n=200)
    assert "shared" in report["levels"] and len(report["levels"]["shared"]) == 8
    assert isinstance(report["diffs"]["separate_vs_shared"]["post"], Diff)


# --- warianty wag i dobór hiperparametrów ocen (model v3, etap 3) ---
from oos import VARIANTS, rating_scan, variant_gate  # noqa: E402


def test_variant_gate_keeps_a_clearly_better_weight_set_and_drops_a_worse_one():
    base = {**BASE, "signal": 0.0, "noise": 0.5}
    verdict_good, _ = variant_gate(CASES, [2024, 2025], base, {"signal": 1.0, "noise": 0.0}, n=300)
    verdict_bad, _ = variant_gate(CASES, [2024, 2025], {**base, "signal": 1.0, "noise": 0.0}, {"signal": 0.0, "noise": 1.0}, n=300)
    assert verdict_good == "keep" and verdict_bad == "drop"


def test_named_variants_exist_and_only_touch_known_weights():
    import config
    assert {"rating_race", "rating_race_plus"} <= set(VARIANTS)
    for overrides in VARIANTS.values():
        assert set(overrides) <= set(config.default_weights())


def test_rating_scan_returns_a_finite_score_for_every_combination():
    from evaluation import prepare_rounds
    from fakes import clients
    import math

    cases = prepare_rounds(2027, clients())
    grid = [{"eta_car": 0.05, "eta_driver": 0.05, "car_keep": 0.6}, {"eta_car": 0.3, "eta_driver": 0.1, "car_keep": 0.9}]
    weights = {k: 0.0 for k in __import__("config").default_weights()} | {"rating_race": 1.0, "grid_base_weight": 0.9,
                                                                         "race_noise_base": 0.5, "quali_noise": 0.7}
    out = rating_scan(cases, weights, grid, n=200)
    assert len(out) == 2 and all(math.isfinite(v["pre"]) and math.isfinite(v["post"]) for v in out.values())


# --- diagnostyka ogonów i skan losowości (model v3, etap 4) ---
from oos import noise_scan, tail_report  # noqa: E402


def test_levels_include_the_winner_log_loss():
    out = walk_forward_levels(CASES, [2024], BASE, BOUNDS, set(), n=300)[2024]
    assert all(0 <= x.logloss_win_pre <= 7 and 0 <= x.logloss_win_post <= 7 for x in out)   # 7 ~ -ln(0,001)


def test_tail_report_counts_longshot_wins_and_favourite_calibration():
    weights = {**BASE, "signal": 1.0, "noise": 0.0}
    report = tail_report(CASES[2024], weights, n=500)
    for level in ("pre", "post"):
        r = report[level]
        assert set(r) == {"races", "longshot_expected", "longshot_actual", "fav_n", "fav_pred", "fav_actual"}
        assert r["races"] == 8 and 0 <= r["longshot_actual"] <= 8 and r["longshot_expected"] >= 0


def test_noise_scan_returns_every_metric_for_every_combination():
    grid = [{"team_noise_share": 0.0, "chaos_base": 0.0, "chaos_mult": 2.0}, {"team_noise_share": 0.4, "chaos_base": 0.2, "chaos_mult": 3.0}]
    out = noise_scan(CASES[2024], {**BASE, "signal": 1.0, "noise": 0.0}, grid, n=300)
    assert len(out) == 2
    for row in out.values():
        assert {"rps_pre", "rps_post", "logloss_pre", "logloss_post", "tails"} <= set(row)


# --- bramka parametrów ocen (model v3, etap 6) ---
from oos import rating_param_gate  # noqa: E402


def test_rating_param_gate_returns_a_verdict_with_intervals_for_two_parameter_sets():
    from evaluation import prepare_rounds
    from fakes import clients
    cases = {2027: prepare_rounds(2027, clients())}
    weights = {k: 0.0 for k in __import__("config").default_weights()} | {"rating_race": 1.0, "grid_base_weight": 0.9,
                                                                         "race_noise_base": 0.5, "quali_noise": 0.7}
    verdict_, diffs = rating_param_gate(cases, [2027], weights, {"trend_gain": 2.0, "trend_alpha": 0.5}, {}, n=200)
    assert verdict_ in ("keep", "drop", "inconclusive") and {"pre", "post"} <= set(diffs)
