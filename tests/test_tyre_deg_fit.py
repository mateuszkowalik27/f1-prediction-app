import math

from factors.tyre_deg_fit import TyreDegFit, track_deg_ratio
from helpers import make_agg, make_ctx, make_entries, make_race

ENTRIES = make_entries(("d1", "t1"), ("d2", "t2"), ("d3", "t3"))
TEAM_DEG = {"t1": -0.03, "t2": 0.0, "t3": 0.03}            # t1 oszczędza opony, t3 je zjada


def history(n_harsh=4, n_mild=4, team_deg=None):
    aggs = []
    for i in range(n_harsh):
        aggs.append(make_agg(2026, i + 1, circuit="harsh", tyre_deg=team_deg or TEAM_DEG, track_deg=0.12))
    for i in range(n_mild):
        aggs.append(make_agg(2026, 10 + i, circuit="mild", tyre_deg=team_deg or TEAM_DEG, track_deg=0.02))
    return aggs


def ctx(circuit, aggs=None):
    return make_ctx(entries=ENTRIES, race=make_race(circuit_id=circuit), aggregates=history() if aggs is None else aggs)


def test_low_deg_team_scores_higher_on_harsh_track():
    s = TyreDegFit().score(ctx("harsh"))
    assert s["d1"] > s["d2"] > s["d3"]


def test_effect_flips_on_mild_track():
    s = TyreDegFit().score(ctx("mild"))
    assert s["d1"] < s["d3"]


def test_none_without_circuit_history():
    assert TyreDegFit().score(ctx("nowy_tor")) is None


def test_none_below_min_aggregates():
    assert TyreDegFit().score(ctx("harsh", history(n_harsh=3, n_mild=2))) is None
    assert TyreDegFit().score(ctx("harsh", [])) is None


def test_all_equal_deg_gives_zero_not_nan():
    s = TyreDegFit().score(ctx("harsh", history(team_deg={"t1": 0.01, "t2": 0.01, "t3": 0.01})))
    assert all(math.isfinite(v) and abs(v) < 1e-9 for v in s.values())


def test_track_deg_ratio_above_one_for_harsh_track_and_below_for_mild():
    assert track_deg_ratio(ctx("harsh")) > 1.0 > track_deg_ratio(ctx("mild"))
    assert track_deg_ratio(ctx("nowy_tor")) is None
