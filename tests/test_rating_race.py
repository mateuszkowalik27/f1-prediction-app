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
