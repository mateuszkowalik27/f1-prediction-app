"""Szkielet czynników: wspólny kontekst, interfejs czynnika i łączenie ocen w jedną siłę kierowcy."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Protocol

from schemas import (
    DriverEntry, HistoricRace, PracticeData, Race, RaceAggregates, TrackProfile, TrackStats, WeatherForecast,
)

LOW_DATA_FACTOR_COUNT = 3


@dataclass(frozen=True, kw_only=True)
class RaceContext:
    race: Race
    entries: list[DriverEntry]
    track: TrackStats
    season: int
    history: list[HistoricRace] = field(default_factory=list)          # tylko rundy wcześniejsze niż bieżąca
    circuit_history: list[HistoricRace] = field(default_factory=list)
    wet: dict[tuple[int, int], bool] = field(default_factory=dict)
    weather: WeatherForecast | None = None
    practice: PracticeData | None = None
    grid: dict[str, int] | None = None
    profile: TrackProfile | None = None
    profiles: dict[str, TrackProfile] = field(default_factory=dict)    # profile torów rozegranych rund sezonu
    aggregates: list[RaceAggregates] = field(default_factory=list)     # agregaty wyścigów wcześniejszych niż bieżący


class Factor(Protocol):
    name: str

    def score(self, ctx: RaceContext) -> dict[str, float] | None:
        """driver_id -> ocena (wyższa = lepiej) albo None, gdy brak danych."""


@dataclass(frozen=True)
class CombinedStrength:
    strength: dict[str, float]
    used: list[str]
    skipped: list[str]
    low_data: bool


def zscore(values: dict[str, float]) -> dict[str, float]:
    if not values:
        return {}
    mean = sum(values.values()) / len(values)
    var = sum((v - mean) ** 2 for v in values.values()) / len(values)
    if var == 0:
        return {k: 0.0 for k in values}
    sd = math.sqrt(var)
    return {k: (v - mean) / sd for k, v in values.items()}


def combine(ctx: RaceContext, factors: list[Factor], weights: dict[str, float]) -> CombinedStrength:
    scored: dict[str, dict[str, float]] = {}
    skipped: list[str] = []
    active = [f for f in factors if weights.get(f.name, 0) > 0]
    for factor in (active or factors):   # czynniki z wagą 0 są wyłączone: nie liczymy ich i nie zaliczamy do użytych
        scores = factor.score(ctx)
        if scores is None:
            skipped.append(factor.name)
        else:
            scored[factor.name] = scores
    used = list(scored)
    total = sum(weights[n] for n in used)
    norm = {n: (weights[n] / total if total > 0 else 1 / len(used)) for n in used}
    strength = {}
    for entry in ctx.entries:
        value = 0.0
        for name in used:
            s = scored[name].get(entry.driver_id, 0.0)
            value += norm[name] * (s if math.isfinite(s) else 0.0)
        strength[entry.driver_id] = value
    return CombinedStrength(strength=strength, used=used, skipped=skipped,
                            low_data=len(used) < LOW_DATA_FACTOR_COUNT)


def race_points(finish: int | None) -> int:
    """Punkty za miejsce (bez sprintu i najszybszego okrążenia); brak klasyfikacji = 0."""
    import config
    return config.POINTS_TABLE[finish - 1] if finish and finish <= len(config.POINTS_TABLE) else 0


def chronological(history: list[HistoricRace]) -> list[HistoricRace]:
    return sorted(history, key=lambda r: (r.season, r.round))
