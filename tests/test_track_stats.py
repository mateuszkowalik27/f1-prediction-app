from datetime import date

import pytest

import config
from factors.track_stats import compute_track_stats, default_track_stats
from schemas import HistoricRace, HistoricResult, SafetyEvent, TrackOverride


def mk_race(season, pairs, circuit="c"):
    """pairs: lista (pole startowe, miejsce na mecie)."""
    results = [HistoricResult(driver_id=f"d{i}", team_id="t", grid=g, finish=f, status="Finished")
               for i, (g, f) in enumerate(pairs)]
    return HistoricRace(season=season, round=1, circuit_id=circuit, date=date(season, 5, 1),
                        lat=0.0, lon=0.0, results=results)


MONACO_LIKE = [(1, 1), (2, 2), (3, 3), (4, 4), (5, 5), (6, 6)]          # trudność 1.0
MONZA_LIKE = [(6, 1), (1, 6), (2, 7), (10, 2), (3, 8), (8, 3)]          # trudność ~0.025


def stats(history, safety=None, ref=2025, override=None, fallback=None):
    fallback = fallback or default_track_stats([], ref)
    return compute_track_stats("c", history, safety, ref, override, fallback)


def test_monaco_like_history_harder_than_monza_like():
    monaco = stats([mk_race(y, MONACO_LIKE) for y in range(2020, 2025)])
    monza = stats([mk_race(y, MONZA_LIKE) for y in range(2020, 2025)])
    assert monaco.overtaking_difficulty - monza.overtaking_difficulty > 0.3
    assert monaco.source == "computed" and monaco.sample_size == 5


def test_recent_races_weigh_more():
    old_hard_new_easy = stats([mk_race(2015, MONACO_LIKE), mk_race(2024, MONZA_LIKE)])
    old_easy_new_hard = stats([mk_race(2015, MONZA_LIKE), mk_race(2024, MONACO_LIKE)])
    assert old_easy_new_hard.overtaking_difficulty - old_hard_new_easy.overtaking_difficulty > 0.5


def test_empty_history_returns_fallback_default_zero_sample():
    s = stats([])
    assert s.source == "default" and s.sample_size == 0
    assert s.sc_probability == config.DEFAULT_SC_PROBABILITY
    assert s.circuit_id == "c"


def test_manual_override_wins():
    s = stats([mk_race(2024, MONZA_LIKE)], override=TrackOverride(overtaking_difficulty=0.8))
    assert s.overtaking_difficulty == 0.8
    assert s.source == "manual"


def test_sc_probability_from_events():
    safety = {2024: [SafetyEvent(season=2024, kind="SC", lap=10)], 2023: []}
    s = stats([mk_race(2024, MONZA_LIKE)], safety=safety, ref=2024)
    w_old = 0.5 ** (1 / config.RECENCY_HALF_LIFE_YEARS)
    k = config.SAFETY_PRIOR_STRENGTH
    fallback = default_track_stats([], 2024)
    # ważony odsetek wyścigów z SC, ściągnięty ku wartości domyślnej (mało próbek = mniej pewności)
    assert s.sc_probability == pytest.approx((1 + k * fallback.sc_probability) / (1 + w_old + k))
    assert s.vsc_probability == pytest.approx((k * fallback.vsc_probability) / (1 + w_old + k))


def test_sc_never_reaches_extremes_with_few_races():
    safety = {y: [SafetyEvent(season=y, kind="VSC", lap=5)] for y in (2023, 2024, 2025)}
    s = stats([mk_race(2025, MONZA_LIKE)], safety=safety, ref=2025)
    assert 0.5 < s.vsc_probability < 1.0        # trzy wyścigi z VSC to nie pewność
    assert 0.0 < s.sc_probability < 1.0


def test_sc_falls_back_without_safety_data():
    fallback = default_track_stats([], 2025)
    s = stats([mk_race(2024, MONZA_LIKE)], safety=None, fallback=fallback)
    assert s.sc_probability == fallback.sc_probability
    assert s.vsc_probability == fallback.vsc_probability
