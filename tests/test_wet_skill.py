from datetime import datetime, timezone

import pytest

import config
from factors.wet_skill import WetSkill, compute_wet_skill
from helpers import hist_race, make_ctx, make_entries
from schemas import WeatherForecast

DRY_ORDER = [("d1", "t1", 1), ("d2", "t1", 2), ("d3", "t2", 3), ("d4", "t2", 4)]
WET_ORDER = [("d1", "t1", 2), ("d2", "t1", 1), ("d3", "t2", 3), ("d4", "t2", 4)]  # d2 lepszy od partnera w deszczu


def season(n_wet, n_dry=4):
    races, wet = [], {}
    for r in range(1, n_dry + 1):
        races.append(hist_race(2027, r, DRY_ORDER))
        wet[(2027, r)] = False
    for r in range(n_dry + 1, n_dry + n_wet + 1):
        races.append(hist_race(2027, r, WET_ORDER))
        wet[(2027, r)] = True
    return races, wet


def forecast(rain):
    return WeatherForecast(rain_probability=rain, temperature_c=18.0, fetched_at=datetime.now(timezone.utc))


def test_teammate_comparison_removes_car_effect():
    races, wet = season(n_wet=2)
    skill = compute_wet_skill(races, wet, make_ctx().entries)
    assert skill["d2"] > 0 > skill["d1"]
    assert skill["d3"] == 0 and skill["d4"] == 0   # ten sam układ w suchym i mokrym: bolid nie daje punktów


def test_rookie_gets_zero():
    races, wet = season(n_wet=2)
    entries = make_entries(("d1", "t1"), ("rookie", "t9"))
    assert compute_wet_skill(races, wet, entries)["rookie"] == 0.0


def test_shrinks_with_few_wet_races():
    entries = make_ctx().entries
    one = compute_wet_skill(*season(n_wet=1), entries)["d2"]
    three = compute_wet_skill(*season(n_wet=3), entries)["d2"]
    k = config.WET_SHRINK_K
    assert one == pytest.approx(2 * 1 / (1 + k))
    assert three == pytest.approx(2 * 3 / (3 + k))
    assert three > one


def factor_ctx(rain, n_wet=2):
    races, wet = season(n_wet)
    return make_ctx(history=races, wet=wet, weather=None if rain is None else forecast(rain))


def test_none_when_dry_forecast():
    assert WetSkill().score(factor_ctx(rain=0.1)) is None


def test_none_without_forecast():
    assert WetSkill().score(factor_ctx(rain=None)) is None


def test_none_without_wet_races_in_history():
    assert WetSkill().score(factor_ctx(rain=0.8, n_wet=0)) is None


def test_scores_wet_specialist_higher():
    scores = WetSkill().score(factor_ctx(rain=0.8))
    assert scores["d2"] > scores["d1"]


def test_override_wins(monkeypatch):
    monkeypatch.setattr(config, "WET_SKILL_OVERRIDES", {"d4": 10.0})
    scores = WetSkill().score(factor_ctx(rain=0.8))
    assert scores["d4"] == max(scores.values())
