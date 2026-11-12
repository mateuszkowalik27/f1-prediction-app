import pytest

import config
from factors.car_track_fit import CarTrackFit
from helpers import hist_race, make_ctx
from schemas import TrackProfile

FAST = TrackProfile(circuit_id="", slow=0.1, medium=0.2, fast=0.7, straight_share=0.1, source="telemetry")
SLOW = TrackProfile(circuit_id="", slow=0.7, medium=0.2, fast=0.1, straight_share=0.1, source="telemetry")
T1_BETTER = [("d1", "t1", 1), ("d2", "t1", 2), ("d3", "t2", 3), ("d4", "t2", 4)]
T2_BETTER = [("d3", "t2", 1), ("d4", "t2", 2), ("d1", "t1", 3), ("d2", "t1", 4)]


def season(n_each=4):
    """t1 jest mocny na szybkich torach, t2 na wolnych."""
    history, profiles = [], {}
    for i in range(n_each):
        history.append(hist_race(2027, 2 * i + 1, T1_BETTER, circuit_id=f"fast{i}"))
        profiles[f"fast{i}"] = FAST.model_copy(update={"circuit_id": f"fast{i}"})
        history.append(hist_race(2027, 2 * i + 2, T2_BETTER, circuit_id=f"slow{i}"))
        profiles[f"slow{i}"] = SLOW.model_copy(update={"circuit_id": f"slow{i}"})
    return history, profiles


def ctx_for(current, n_each=4):
    history, profiles = season(n_each)
    return make_ctx(history=history, profiles=profiles, profile=current)


def test_team_strong_on_fast_corners_scores_higher_on_fast_track():
    on_fast = CarTrackFit().score(ctx_for(FAST))
    on_slow = CarTrackFit().score(ctx_for(SLOW))
    assert on_fast["d1"] > on_fast["d3"]
    assert on_slow["d3"] > on_slow["d1"]


def test_none_below_min_races():
    assert config.FIT_MIN_RACES == 6
    assert CarTrackFit().score(ctx_for(FAST, n_each=2)) is None   # 4 rundy z profilem < 6


def test_none_without_current_profile():
    assert CarTrackFit().score(ctx_for(None)) is None


def test_ridge_shrinks_small_effects(monkeypatch):
    strong = abs(CarTrackFit().score(ctx_for(FAST))["d1"])
    monkeypatch.setattr(config, "FIT_RIDGE", 50.0)
    shrunk = abs(CarTrackFit().score(ctx_for(FAST))["d1"])
    assert shrunk < strong
