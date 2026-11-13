import math

import pytest

from factors.base import combine, combine_side, zscore
from helpers import make_ctx, make_entries


class Fixed:
    def __init__(self, name, scores):
        self.name = name
        self._scores = scores

    def score(self, ctx):
        return self._scores


def test_none_factor_skipped_and_weights_renormalized():
    ctx = make_ctx()
    result = combine(ctx, [Fixed("a", {"d1": 1.0, "d2": -1.0}), Fixed("b", None)], {"a": 0.3, "b": 0.7})
    assert result.used == ["a"] and result.skipped == ["b"]
    assert result.strength["d1"] == pytest.approx(1.0)  # waga 0.3 po renormalizacji = 1.0


def test_driver_missing_from_factor_gets_neutral_and_values_finite():
    ctx = make_ctx(entries=make_entries(("d1", "t"), ("d2", "t"), ("d3", "t")))
    result = combine(ctx, [Fixed("a", {"d1": 2.0, "d2": float("nan")})], {"a": 1.0})
    assert result.strength["d3"] == 0.0   # debiutant bez danych: neutralnie
    assert result.strength["d2"] == 0.0   # NaN zamieniony na 0
    assert all(math.isfinite(v) for v in result.strength.values())


def test_all_factors_none_gives_zero_strength_and_low_data():
    ctx = make_ctx()
    result = combine(ctx, [Fixed("a", None), Fixed("b", None)], {"a": 0.5, "b": 0.5})
    assert set(result.strength.values()) == {0.0}
    assert result.low_data is True and result.used == []


def test_low_data_false_with_three_used_factors():
    ctx = make_ctx()
    factors = [Fixed(n, {"d1": 1.0}) for n in "abc"]
    assert combine(ctx, factors, {"a": 1, "b": 1, "c": 1}).low_data is False


def test_zscore_constant_input_is_zeros():
    assert zscore({"a": 3.0, "b": 3.0}) == {"a": 0.0, "b": 0.0}


def test_zscore_has_zero_mean_unit_variance():
    z = zscore({"a": 1.0, "b": 2.0, "c": 3.0})
    assert sum(z.values()) == pytest.approx(0.0)
    assert sum(v * v for v in z.values()) / 3 == pytest.approx(1.0)


def test_aggregates_filtered_by_as_of_round_no_future_leak():
    from factors.context import build_context
    from helpers import make_agg, make_entries, make_race, make_track

    aggs = [make_agg(2027, r) for r in range(1, 6)] + [make_agg(2026, 24)]
    ctx = build_context(make_race(round=3), make_entries(("d1", "t1")), [], [], {}, None, None, None, make_track(),
                        None, {}, as_of_round=3, aggregates=aggs)
    assert [(a.season, a.round) for a in ctx.aggregates] == [(2026, 24), (2027, 1), (2027, 2)]


def test_aggregates_default_to_empty():
    assert make_ctx().aggregates == []


def test_zero_weight_factor_is_not_computed_or_counted_as_used():
    from factors.base import combine
    from helpers import make_ctx, make_entries

    class F:
        def __init__(self, name, out): self.name, self.out, self.called = name, out, False
        def score(self, ctx):
            self.called = True
            return self.out

    on, off = F("on", {"d1": 1.0}), F("off", {"d1": -1.0})
    res = combine(make_ctx(entries=make_entries(("d1", "t1"))), [on, off], {"on": 1.0, "off": 0.0})
    assert res.used == ["on"] and not off.called and res.skipped == []


def test_combine_side_quali_uses_only_the_q_weights():
    ctx = make_ctx()
    factors = [Fixed("a", {"d1": 1.0, "d2": -1.0}), Fixed("b", {"d1": -1.0, "d2": 1.0})]
    weights = {"a": 1.0, "b": 0.0, "q_a": 0.0, "q_b": 1.0}
    race = combine_side(ctx, factors, weights, "race")
    quali = combine_side(ctx, factors, weights, "quali")
    assert race.used == ["a"] and race.strength["d1"] == pytest.approx(1.0)
    assert quali.used == ["b"] and quali.strength["d1"] == pytest.approx(-1.0)


def test_combine_side_missing_q_weight_means_the_factor_is_skipped():
    ctx = make_ctx()
    result = combine_side(ctx, [Fixed("a", {"d1": 1.0})], {"a": 1.0}, "quali")
    assert result.used == [] and all(v == 0.0 for v in result.strength.values())      # siła zerowa, nie błąd


def test_long_history_is_filtered_to_earlier_races_and_defaults_to_empty():
    from factors.context import build_context
    from helpers import hist_race, make_race

    rows = [("d1", "t1", 1), ("d2", "t1", 2)]
    long = [hist_race(2020, 3, rows), hist_race(2027, 4, rows), hist_race(2027, 5, rows), hist_race(2027, 6, rows)]
    race = make_race(round=5)
    ctx = build_context(race, make_entries(("d1", "t1")), [], [], {}, None, None, None, make_ctx().track, None, {},
                        as_of_round=5, long_history=long)
    assert [(h.season, h.round) for h in ctx.long_history] == [(2020, 3), (2027, 4)]       # bez rundy 5 i późniejszych
    assert make_ctx().long_history == []
