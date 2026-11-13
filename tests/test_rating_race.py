import math

from factors.rating_race import RatingRace
from helpers import hist_race, make_ctx, make_entries

ENTRIES = make_entries(("a1", "fast"), ("a2", "fast"), ("b1", "mid"), ("b2", "mid"), ("c1", "slow"), ("c2", "slow"))


def season(year, n=6):
    rows = [("a1", "fast", 1), ("b1", "mid", 2), ("a2", "fast", 3), ("c1", "slow", 4), ("b2", "mid", 5), ("c2", "slow", 6)]
    return [hist_race(year, i + 1, rows) for i in range(n)]


def test_leader_of_the_ratings_scores_highest_and_values_are_finite():
    scores = RatingRace().score(make_ctx(entries=ENTRIES, long_history=season(2026)))
    assert scores["a1"] == max(scores.values()) and scores["c2"] == min(scores.values())
    assert all(math.isfinite(v) for v in scores.values())


def test_driver_without_history_gets_a_neutral_finite_score():
    entries = ENTRIES + make_entries(("rookie", "new_team"))
    scores = RatingRace().score(make_ctx(entries=entries, long_history=season(2026)))
    assert math.isfinite(scores["rookie"]) and min(scores.values()) < scores["rookie"] < max(scores.values())


def test_none_when_history_is_too_short():
    assert RatingRace().score(make_ctx(entries=ENTRIES, long_history=season(2026, n=2))) is None
    assert RatingRace().score(make_ctx(entries=ENTRIES)) is None


def test_falls_back_to_the_short_history_when_there_is_no_long_one():
    assert RatingRace().score(make_ctx(entries=ENTRIES, history=season(2026))) is not None


def test_same_inputs_give_the_same_scores():
    ctx = make_ctx(entries=ENTRIES, long_history=season(2026))
    assert RatingRace().score(ctx) == RatingRace().score(ctx)


# --- trend, dziedziczenie i dostawca silnika (model v3, etap 6) ---
def improving_history():
    rows_a = [("a1", "up", 1), ("a2", "up", 2), ("b1", "mid", 3), ("b2", "mid", 4), ("c1", "down", 5), ("c2", "down", 6)]
    early = [hist_race(2026, i + 1, [("a1", "up", 3), ("a2", "up", 4), ("b1", "mid", 1), ("b2", "mid", 2), ("c1", "down", 5), ("c2", "down", 6)])
             for i in range(4)]                                                 # "up" na początku sezonu słaby...
    late = [hist_race(2026, 5 + i, rows_a) for i in range(4)]                   # ...a potem wygrywa: zespół przyspiesza
    return early + late


def test_trend_gain_rewards_the_team_that_is_getting_faster():
    ctx = make_ctx(entries=ENTRIES, long_history=improving_history())
    flat = RatingRace(trend_gain=0.0).score(ctx)
    pushed = RatingRace(trend_gain=3.0, trend_alpha=0.5).score(ctx)
    assert pushed["a1"] - flat["a1"] > pushed["b1"] - flat["b1"]               # "up" zyskuje względem "mid" dzięki trendowi


def test_switched_off_parameters_equal_explicit_zeros(monkeypatch):
    import config
    for name, value in (("RATING_TREND_GAIN", 0.0), ("RATING_SUPPLIER_WEIGHT", 0.0), ("RATING_USE_LINEAGE", False)):
        monkeypatch.setattr(config, name, value)
    ctx = make_ctx(entries=ENTRIES, long_history=improving_history())
    assert RatingRace().score(ctx) == RatingRace(trend_gain=0.0, supplier_weight=0.0, use_lineage=False).score(ctx)


def test_the_adopted_defaults_come_from_the_config():
    import config
    ctx = make_ctx(entries=ENTRIES, long_history=improving_history())
    assert RatingRace().score(ctx) == RatingRace(trend_gain=config.RATING_TREND_GAIN, trend_alpha=config.RATING_TREND_ALPHA,
                                                 supplier_weight=config.RATING_SUPPLIER_WEIGHT,
                                                 use_lineage=config.RATING_USE_LINEAGE).score(ctx)
