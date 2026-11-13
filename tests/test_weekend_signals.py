import pytest

from schemas import LapRecord
from weekend_signals import gap_percent, long_run_pace, quali_sim_pace


def lap(driver, n, secs, compound="MEDIUM", age=None, pit_out=False):
    return LapRecord(driver_id=driver, lap=n, duration_s=secs, is_pit_out=pit_out, compound=compound,
                     tyre_age=(n - 1) if age is None else age)


def stint(driver, start, count, base, compound="MEDIUM", deg=0.0, fuel=0.0):
    """Stint z paliwem (okrążenia szybsze o `fuel` s na okrążenie) i zużyciem opon (`deg` s na okrążenie)."""
    return [lap(driver, start + i, base - fuel * i + deg * i, compound, age=i) for i in range(count)]


def test_faster_long_run_gets_a_negative_percentage():
    laps = stint("fast", 3, 8, 90.0) + stint("slow", 3, 8, 91.0)
    pace = long_run_pace(laps)
    assert pace["fast"] < 0 < pace["slow"]


def test_too_short_stint_is_ignored():
    laps = stint("fast", 3, 8, 90.0) + stint("slow", 3, 8, 91.0) + stint("short", 3, 3, 80.0)
    assert "short" not in long_run_pace(laps)


def test_fuel_correction_removes_the_advantage_of_a_later_stint_start():
    # ten sam kierowca/tempo: fuel=0,035 powoduje, że kolejne okrążenia są szybsze; po korekcie tempo ma być płaskie
    laps = stint("a", 3, 8, 90.0, fuel=0.035) + stint("b", 3, 8, 90.0, fuel=0.035)
    pace = long_run_pace(laps)
    assert abs(pace["a"] - pace["b"]) < 1e-9


def test_slow_laps_in_a_stint_are_dropped():
    laps = stint("a", 3, 8, 90.0) + stint("b", 3, 8, 90.0)
    laps[3] = lap("a", 6, 120.0, age=3)                      # jedno okrążenie z ruchem / błędem w środku stintu
    assert abs(long_run_pace(laps)["a"]) < 0.05              # bez niego tempo prawie równe b (zostaje drobna różnica od korekty na paliwo)


def test_compound_offset_makes_drivers_on_different_tyres_comparable():
    laps = (stint("a", 3, 8, 90.0, "MEDIUM") + stint("a", 14, 8, 91.0, "HARD")
            + stint("b", 3, 8, 90.5, "MEDIUM") + stint("b", 14, 8, 91.5, "HARD")
            + stint("c", 3, 8, 91.5, "HARD"))                # c jeździ tylko na twardych
    pace = long_run_pace(laps)
    assert pace["a"] < pace["b"]
    assert pace["c"] > pace["b"] or pace["c"] > pace["a"]


def test_quali_sim_uses_the_best_clean_lap_after_compound_offset():
    laps = ([lap("a", 5, 80.0, "SOFT"), lap("a", 6, 85.0, "SOFT"), lap("a", 7, 79.0, "SOFT", pit_out=True)]
            + [lap("b", 5, 80.5, "SOFT")] + [lap("c", 5, 81.0, "MEDIUM"), lap("a", 9, 80.8, "MEDIUM")])
    pace = quali_sim_pace(laps)
    assert pace["a"] < pace["b"]                              # a: 80,0 na SOFT (okrążenie wyjazdowe 79,0 się nie liczy)


def test_gap_percent_zero_for_the_fastest_and_positive_for_the_rest():
    gaps = gap_percent({"a": 80.0, "b": 80.8, "c": 82.4})
    assert gaps["a"] == 0 and gaps["b"] == pytest.approx(1.0) and gaps["c"] == pytest.approx(3.0)
    assert gap_percent({}) == {}
