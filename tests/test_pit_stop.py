import math

import config
from factors.pit_stop import PitStopSpeed
from helpers import make_agg, make_ctx, make_entries

TEAMS = make_entries(("d1", "t1"), ("d2", "t1"), ("d3", "t2"), ("d4", "t3"))
DELTAS = {"t1": -0.5, "t2": 0.0, "t3": 0.8}


def ctx(deltas_list, **kw):
    aggs = [make_agg(2027, i + 1, pit_delta=d) for i, d in enumerate(deltas_list)]
    return make_ctx(entries=kw.pop("entries", TEAMS), aggregates=aggs, **kw)


def test_faster_pit_crew_scores_higher():
    s = PitStopSpeed().score(ctx([DELTAS] * 3))
    assert s["d1"] > s["d3"] > s["d4"]


def test_score_is_assigned_to_drivers_of_the_current_team():
    s = PitStopSpeed().score(ctx([DELTAS] * 3))
    assert s["d1"] == s["d2"]                                   # ten sam zespół


def test_team_not_in_aggregates_gets_no_score_and_values_are_finite():
    entries = make_entries(("d1", "t1"), ("d3", "t2"), ("rookie", "t_new"))
    s = PitStopSpeed().score(ctx([{"t1": -0.5, "t2": 0.4}] * 3, entries=entries))
    assert "rookie" not in s and all(math.isfinite(v) for v in s.values())


def test_extreme_delta_is_clipped():
    assert config.PIT_DELTA_CLIP == 2.0
    big, clipped = {"t1": -0.5, "t2": 0.0, "t3": 9.0}, {"t1": -0.5, "t2": 0.0, "t3": 2.0}
    assert PitStopSpeed().score(ctx([big] * 3)) == PitStopSpeed().score(ctx([clipped] * 3))


def test_recent_races_weigh_more():
    old, new = {"t1": -1.0, "t2": 1.0, "t3": 0.0}, {"t1": 1.0, "t2": -1.0, "t3": 0.0}
    s = PitStopSpeed().score(ctx([old, old, new, new]))
    assert s["d3"] > s["d1"]                                    # t2 był wolny dawniej, ale ostatnio jest najszybszy


def test_none_below_min_aggregates_and_without_aggregates():
    assert PitStopSpeed().score(ctx([DELTAS] * 2)) is None
    assert PitStopSpeed().score(ctx([])) is None


def test_debut_team_with_one_race_is_shrunk_toward_neutral():
    entries = make_entries(("d1", "t1"), ("d3", "t2"), ("rookie", "t_new"))
    veteran = {"t1": -0.5, "t2": 0.4}
    aggs = [make_agg(2027, i + 1, pit_delta=veteran) for i in range(5)]
    aggs.append(make_agg(2027, 6, pit_delta={"t1": -0.5, "t2": 0.4, "t_new": -0.5}))   # debiutant: jeden wyścig
    s = PitStopSpeed().score(make_ctx(entries=entries, aggregates=aggs))
    assert abs(s["rookie"]) < abs(s["d1"])


def test_retired_team_does_not_shift_the_field_average():
    entries = make_entries(("d1", "t1"), ("d3", "t2"))
    aggs = [make_agg(2027, i + 1, pit_delta={"t1": -0.5, "t2": 0.5, "defunct": 5.0}) for i in range(4)]
    s = PitStopSpeed().score(make_ctx(entries=entries, aggregates=aggs))
    assert abs(s["d1"] + s["d3"]) < 1e-9        # z-score po obecnych zespołach: średnia 0
