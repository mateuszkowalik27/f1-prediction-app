"""Model kwalifikacji: symulacja Monte Carlo na samej sile kierowców (bez pozycji startowej)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

import config
from schemas import DriverProbability


@dataclass(frozen=True)
class QualifyingPrediction:
    probabilities: list[DriverProbability]   # win = szansa na pole position
    predicted_grid: dict[str, int]           # driver_id -> przewidziana pozycja startowa (1..N)


def predict_qualifying(
    strength: dict[str, float],
    n: int = config.N_SIMULATIONS,
    seed: int = config.RANDOM_SEED,
    noise: float = 0.8,
) -> QualifyingPrediction:
    drivers = sorted(strength)
    count = len(drivers)
    base = np.array([strength[d] for d in drivers])
    rng = np.random.default_rng(seed)
    performance = base + rng.normal(0.0, noise, size=(n, count))
    ranks = (-performance).argsort(axis=1).argsort(axis=1)   # 0 = pole position

    probabilities = []
    medians = {}
    for i, driver in enumerate(drivers):
        distribution = np.bincount(ranks[:, i], minlength=count) / n
        medians[driver] = float(np.median(ranks[:, i]))
        probabilities.append(DriverProbability(
            driver_id=driver,
            win=float(distribution[0]),
            podium=float(distribution[:3].sum()),
            points=0.0,
            expected_points=0.0,
            position_distribution=distribution.tolist(),
        ))
    order = sorted(drivers, key=lambda d: (medians[d], -strength[d], d))
    return QualifyingPrediction(probabilities=probabilities,
                                predicted_grid={d: pos + 1 for pos, d in enumerate(order)})
