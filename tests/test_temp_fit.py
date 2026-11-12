import math
from datetime import datetime, timezone

import config
from factors.temp_fit import TempFit
from helpers import hist_race, make_agg, make_ctx, make_entries
from schemas import WeatherForecast

ENTRIES = make_entries(("d1", "t1"), ("d3", "t2"))
T1_BETTER = [("d1", "t1", 1), ("d3", "t2", 2)]
T2_BETTER = [("d3", "t2", 1), ("d1", "t1", 2)]


def season(n_hot=4, n_cold=4):
    """t1 jest mocny w upale (35 C), t2 w chłodzie (12 C)."""
    history, aggs, rnd = [], [], 0
    for _ in range(n_hot):
        rnd += 1
        history.append(hist_race(2026, rnd, T1_BETTER))
        aggs.append(make_agg(2026, rnd, air_temp_c=35.0))
    for _ in range(n_cold):
        rnd += 1
        history.append(hist_race(2026, rnd, T2_BETTER))
        aggs.append(make_agg(2026, rnd, air_temp_c=12.0))
    return history, aggs


def ctx(temp, history=None, aggs=None):
    h, a = season()
    weather = None if temp is None else WeatherForecast(rain_probability=0.0, temperature_c=temp,
                                                        fetched_at=datetime(2027, 1, 1, tzinfo=timezone.utc),
                                                        start_temperature_c=temp)
    return make_ctx(entries=ENTRIES, history=history or h, aggregates=aggs or a, weather=weather)


def test_team_strong_in_heat_scores_higher_on_hot_forecast():
    hot, cold = TempFit().score(ctx(35.0)), TempFit().score(ctx(12.0))
    assert hot["d1"] > hot["d3"] and cold["d3"] > cold["d1"]


def test_none_without_start_temperature():
    assert TempFit().score(ctx(None)) is None
    no_start = make_ctx(entries=ENTRIES, history=season()[0], aggregates=season()[1],
                        weather=WeatherForecast(rain_probability=0.0, temperature_c=20.0,
                                                fetched_at=datetime(2027, 1, 1, tzinfo=timezone.utc)))
    assert TempFit().score(no_start) is None


def test_none_below_min_races():
    h, a = season(n_hot=3, n_cold=2)                       # 5 < FIT_MIN_RACES = 6
    assert config.FIT_MIN_RACES == 6 and TempFit().score(ctx(35.0, h, a)) is None


def test_races_without_air_temp_are_ignored():
    h, a = season()
    a = [x.model_copy(update={"air_temp_c": None}) if i % 2 == 0 else x for i, x in enumerate(a)]   # połowa bez temperatury
    assert TempFit().score(ctx(35.0, h, a)) is None


def test_ridge_shrinks_small_effects(monkeypatch):
    strong = abs(TempFit().score(ctx(35.0))["d1"])
    monkeypatch.setattr(config, "FIT_RIDGE", 50.0)
    assert abs(TempFit().score(ctx(35.0))["d1"]) < strong


def test_scores_are_finite_and_extreme_forecast_is_bounded():
    s = TempFit().score(ctx(80.0))                          # absurdalna prognoza: obcięte do +-2 odchyleń
    assert all(math.isfinite(v) for v in s.values())
    assert abs(s["d1"]) <= abs(TempFit().score(ctx(35.0))["d1"]) * 3
