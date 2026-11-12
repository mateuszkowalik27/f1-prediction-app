"""Kalibracja szans na wygraną: jeden parametr tau, szansa' ~ szansa^tau, dopasowany poza próbką."""
from __future__ import annotations

from pathlib import Path

import config
from schemas import Calibration, DriverProbability

Prediction = tuple[list[DriverProbability], dict[str, "int | None"]]


def apply_tau(rows: list[DriverProbability], tau: float) -> list[DriverProbability]:
    """Skaluje szanse na wygraną (win' ~ win^tau, suma 1). Podium i punkty zostają, ale nie mniejsze niż win';
    rozkład pozycji: pierwszy element = win', reszta przeskalowana do sumy 1."""
    if tau == 1.0:
        return rows
    powered = [r.win ** tau for r in rows]
    total = sum(powered)
    if total <= 0:
        return rows
    out = []
    for r, p in zip(rows, powered):
        win = p / total
        rest = list(r.position_distribution[1:])
        rest_sum = sum(rest)
        if rest and rest_sum > 0:
            rest = [x * (1 - win) / rest_sum for x in rest]
        elif rest:
            rest = [(1 - win) / len(rest)] * len(rest)
        out.append(r.model_copy(update={
            "win": win, "podium": max(r.podium, win), "points": max(r.points, win),
            "position_distribution": [win] + rest if r.position_distribution else [],
        }))
    return out


def _brier(predictions: list[Prediction], tau: float) -> float:
    total = 0.0
    for rows, actual in predictions:
        wins = {r.driver_id: r.win for r in apply_tau(rows, tau)}
        total += sum((p - (actual.get(d) == 1)) ** 2 for d, p in wins.items()) / len(wins)
    return total / len(predictions)


def fit_tau(predictions: list[Prediction], min_races: int = config.CAL_MIN_RACES) -> float:
    """tau z siatki minimalizujący Brier szans na wygraną; 1.0, gdy przewidywań jest za mało."""
    usable = [(rows, actual) for rows, actual in predictions if any(f == 1 for f in actual.values())]
    if len(usable) < min_races:
        return 1.0
    return min(config.CAL_TAU_GRID, key=lambda t: (_brier(usable, t), abs(t - 1.0)))


def load_calibration(path: Path) -> Calibration | None:
    try:
        return Calibration.model_validate_json(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
