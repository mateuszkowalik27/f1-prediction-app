"""Uzupełnianie historii agregatów: raz na zakończony wyścig, najnowsze najpierw, w ramach budżetu na uruchomienie.

Użycie:  python data-pipeline/backfill.py --out public/data --budget 30
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import config
from aggregates import compute_pit_deltas, compute_race_pace, compute_tyre_deg, link_session_gaps
from factors.context import race_from_history
from fetch.jolpica import JolpicaError
from history_store import HistoryStore
from optional import optional
from schemas import DriverEntry, HistoricRace, RaceAggregates

if TYPE_CHECKING:
    from run import Clients


@dataclass(frozen=True)
class BackfillReport:
    created: int        # zapisane teraz agregaty
    retry_later: int    # nie zapisane przez błąd źródła: próbujemy znów przy następnym uruchomieniu
    remaining: int      # ile wyścigów nadal bez agregatu


def build_aggregates(race: HistoricRace, entries: list[DriverEntry], clients: "Clients") -> RaceAggregates:
    """Liczy agregat jednego zakończonego wyścigu. Błąd Jolpica propaguje; błąd OpenF1 oznacza źródło `failed`."""
    j, f1 = clients.jolpica, clients.openf1
    team_of = {r.driver_id: r.team_id for r in race.results}
    quali = j.qualifying_times(race.season, race.round)
    stops = j.pit_stops(race.season, race.round)
    jolpica_status = "ok" if (quali or stops) else "missing"

    race_pace: dict[str, float] = {}
    tyre_deg: dict[str, float] = {}
    track_deg = air = track_temp = official = None
    openf1_status = "missing"
    if race.season >= config.OPENF1_FIRST_SEASON:
        errors_before = getattr(f1, "errors", 0)
        weekend = race_from_history(race)
        laps, failed_laps = optional("okrążenia wyścigu (OpenF1)", f1.race_laps, weekend, entries)
        weather, failed_weather = optional("pogoda wyścigu (OpenF1)", f1.race_weather, weekend)
        official, failed_grid = optional("siatka startowa (OpenF1)", f1.starting_grid, weekend, entries)
        if laps:
            race_pace = compute_race_pace(laps)
            tyre_deg, track_deg = compute_tyre_deg(laps, team_of)
        if weather:
            air, track_temp = weather.air_c, weather.track_c
        # klient zwraca None zarówno przy braku danych, jak i przy awarii: odróżnia je licznik błędów
        errored = getattr(f1, "errors", 0) > errors_before
        if failed_laps or failed_weather or failed_grid or errored:
            openf1_status = "failed"
        elif laps or weather or official:
            openf1_status = "ok"

    return RaceAggregates(
        season=race.season, round=race.round, circuit_id=race.circuit_id, computed_at=datetime.now(timezone.utc),
        quali_gap=link_session_gaps(quali) if quali else {}, pit_delta=compute_pit_deltas(stops, team_of),
        race_pace=race_pace, tyre_deg=tyre_deg, track_deg=track_deg, air_temp_c=air, track_temp_c=track_temp,
        official_grid=official, sources={"jolpica": jolpica_status, "openf1": openf1_status},
    )


def _merge(old: RaceAggregates, new: RaceAggregates) -> RaceAggregates:
    """Przy dopełnianiu: to, co nowa próba przyniosła, wygrywa; czego nie przyniosła, zostaje ze starego agregatu."""
    fields = {}
    for name in ("quali_gap", "pit_delta", "race_pace", "tyre_deg"):
        fields[name] = getattr(new, name) or getattr(old, name)
    for name in ("track_deg", "air_temp_c", "track_temp_c", "official_grid"):
        value = getattr(new, name)
        fields[name] = value if value is not None else getattr(old, name)
    return new.model_copy(update=fields)


def ensure_aggregates(store: HistoryStore, clients: "Clients", seasons: list[int], budget: int,
                      now: datetime | None = None) -> BackfillReport:
    """Uzupełnia brakujące i niekompletne agregaty (od najnowszych), próbując najwyżej `budget` wyścigów.
    Wyścigów zakończonych niedawno (BACKFILL_MIN_AGE_DAYS) nie ruszamy: źródła dopisują dane z opóźnieniem."""
    j = clients.jolpica
    cutoff = ((now or datetime.now(timezone.utc)) - timedelta(days=config.BACKFILL_MIN_AGE_DAYS)).date()
    candidates: list[tuple[HistoricRace, list[DriverEntry]]] = []
    for season in sorted(seasons, reverse=True):
        races = sorted((h for h in j.season_results(season, 9999) if h.results and h.date <= cutoff), key=lambda h: h.round, reverse=True)
        if not races:
            continue
        entries = j.entries(season)
        candidates += [(h, entries) for h in races]
    missing = set(store.pending([(h.season, h.round) for h, _ in candidates]))

    # najpierw wyścigi całkiem bez agregatu, dopiero potem dopełnianie niekompletnych (stabilnie: najnowsze najpierw)
    candidates.sort(key=lambda c: store.load(c[0].season, c[0].round) is not None)
    created = retry_later = 0
    for race, entries in candidates:
        if (race.season, race.round) not in missing:
            continue
        if created + retry_later >= budget:
            break
        existing = store.load(race.season, race.round)
        aggregate = build_aggregates(race, entries, clients)
        if aggregate.sources["openf1"] == "failed":
            retry_later += 1                      # awaria źródła: nic nie zapisujemy, próbujemy znów
            continue
        if existing is not None:
            aggregate = _merge(existing, aggregate).model_copy(update={"attempts": existing.attempts + 1})
        if store.save(aggregate, overwrite=existing is not None):
            created += 1
    return BackfillReport(created=created, retry_later=retry_later, remaining=len(missing) - created)


def main(argv: list[str] | None = None) -> int:
    from run import default_clients, resolve_season  # import tutaj: run.py importuje ten moduł

    parser = argparse.ArgumentParser(description="Uzupełnianie historii agregatów wyścigów")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--budget", type=int, default=config.BACKFILL_RACES_PER_RUN)
    parser.add_argument("--season", type=int, default=None, help="domyślnie: bieżący sezon")
    args = parser.parse_args(argv)
    now = datetime.now(timezone.utc)
    try:
        season = args.season or resolve_season(now, default_clients(now.year).jolpica)
        report = ensure_aggregates(HistoryStore(args.out / "history"), default_clients(season),
                                   list(range(config.FIRST_BACKFILL_SEASON, season + 1)), args.budget)
    except JolpicaError as exc:
        print(f"BŁĄD: {exc}. Nic nie zapisano w tym przebiegu.", file=sys.stderr)
        return 1
    print(f"Zapisano {report.created}, do ponowienia {report.retry_later}, pozostało {report.remaining}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
