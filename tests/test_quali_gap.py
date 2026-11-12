import math

import config
from factors.quali_gap import QualiGap
from helpers import make_agg, make_ctx, make_entries

GAPS = {"d1": 0.0, "d2": 0.5, "d3": 1.0, "d4": 2.0}


def ctx(aggs, **kw):
    return make_ctx(aggregates=aggs, **kw)


def aggs_of(*gap_dicts):
    return [make_agg(2027, i + 1, quali_gap=g) for i, g in enumerate(gap_dicts)]


def test_smaller_gap_scores_higher():
    s = QualiGap().score(ctx(aggs_of(GAPS, GAPS, GAPS)))
    assert s["d1"] > s["d2"] > s["d3"] > s["d4"]


def test_recent_races_weigh_more():
    favours_d1 = {"d1": 0.0, "d2": 2.0, "d3": 1.0, "d4": 1.0}
    favours_d2 = {"d1": 2.0, "d2": 0.0, "d3": 1.0, "d4": 1.0}
    s = QualiGap().score(ctx(aggs_of(favours_d1, favours_d1, favours_d2, favours_d2)))
    assert s["d2"] > s["d1"]                                   # po dwa wyścigi, ale nowsze ważą więcej


def test_extreme_gap_is_clipped_so_one_bad_lap_does_not_dominate():
    assert config.QUALI_GAP_CLIP == 7.0
    g = {"d1": 0.0, "d2": 0.5, "d3": 8.0, "d4": 50.0}          # d3 i d4: obaj powyżej progu
    s = QualiGap().score(ctx(aggs_of(g, g, g)))
    assert s["d3"] == s["d4"]


def test_driver_without_data_omitted_and_scores_finite():
    entries = make_entries(("d1", "t"), ("d2", "t"), ("d3", "t"), ("d4", "t"), ("rookie", "t"))
    s = QualiGap().score(ctx(aggs_of(GAPS, GAPS, GAPS), entries=entries))
    assert "rookie" not in s and all(math.isfinite(v) for v in s.values())


def test_none_below_min_aggregates_and_without_aggregates():
    assert QualiGap().score(ctx(aggs_of(GAPS, GAPS))) is None
    assert QualiGap().score(ctx([])) is None


def test_races_with_empty_gaps_do_not_count():
    assert QualiGap().score(ctx(aggs_of(GAPS, GAPS, {}, {}))) is None          # tylko 2 użyteczne (np. 2022 bez czasów)


def test_rookie_with_one_race_is_shrunk_and_retired_driver_ignored():
    from helpers import make_agg, make_ctx, make_entries
    from factors.quali_gap import QualiGap
    entries = make_entries(("d1", "t1"), ("d2", "t1"), ("rookie", "t2"))
    aggs = [make_agg(2027, i + 1, quali_gap={"d1": 0.0, "d2": 1.0, "gone": 6.0}) for i in range(5)]
    aggs.append(make_agg(2027, 6, quali_gap={"d1": 0.0, "d2": 1.0, "rookie": 0.0, "gone": 6.0}))
    s = QualiGap().score(make_ctx(entries=entries, aggregates=aggs))
    assert "gone" not in s and abs(s["rookie"]) < abs(s["d2"])
