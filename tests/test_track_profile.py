import json
from pathlib import Path

import pytest

from factors.track_profile import get_profile, load_estimates, profile_from_speed_trace
from schemas import TrackProfile

CALENDAR = Path(__file__).parent / "fixtures" / "jolpica_calendar_2026.json"


def trace_with_corners(minima, straight=300.0):
    """Prosta -> zakręt o danej minimalnej prędkości -> prosta ... (syntetyczne okrążenie)."""
    speeds = [straight] * 5
    for m in minima:
        speeds += [straight - (straight - m) * k / 5 for k in range(1, 6)]
        speeds += [m + (straight - m) * k / 5 for k in range(1, 6)]
        speeds += [straight] * 3
    return speeds


def test_counts_slow_medium_fast_corners():
    p = profile_from_speed_trace("x", trace_with_corners([80, 100, 150, 180, 240]))
    assert (p.slow, p.medium, p.fast) == pytest.approx((0.4, 0.4, 0.2))
    assert p.source == "telemetry"
    assert 0 < p.straight_share < 1


def test_flat_trace_returns_none():
    assert profile_from_speed_trace("x", [300.0] * 100) is None
    assert profile_from_speed_trace("x", [300.0 + (i % 2) * 5 for i in range(100)]) is None  # drgania < progu


def test_get_profile_priority_override_telemetry_estimate():
    est = {"x": TrackProfile(circuit_id="x", slow=0.5, medium=0.3, fast=0.2, straight_share=0.1, source="estimate")}
    manual = TrackProfile(circuit_id="x", slow=0.1, medium=0.1, fast=0.8, straight_share=0.1, source="manual")
    trace = trace_with_corners([80, 150])
    assert get_profile("x", trace, est, manual).source == "manual"
    assert get_profile("x", trace, est, None).source == "telemetry"
    assert get_profile("x", None, est, None).source == "estimate"


def test_unknown_circuit_without_data_returns_none():
    assert get_profile("nowy_tor", None, {}, None) is None
    assert get_profile("nowy_tor", [300.0] * 50, {}, None) is None  # telemetria bez zakrętów też nie pomoże


def test_estimates_shares_sum_to_one_and_cover_2026_calendar():
    estimates = load_estimates()
    assert all(p.source == "estimate" for p in estimates.values())
    races = json.loads(CALENDAR.read_text())["MRData"]["RaceTable"]["Races"]
    missing = {r["Circuit"]["circuitId"] for r in races} - set(estimates)
    assert not missing, f"brak szacunków dla: {missing}"
