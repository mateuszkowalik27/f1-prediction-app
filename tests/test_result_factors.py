from factors.car_pace import CarPace, team_result_z
from factors.driver_form import DriverForm
from factors.reliability import Reliability, dnf_rates
from factors.track_history import TrackHistory
from helpers import hist_race, make_ctx

STRONG_T1 = [("d1", "t1", 1), ("d2", "t1", 2), ("d3", "t2", 3), ("d4", "t2", 4)]


def test_car_pace_ranks_strongest_team_first():
    ctx = make_ctx(history=[hist_race(2027, r, STRONG_T1) for r in (1, 2, 3)])
    scores = CarPace().score(ctx)
    assert scores["d1"] > scores["d3"]
    assert scores["d1"] == scores["d2"]  # ten sam bolid


def test_car_pace_none_without_history():
    assert CarPace().score(make_ctx()) is None


def test_team_result_z_higher_for_team_with_more_points():
    z = team_result_z(make_ctx(), hist_race(2027, 1, STRONG_T1))
    assert z["t1"] > z["t2"]


def test_driver_form_uses_only_last_five_rounds():
    early = [("d1", "t1", 1), ("d2", "t1", 2), ("d3", "t2", 3), ("d4", "t2", 4)]
    late = [("d1", "t1", None), ("d2", "t1", 2), ("d3", "t2", 3), ("d4", "t2", 4)]
    history = [hist_race(2027, r, early) for r in (1, 2)] + [hist_race(2027, r, late) for r in (3, 4, 5, 6, 7)]
    scores = DriverForm().score(make_ctx(history=history))
    assert scores["d2"] > scores["d1"]   # wygrane z rund 1-2 nie liczą się do ostatnich pięciu


def test_track_history_none_without_history():
    assert TrackHistory().score(make_ctx()) is None


def test_track_history_skips_driver_with_no_starts():
    rows = [("d1", "t1", 1), ("d2", "t1", 5)]
    ctx = make_ctx(circuit_history=[hist_race(2026, 5, rows), hist_race(2025, 5, rows)])
    scores = TrackHistory().score(ctx)
    assert set(scores) == {"d1", "d2"}
    assert scores["d1"] > scores["d2"]


def test_reliability_penalizes_high_dnf_team():
    flaky = [("d1", "t1", None), ("d2", "t1", None), ("d3", "t2", 1), ("d4", "t2", 2)]
    ctx = make_ctx(history=[hist_race(2027, r, flaky) for r in (1, 2, 3)])
    scores = Reliability().score(ctx)
    assert scores["d1"] < scores["d3"]


def test_dnf_rates_in_0_1_for_rookie():
    from helpers import make_entries
    entries = make_entries(("d1", "t1"), ("d3", "t2"), ("rookie", "t2"))
    flaky = [("d1", "t1", None), ("d3", "t2", 1)]
    rates = dnf_rates(make_ctx(entries=entries, history=[hist_race(2027, r, flaky) for r in (1, 2, 3)]))
    assert set(rates) == {"d1", "d3", "rookie"}
    assert all(0.0 <= v <= 1.0 for v in rates.values())
    assert rates["d1"] > rates["d3"]
