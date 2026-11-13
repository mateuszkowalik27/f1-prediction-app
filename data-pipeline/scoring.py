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
