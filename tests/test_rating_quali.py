import math

import config
from factors.rating_quali import RatingQuali
from helpers import hist_race, make_agg, make_ctx, make_entries


def history(rows_by_round, season=2027):
    return [hist_race(season, rnd, rows) for rnd, rows in rows_by_round.items()]


def build(entries, gaps_by_round, teams_by_round=None, season=2027):
    """gaps_by_round: {runda: {kierowca: strata%}}; składy z `teams_by_round` (kierowca -> zespół)."""
    teams_by_round = teams_by_round or {}
    rows = {rnd: [(d, teams_by_round.get(rnd, {}).get(d, "t_" + d), i + 1) for i, d in enumerate(g)] for rnd, g in gaps_by_round.items()}
    aggs = [make_agg(season, rnd, quali_gap=g) for rnd, g in gaps_by_round.items()]
    return make_ctx(entries=entries, aggregates=aggs, long_history=history(rows, season))


def test_none_without_enough_aggregates():
    ctx = build(make_entries(("a", "t_a"), ("b", "t_b")), {1: {"a": 0.0, "b": 0.5}})
    assert RatingQuali().score(ctx) is None


def test_faster_team_and_faster_teammate_score_higher():
    teams = {r: {"a1": "A", "a2": "A", "b1": "B", "b2": "B"} for r in range(1, 7)}
    gaps = {r: {"a1": 0.0, "a2": 0.4, "b1": 1.0, "b2": 1.6} for r in range(1, 7)}
    entries = make_entries(("a1", "A"), ("a2", "A"), ("b1", "B"), ("b2", "B"))
    s = RatingQuali().score(build(entries, gaps, teams))
    assert s["a1"] > s["a2"] > s["b1"] > s["b2"]
    assert all(math.isfinite(v) for v in s.values())


def test_a_driver_keeps_his_edge_over_the_teammate_when_he_moves_to_a_better_car():
    old = {"star": "slow_team", "mate": "slow_team", "x": "fast_team", "y": "fast_team"}
    gaps = {r: {"star": 1.0, "mate": 1.6, "x": 0.0, "y": 0.1} for r in range(1, 7)}
    teams = {r: old for r in gaps}
    entries = make_entries(("star", "fast_team"), ("x", "fast_team"), ("mate", "slow_team"), ("y", "fast_team2"))
    s = RatingQuali().score(build(entries, gaps, teams))
    assert s["star"] > s["mate"]            # w lepszym aucie i z przewagą nad kolegą z poprzedniego zespołu
    assert s["star"] > s["y"]            # lepszy od kierowcy, który w tych samych danych jedzie szybkim autem, ale z mniejszą przewagą


def test_rookie_in_an_established_team_gets_the_team_pace_not_nothing():
    teams = {r: {"a1": "A", "a2": "A", "b1": "B"} for r in range(1, 7)}
    gaps = {r: {"a1": 0.0, "a2": 0.2, "b1": 1.5} for r in range(1, 7)}
    entries = make_entries(("a1", "A"), ("rookie", "A"), ("b1", "B"))
    s = RatingQuali().score(build(entries, gaps, teams))
    assert s["rookie"] > s["b1"]            # nowy kierowca w szybkim zespole wyprzedza kierowcę wolnego zespołu


def test_extreme_gap_is_clipped():
    teams = {r: {"a": "A", "b": "B"} for r in range(1, 7)}
    huge = build(make_entries(("a", "A"), ("b", "B")), {r: {"a": 0.0, "b": 90.0} for r in range(1, 7)}, teams)
    capped = build(make_entries(("a", "A"), ("b", "B")), {r: {"a": 0.0, "b": config.QUALI_GAP_CLIP} for r in range(1, 7)}, teams)
    assert RatingQuali().score(huge) == RatingQuali().score(capped)
