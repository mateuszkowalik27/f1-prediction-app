"""Budowanie kontekstu predykcji (wspólne dla pipeline'u i testu wstecznego)."""
from __future__ import annotations

from datetime import datetime, time, timezone

from factors.base import RaceContext
from schemas import HistoricRace, Race, Session


def build_context(race, entries, history, circuit_history, wet, weather, practice, grid, track, profile,
                  profiles, as_of_round: int) -> RaceContext:
    """Kontekst predykcji bez wyników z rundy `as_of_round` i późniejszych (ważne dla testu wstecznego)."""
    def before(h: HistoricRace) -> bool:
        return (h.season, h.round) < (race.season, as_of_round)

    return RaceContext(
        race=race, entries=entries, track=track, season=race.season,
        history=[h for h in history if before(h) and h.results],
        circuit_history=[h for h in circuit_history if before(h) and h.results],
        wet=wet, weather=weather, practice=practice, grid=grid, profile=profile, profiles=profiles,
    )


def race_from_history(h: HistoricRace) -> Race:
    return Race(season=h.season, round=h.round, name=f"{h.season} R{h.round}", circuit_id=h.circuit_id,
                country="", lat=h.lat, lon=h.lon, is_sprint=False,
                sessions=[Session(name="Race", start_utc=datetime.combine(h.date, time(13, 0), tzinfo=timezone.utc))])
