import math

import config
from factors.race_vs_quali import RaceVsQuali
from helpers import make_agg, make_ctx, make_entries


def ctx(aggs, entries=None):
    return make_ctx(entries=entries, aggregates=aggs)


def races(quali, pace, n=3):
    return [make_agg(2027, i + 1, quali_gap=quali, race_pace=pace) for i in range(n)]


def test_driver_faster_on_sunday_than_saturday_scores_higher():
    # A: pole, ale w wyścigu wolniejszy od stawki; B: wolniejszy w kwalifikacjach, a w wyścigu szybszy
    s = RaceVsQuali().score(ctx(races({"d1": 0.0, "d2": 1.0}, {"d1": 0.5, "d2": -0.5})))
    assert s["d2"] > s["d1"]


def test_quali_gap_is_made_relative_to_field_median():
    base = RaceVsQuali().score(ctx(races({"d1": 0.0, "d2": 1.0, "d3": 2.0}, {"d1": -0.4, "d2": 0.0, "d3": 0.4})))
    shifted = RaceVsQuali().score(ctx(races({"d1": 2.0, "d2": 3.0, "d3": 4.0}, {"d1": -0.4, "d2": 0.0, "d3": 0.4})))
    assert all(abs(base[d] - shifted[d]) < 1e-9 for d in base)          # stała dodana do wszystkich nic nie zmienia


def test_driver_with_few_races_is_shrunk_towards_zero():
    entries = make_entries(("vet", "t"), ("new", "t"), ("mid", "t"))
    aggs = [make_agg(2027, i + 1, quali_gap={"vet": 0.0, "mid": 0.5, "new": 0.0},
                     race_pace={"vet": -2.0, "mid": 0.0, "new": -3.0}) for i in range(3)]
    # vet jeździł 12 wyścigów z przewagą +2, new tylko 3 z +3: surowo new > vet, po ściągnięciu vet > new
    aggs += [make_agg(2026, i + 1, quali_gap={"vet": 0.0, "mid": 0.5}, race_pace={"vet": -2.0, "mid": 0.0}) for i in range(9)]
    s = RaceVsQuali().score(ctx(aggs, entries))
    assert config.RACEQ_SHRINK_K == 4 and s["vet"] > s["new"]


def test_extreme_race_pace_is_clipped():
    assert config.RACE_PACE_CLIP == 5.0
    a = RaceVsQuali().score(ctx(races({"d1": 0.0, "d2": 0.5, "d3": 1.0}, {"d1": -0.5, "d2": 0.0, "d3": 15.0})))
    b = RaceVsQuali().score(ctx(races({"d1": 0.0, "d2": 0.5, "d3": 1.0}, {"d1": -0.5, "d2": 0.0, "d3": 5.0})))
    assert a == b


def test_none_when_race_pace_missing_or_too_few_races():
    assert RaceVsQuali().score(ctx([make_agg(2022, i + 1, quali_gap={"d1": 0.0, "d2": 1.0}) for i in range(5)])) is None   # 2022: bez tempa
    assert RaceVsQuali().score(ctx(races({"d1": 0.0, "d2": 1.0}, {"d1": 0.0, "d2": 0.0}, n=2))) is None
    assert RaceVsQuali().score(ctx([])) is None


def test_scores_are_finite():
    s = RaceVsQuali().score(ctx(races({"d1": 0.0, "d2": 1.0}, {"d1": 0.0, "d2": 0.0})))
    assert all(math.isfinite(v) for v in s.values())
