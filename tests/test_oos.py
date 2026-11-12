import json

import pytest

import oos
from evaluation import RoundCase
from helpers import make_ctx, make_entries, make_track
from oos import factor_gate, keep_rule, walk_forward, write_oos
from schemas import SeasonScore

DRIVERS = ["d1", "d2", "d3", "d4"]
BASE = {"signal": 0.5, "noise": 0.5, "grid_base_weight": 0.9, "race_noise_base": 0.5}
BOUNDS = {"signal": (0.0, 1.0), "noise": (0.0, 1.0)}


def case(round_no, winner):
    """Wyścig, w którym czynnik `signal` wskazuje zwycięzcę, a `noise` zawsze faworyzuje d1 (bez związku z wynikiem)."""
    entries = make_entries(*[(d, "t") for d in DRIVERS])
    ctx = make_ctx(entries=entries, grid={d: i + 1 for i, d in enumerate(DRIVERS)})
    finish = {d: (1 if d == winner else 2 + i) for i, d in enumerate(d for d in DRIVERS if d != winner)}
    finish[winner] = 1
    return RoundCase(
        round=round_no, ctx=ctx,
        factor_scores={"signal": {d: (5.0 if d == winner else 0.0) for d in DRIVERS},
                       "noise": {d: (5.0 if d == "d1" else 0.0) for d in DRIVERS}},
        dnf={d: 0.0 for d in DRIVERS}, sim_track=make_track(0.0), stops=2, actual_finish=finish,
    )


def season_cases(n=8):
    return [case(i + 1, DRIVERS[i % 4]) for i in range(n)]


CASES = {2023: season_cases(), 2024: season_cases(), 2025: season_cases()}


def test_tuning_never_sees_the_test_season(monkeypatch):
    seen = []
    monkeypatch.setattr(oos, "tune_weights", lambda base, bounds, locked, rounds_played, evaluate: seen.append(rounds_played) or base)
    walk_forward({2023: season_cases(3), 2024: season_cases(3), 2025: season_cases(3)}, [2024, 2025], BASE, BOUNDS, set(), n=100)
    assert seen == [3, 6]                              # sezon 2024 widzi tylko 2023, sezon 2025 widzi 2023-2024


def test_walk_forward_returns_a_finite_brier_per_test_season():
    scores = walk_forward(CASES, [2024, 2025], BASE, BOUNDS, set(), n=300)
    assert sorted(scores) == [2024, 2025] and all(0 <= v <= 1 for v in scores.values())


def test_walk_forward_skips_test_season_without_cases():
    assert sorted(walk_forward(CASES, [2024, 2030], BASE, BOUNDS, set(), n=200)) == [2024]


@pytest.mark.parametrize("with_s, without_s, expected", [
    ({2024: .02, 2025: .02, 2026: .02}, {2024: .03, 2025: .03, 2026: .03}, True),
    ({2024: .01, 2025: .01, 2026: .035}, {2024: .03, 2025: .03, 2026: .03}, True),      # gorszy w jednym sezonie: nadal OK
    ({2024: .01, 2025: .035, 2026: .035}, {2024: .03, 2025: .03, 2026: .03}, False),    # średnio lepszy, ale gorszy w dwóch
    ({2024: .03, 2025: .03, 2026: .03}, {2024: .03, 2025: .03, 2026: .03}, False),      # remis nie wystarcza
    ({2024: .04, 2025: .04, 2026: .04}, {2024: .03, 2025: .03, 2026: .03}, False),
    ({2024: .01}, {2030: .03}, False),                                                  # brak wspólnych sezonów
])
def test_keep_rule(with_s, without_s, expected):
    assert keep_rule(with_s, without_s) is expected


def test_gate_keeps_informative_factor():
    result = factor_gate(CASES, "signal", [2024, 2025], BASE, BOUNDS, set(), n=300)
    assert result.keep is True
    assert all(result.with_scores[s] < result.without_scores[s] for s in (2024, 2025))


def test_gate_drops_pure_noise_factor():
    result = factor_gate(CASES, "noise", [2024, 2025], BASE, BOUNDS, set(), n=300)
    assert result.keep is False
    assert all(result.with_scores[s] > result.without_scores[s] for s in (2024, 2025))


def test_write_oos_roundtrip(tmp_path):
    path = tmp_path / "oos.json"
    write_oos(path, {2024: 0.0251, 2025: 0.0243})
    rows = [SeasonScore(**r) for r in json.loads(path.read_text())]
    assert [(r.season, r.brier) for r in rows] == [(2024, 0.0251), (2025, 0.0243)]
