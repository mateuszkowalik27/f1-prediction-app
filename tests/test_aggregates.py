import pytest

from aggregates import compute_pit_deltas, link_session_gaps
from schemas import PitStop, QualiTimes


def qt(driver, q1=None, q2=None, q3=None):
    return QualiTimes(driver_id=driver, q1=q1, q2=q2, q3=q3)


SESSIONS = [
    qt("A", 80.0, 79.0, 78.0), qt("B", 80.4, 79.5, 78.6),   # Q3
    qt("C", 80.8, 79.9),                                    # odpadł w Q2
    qt("D", 81.5),                                          # odpadł w Q1
]


def test_chain_links_sessions():
    gaps = link_session_gaps(SESSIONS)
    assert gaps["A"] == pytest.approx(0.0)
    assert gaps["B"] == pytest.approx(0.769, abs=0.01)       # z Q3
    assert gaps["C"] == pytest.approx(1.207, abs=0.01)       # Q2 + δ(2→3)
    assert gaps["D"] == pytest.approx(2.076, abs=0.01)       # Q1 + δ(1→2) + δ(2→3)


def test_slower_drivers_always_get_larger_gap():
    gaps = link_session_gaps(SESSIONS)
    assert gaps["A"] < gaps["B"] < gaps["C"] < gaps["D"]


def test_only_q1_when_later_sessions_missing():
    gaps = link_session_gaps([qt("A", 80.0), qt("B", 80.8)])
    assert gaps == {"A": pytest.approx(0.0), "B": pytest.approx(1.0)}


def test_q1_and_q2_only_when_q3_missing():
    gaps = link_session_gaps([qt("A", 80.0, 79.0), qt("B", 80.4, 79.5), qt("C", 81.0)])
    assert gaps["A"] == pytest.approx(0.0) and gaps["B"] == pytest.approx(0.633, abs=0.01)
    assert gaps["C"] > gaps["B"]


def test_driver_without_times_omitted_and_empty_input_ok():
    gaps = link_session_gaps([qt("A", 80.0), qt("X")])
    assert set(gaps) == {"A"}
    assert link_session_gaps([]) == {}


TEAM_OF = {"a1": "t1", "a2": "t1", "b1": "t2", "b2": "t2", "c1": "t3", "c2": "t3", "d1": "t4"}


def stops(*pairs):
    return [PitStop(driver_id=d, lap=10 + i, duration_s=s) for i, (d, s) in enumerate(pairs)]


BASE = [("a1", 23.0), ("a2", 23.4), ("b1", 25.0), ("b2", 25.4), ("c1", 24.0), ("c2", 24.2)]


def test_pit_delta_is_team_median_vs_race_median():
    d = compute_pit_deltas(stops(*BASE), TEAM_OF)
    assert d["t1"] == pytest.approx(-0.9) and d["t2"] == pytest.approx(1.1) and d["t3"] == pytest.approx(0.0)


def test_pit_outlier_dropped():
    with_outlier = compute_pit_deltas(stops(*BASE, ("a1", 60.0)), TEAM_OF)   # 60 s: czerwona flaga / kara
    assert with_outlier == pytest.approx(compute_pit_deltas(stops(*BASE), TEAM_OF))


def test_team_with_one_stop_omitted():
    d = compute_pit_deltas(stops(*BASE, ("d1", 24.0)), TEAM_OF)
    assert "t4" not in d


def test_unknown_driver_ignored_and_empty_inputs_give_empty_dict():
    assert "x" not in compute_pit_deltas(stops(*BASE, ("zz", 24.0)), TEAM_OF)
    assert compute_pit_deltas([], TEAM_OF) == {}
