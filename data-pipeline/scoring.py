"""Miary oceny prognoz: RPS dla całej kolejności, bootstrap różnic i werdykt (model v3, etap 1).

RPS (ranked probability score) porównuje przewidziany rozkład miejsc z faktycznym miejscem. Im dalej od prawdy, tym większa kara
(pomyłka o jedno miejsce kosztuje mało, o piętnaście dużo). Daje ok. 20 obserwacji na wyścig zamiast jednej (zwycięzca).
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np

from schemas import DriverProbability


def rps(predicted: Sequence[float], actual: Sequence[float]) -> float:
    """RPS dla rozkładów na miejsca 1..N (0 = idealnie, 1 = najgorzej): suma kwadratów różnic dystrybuant / (N-1)."""
    if len(predicted) != len(actual):
        raise ValueError("rozkłady muszą mieć tyle samo kategorii")
    if len(predicted) < 2:
        return 0.0
    gaps = np.cumsum(predicted)[:-1] - np.cumsum(actual)[:-1]
    return float(np.sum(gaps ** 2) / (len(predicted) - 1))


def actual_distribution(position: int | None, n: int, classified: int) -> list[float]:
    """Faktyczny wynik jako rozkład: jedynka na miejscu, a dla nieklasyfikowanego (None) równo na miejscach classified+1..n."""
    if position is None:
        tail = n - classified
        if tail <= 0:
            return [0.0] * (n - 1) + [1.0]
        return [0.0] * classified + [1.0 / tail] * tail
    dist = [0.0] * n
    dist[min(max(position, 1), n) - 1] = 1.0
    return dist


def ranking_rps(prediction: list[DriverProbability], actual: dict[str, int | None]) -> float:
    """Średnie RPS po kierowcach obecnych i w prognozie, i w wyniku. Wynik None = nieklasyfikowany (ostatnie miejsca)."""
    by_id = {p.driver_id: p for p in prediction}
    shared = [d for d in actual if d in by_id]
    if not shared:
        raise ValueError("brak wspólnych kierowców w prognozie i wyniku")
    n = len(by_id[shared[0]].position_distribution)
    classified = sum(1 for f in actual.values() if f is not None)
    return float(np.mean([rps(by_id[d].position_distribution, actual_distribution(actual[d], n, classified))
                          for d in shared]))


@dataclass(frozen=True)
class Diff:
    """Różnica `a - b` miary na wyścig: średnia i przedział (ujemna = a lepsze, bo mniejsza miara jest lepsza)."""
    mean: float
    lo: float
    hi: float
    n: int


def paired_bootstrap(a: Sequence[float], b: Sequence[float], n_boot: int = 4000, seed: int = 0,
                     level: float = 0.9) -> Diff:
    """Bootstrap po wyścigach (pary a[i], b[i]); przedział percentylowy na poziomie `level`."""
    if len(a) != len(b):
        raise ValueError("listy muszą mieć tę samą długość")
    if not a:
        raise ValueError("brak wyścigów do porównania")
    diffs = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    rng = np.random.default_rng(seed)
    means = diffs[rng.integers(0, len(diffs), size=(n_boot, len(diffs)))].mean(axis=1)
    tail = (1 - level) / 2 * 100
    lo, hi = np.percentile(means, [tail, 100 - tail])
    return Diff(mean=float(diffs.mean()), lo=float(lo), hi=float(hi), n=len(diffs))


def verdict(diff: Diff) -> Literal["better", "worse", "inconclusive"]:
    """`better` gdy cały przedział leży poniżej zera, `worse` gdy powyżej, inaczej `inconclusive` (szum)."""
    if diff.hi < 0:
        return "better"
    if diff.lo > 0:
        return "worse"
    return "inconclusive"
