"""Statystyki toru liczone z historii: trudność wyprzedzania i prawdopodobieństwo safety cara."""
from __future__ import annotations

import config
from schemas import HistoricRace, SafetyEvent, TrackOverride, TrackStats

MAX_MEAN_CHANGE = 6.0  # średnia zmiana pozycji, od której tor uznajemy za "łatwy"


def _weight(season: int, ref_season: int) -> float:
    return 0.5 ** ((ref_season - season) / config.RECENCY_HALF_LIFE_YEARS)


def _race_numbers(race: HistoricRace) -> tuple[float, float, float] | None:
    """(zwycięzca z pole, zwycięzca spoza top 3, średnia bezwzględna zmiana pozycji) albo None."""
    winner = next((r for r in race.results if r.finish == 1), None)
    if winner is None:
        return None
    moved = [abs(r.grid - r.finish) for r in race.results if r.finish is not None and r.grid > 0]
    mean_change = sum(moved) / len(moved) if moved else 0.0
    return float(winner.grid == 1), float(winner.grid == 0 or winner.grid > 3), mean_change


def _difficulty(history: list[HistoricRace], ref_season: int) -> tuple[float, int] | None:
    total = pole = outside = change = 0.0
    used = 0
    for race in history:
        numbers = _race_numbers(race)
        if numbers is None:
            continue
        w = _weight(race.season, ref_season)
        total += w
        pole += w * numbers[0]
        outside += w * numbers[1]
        change += w * numbers[2]
        used += 1
    if used == 0:
        return None
    value = (0.4 * (pole / total)
             + 0.3 * (1 - outside / total)
             + 0.3 * (1 - min(change / total / MAX_MEAN_CHANGE, 1.0)))
    return value, used


def default_track_stats(all_history: list[HistoricRace], ref_season: int) -> TrackStats:
    """Wartości dla toru bez historii: średnia ze wszystkich torów albo stałe z configu."""
    computed = _difficulty(all_history, ref_season)
    return TrackStats(
        circuit_id="default",
        overtaking_difficulty=computed[0] if computed else 0.5,
        sc_probability=config.DEFAULT_SC_PROBABILITY,
        vsc_probability=config.DEFAULT_VSC_PROBABILITY,
        sample_size=computed[1] if computed else 0,
        source="default",
    )


def _event_rate(safety: dict[int, list[SafetyEvent]], kind: str, ref_season: int, prior: float) -> float:
    """Ważony odsetek wyścigów ze zdarzeniem, ściągnięty ku `prior`: kilka próbek to jeszcze nie pewność."""
    total = hit = 0.0
    for season, events in safety.items():
        w = _weight(season, ref_season)
        total += w
        hit += w * any(e.kind == kind for e in events)
    k = config.SAFETY_PRIOR_STRENGTH
    return (hit + k * prior) / (total + k)


def compute_track_stats(
    circuit_id: str,
    history: list[HistoricRace],
    safety: dict[int, list[SafetyEvent]] | None,
    ref_season: int,
    override: TrackOverride | None,
    fallback: TrackStats,
) -> TrackStats:
    computed = _difficulty(history, ref_season)
    if computed:
        stats = TrackStats(
            circuit_id=circuit_id, overtaking_difficulty=computed[0],
            sc_probability=fallback.sc_probability, vsc_probability=fallback.vsc_probability,
            sample_size=computed[1], source="computed",
        )
    else:
        stats = fallback.model_copy(update={"circuit_id": circuit_id, "sample_size": 0})
    if safety:
        stats = stats.model_copy(update={
            "sc_probability": _event_rate(safety, "SC", ref_season, fallback.sc_probability),
            "vsc_probability": _event_rate(safety, "VSC", ref_season, fallback.vsc_probability),
        })
    if override:
        updates = {k: v for k, v in override.model_dump().items() if v is not None}
        if updates:
            stats = stats.model_copy(update={**updates, "source": "manual"})
    return stats
