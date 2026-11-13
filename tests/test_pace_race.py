import math

import config
from factors.pace_race import PaceRace
from helpers import make_agg, make_ctx, make_entries

ENTRIES = make_entries(("fast", "t1"), ("mid", "t2"), ("slow", "t3"))


def ctx(pace_list, **kw):
    aggs = [make_agg(2027, i + 1, race_pace=p) for i, p in enumerate(pace_list)]
    return make_ctx(entries=kw.pop("entries", ENTRIES), aggregates=aggs, **kw)


def test_faster_driver_scores_higher():
    s = PaceRace().score(ctx([{"fast": -1.0, "mid": 0.0, "slow": 1.5}] * 4))
    assert s["fast"] > s["mid"] > s["slow"]


def test_none_without_enough_aggregates_with_pace():
    assert PaceRace().score(ctx([{"fast": -1.0, "mid": 0.0}] * (config.AGGREGATE_MIN_RACES - 1))) is None
    assert PaceRace().score(ctx([{}] * 5)) is None


def test_extreme_pace_is_clipped_and_values_are_finite():
    s = PaceRace().score(ctx([{"fast": -1.0, "mid": 0.0, "slow": 80.0}] * 4))     # uszkodzone auto: 80% wolniej
    assert all(math.isfinite(v) for v in s.values())
    clipped = PaceRace().score(ctx([{"fast": -1.0, "mid": 0.0, "slow": config.RACE_PACE_CLIP}] * 4))
    assert s == clipped


def test_driver_with_one_race_is_shrunk_towards_zero():
    base = {"fast": -1.0, "mid": 0.0, "slow": 1.5}
    entries = ENTRIES + make_entries(("rookie", "t4"))
    one = PaceRace().score(ctx([base] * 5 + [{**base, "rookie": -3.0}], entries=entries))
    six = PaceRace().score(ctx([{**base, "rookie": -3.0}] * 6, entries=entries))
    assert one["rookie"] > 0 and abs(one["rookie"]) < abs(six["rookie"])      # ta sama prędkość, mniej pewności


def test_retired_drivers_do_not_shift_the_field_average():
    entries = make_entries(("fast", "t1"), ("slow", "t3"))
    s = PaceRace().score(ctx([{"fast": -1.0, "slow": 1.0, "gone": 4.0}] * 4, entries=entries))
    assert abs(s["fast"] + s["slow"]) < 1e-9
