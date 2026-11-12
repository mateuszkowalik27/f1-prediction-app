"""Auto-wagi: po każdym wyścigu robot ostrożnie dostraja wagi, minimalizując błąd przewidywania zwycięzcy.

Zabezpieczenia: wagi zostają w granicach, zablokowanych nie ruszamy, poniżej MIN_ROUNDS nic się nie zmienia,
a zmiana jest tylko ułamkiem drogi do optimum (lambda rośnie z liczbą rund), bo próbka jest mała.
"""
from __future__ import annotations

from typing import Callable

import numpy as np

import config
from schemas import WeightSnapshot, WeightsFile

MIN_ROUNDS = 3
CANDIDATES_PER_WEIGHT = 9


def tune_weights(
    base: dict[str, float],
    bounds: dict[str, tuple[float, float]],
    locked: set[str],
    rounds_played: int,
    evaluate: Callable[[dict[str, float]], float],
) -> dict[str, float]:
    """`evaluate(wagi)` zwraca błąd (mniejszy = lepiej). Wynik to baza przesunięta o ułamek drogi do optimum."""
    if rounds_played < MIN_ROUNDS:
        return dict(base)
    best = dict(base)
    for key in base:                                   # wyszukiwanie współrzędnych: po jednej wadze naraz
        if key in locked or key not in bounds:
            continue
        lo, hi = bounds[key]
        candidates = list(np.linspace(lo, hi, CANDIDATES_PER_WEIGHT)) + [base[key]]
        scored = [(evaluate({**best, key: float(v)}), abs(v - base[key]), float(v)) for v in candidates]
        best[key] = min(scored)[2]                     # remis rozstrzyga bliskość bazy
    lam = rounds_played / (rounds_played + config.TUNING_K)
    tuned = {}
    for key, value in base.items():
        if key in locked or key not in bounds:
            tuned[key] = value
        else:
            lo, hi = bounds[key]
            tuned[key] = float(min(hi, max(lo, value + lam * (best[key] - value))))
    return tuned


def append_snapshot(previous: WeightsFile | None, weights: dict[str, float], round: int,
                    season: int | None = None) -> WeightsFile:
    history = [s for s in (previous.history if previous else []) if (s.season, s.round) != (season, round)]
    history.append(WeightSnapshot(season=season, round=round, weights=dict(weights)))
    return WeightsFile(weights=dict(weights), history=sorted(history, key=lambda s: (s.season or 0, s.round)))
