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


# --- tempo wyścigowe i zużycie opon ---
from aggregates import compute_race_pace, compute_tyre_deg   # noqa: E402
from schemas import LapRecord                                  # noqa: E402


def lap(driver, n, dur, pit_out=False, compound="MEDIUM", age=None):
    return LapRecord(driver_id=driver, lap=n, duration_s=dur, is_pit_out=pit_out, compound=compound,
                     tyre_age=age if age is not None else n - 1)


def steady(driver, seconds, laps=range(1, 13)):
    return [lap(driver, n, 100.0 if n == 1 else seconds) for n in laps]


def test_race_pace_drops_lap_one_pit_laps_and_slow_laps():
    laps = steady("A", 90.0)
    laps[4] = lap("A", 5, 120.0)                       # safety car / błąd: >107% mediany
    laps[6] = lap("A", 7, 96.0)                        # okrążenie wjazdowe (przed wyjazdem z boksu)
    laps[7] = lap("A", 8, 95.0, pit_out=True)          # okrążenie wyjazdowe
    pace = compute_race_pace(laps + steady("B", 91.0))
    assert pace["A"] == pytest.approx((90.0 / 90.5 - 1) * 100)      # tylko czyste okrążenia po 90,0
    assert pace["B"] == pytest.approx((91.0 / 90.5 - 1) * 100)


def test_race_pace_negative_is_faster():
    pace = compute_race_pace(steady("A", 90.0) + steady("B", 91.0))
    assert pace["A"] < 0 < pace["B"]


def test_driver_with_few_clean_laps_omitted():
    pace = compute_race_pace(steady("A", 90.0) + steady("B", 91.0) + steady("C", 92.0, laps=range(1, 5)))
    assert "C" not in pace


def test_race_pace_empty_input():
    assert compute_race_pace([]) == {}


def stint_laps(driver, slope, compound="MEDIUM", laps=range(2, 14)):
    """t = 90 + slope * wiek - paliwo * okrążenie: po korekcie na paliwo nachylenie = slope."""
    return [lap(driver, n, 90 + slope * (n - 1) - 0.035 * n, compound=compound, age=n - 1) for n in laps]


TEAMS = {"d1": "t1", "d2": "t2", "d3": "t3", "d4": "t4"}


def test_tyre_deg_recovers_known_slope_relative_to_field():
    deg, track = compute_tyre_deg(stint_laps("d1", 0.1) + stint_laps("d2", 0.2), TEAMS)
    assert deg["t1"] == pytest.approx(-0.05, abs=1e-6) and deg["t2"] == pytest.approx(0.05, abs=1e-6)
    assert track == pytest.approx(0.15, abs=1e-6)


def test_short_stints_ignored():
    deg, _ = compute_tyre_deg(stint_laps("d1", 0.1) + stint_laps("d2", 0.2) + stint_laps("d3", 0.5, laps=range(2, 7)), TEAMS)
    assert "t3" not in deg


def test_team_deg_relative_to_same_compound_median():
    laps = (stint_laps("d1", 0.10) + stint_laps("d2", 0.20)                       # średnie: mediana 0,15
            + stint_laps("d3", 0.05, compound="HARD") + stint_laps("d4", 0.07, compound="HARD"))   # twarde: mediana 0,06
    deg, _ = compute_tyre_deg(laps, TEAMS)
    assert deg["t3"] == pytest.approx(-0.01, abs=1e-6) and deg["t4"] == pytest.approx(0.01, abs=1e-6)
    assert deg["t1"] == pytest.approx(-0.05, abs=1e-6)                             # nie miesza się z twardymi


def test_no_valid_stints_gives_empty_and_none():
    assert compute_tyre_deg([], TEAMS) == ({}, None)
    assert compute_tyre_deg(steady("d1", 90.0, laps=range(1, 5)), TEAMS) == ({}, None)
