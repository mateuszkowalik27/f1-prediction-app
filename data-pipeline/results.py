"""Wyniki zakończonych sesji weekendu (public/data/results/<sezon>-<runda>.json), pokazywane w Kalendarzu.

Wyniki pojawiają się kilka minut po końcu sesji (RESULTS_DELAY_MINUTES) i są odświeżane przez RESULTS_SETTLE_HOURS,
bo źródła dopisują dane z opóźnieniem; potem tabela zostaje już jak jest. Awaria któregokolwiek źródła tylko pomija
daną sesję: to dodatek do prognoz, nie warunek ich działania.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import config
from fetch.jolpica import JolpicaError
from optional import optional
from schemas import Race, RoundResults, SessionTable

if TYPE_CHECKING:
    from run import Clients

SESSION_LENGTH = {"FP1": 1.0, "FP2": 1.0, "FP3": 1.0, "SprintQualifying": 1.0, "Sprint": 1.0, "Qualifying": 1.0, "Race": 2.5}   # godziny
FROM_OPENF1 = ("FP1", "FP2", "FP3", "SprintQualifying")


def results_path(out_dir: Path, season: int, round: int) -> Path:
    return Path(out_dir) / "results" / f"{season}-{round}.json"


def load_results(path: Path) -> RoundResults | None:
    try:
        return RoundResults.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _end(race: Race, name: str) -> datetime | None:
    session = next((s for s in race.sessions if s.name == name), None)
    if session is None or session.start_utc is None:
        return None
    return session.start_utc + timedelta(hours=SESSION_LENGTH[name])


def _due(race: Race, existing: RoundResults | None, now: datetime) -> list[str]:
    """Sesje, dla których trzeba (znów) pobrać wyniki: brakujące po końcu sesji albo jeszcze świeże (do ustabilizowania)."""
    have = existing.sessions if existing else {}
    tried = existing.attempts if existing else {}
    due = []
    for s in race.sessions:
        end = _end(race, s.name)
        if end is None or end + timedelta(minutes=config.RESULTS_DELAY_MINUTES) > now:
            continue
        table = have.get(s.name)
        if table is None:
            if tried.get(s.name, 0) < config.RESULTS_MAX_ATTEMPTS:
                due.append(s.name)
        elif table.fetched_at is not None and table.fetched_at < end + timedelta(hours=config.RESULTS_SETTLE_HOURS):
            due.append(s.name)          # pobrane tuż po sesji: odświeżamy, dopóki źródła mogą coś dopisywać
    return due


def build_results(race: Race, now: datetime, clients: "Clients", existing: RoundResults | None) -> RoundResults | None:
    """Dokłada tabele brakujących, zakończonych sesji do już zapisanych. None = nic nowego."""
    have = dict(existing.sessions) if existing else {}
    tried = dict(existing.attempts) if existing else {}
    due = _due(race, existing, now)
    if not due:
        return None
    j, f1 = clients.jolpica, clients.openf1
    new: dict[str, SessionTable] = {}

    def jolpica(label: str, fn, *args):
        try:
            return fn(*args)
        except JolpicaError as exc:
            print(f"UWAGA: wyniki ({label}) niedostępne: {exc}", file=sys.stderr)
            return None

    if "Race" in due and (rows := jolpica("wyścig", j.race_table, race.season, race.round)):
        new["Race"] = SessionTable(kind="race", rows=rows)
    if "Sprint" in due and (rows := jolpica("sprint", j.race_table, race.season, race.round, True)):
        new["Sprint"] = SessionTable(kind="race", rows=rows)
    if "Qualifying" in due and (rows := jolpica("kwalifikacje", j.qualifying_table, race.season, race.round)):
        new["Qualifying"] = SessionTable(kind="qualifying", rows=rows)
    if any(name in due for name in FROM_OPENF1):
        entries = jolpica("skład", j.entries, race.season) or []
        laps, _ = optional("najlepsze okrążenia (OpenF1)", f1.best_laps, race, entries)
        for name, table in (laps or {}).items():
            if name in due:
                new[name] = table
    new = {name: table.model_copy(update={"fetched_at": now}) for name, table in new.items()}
    for name in due:
        if name not in new and name not in have:
            tried[name] = tried.get(name, 0) + 1
    if not new and tried == (existing.attempts if existing else {}):
        return None
    return RoundResults(season=race.season, round=race.round, generated_at=now, sessions={**have, **new}, attempts=tried)


def update_results(out_dir: Path, calendar: list[Race], clients: "Clients", now: datetime,
                   budget: int = config.RESULTS_ROUNDS_PER_RUN) -> int:
    """Uzupełnia pliki wyników rund (od najnowszych) w ramach budżetu. Zwraca liczbę zapisanych plików."""
    written = tried = 0
    for race in sorted(calendar, key=lambda r: r.round, reverse=True):
        if tried >= budget:
            break
        path = results_path(out_dir, race.season, race.round)
        existing = load_results(path)
        if not _due(race, existing, now):
            continue
        tried += 1
        updated = build_results(race, now, clients, existing)
        if updated is None:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(updated.model_dump_json(), encoding="utf-8")
        os.replace(tmp, path)
        written += 1
    return written


def main(argv: list[str] | None = None) -> int:
    """Lekki przebieg samych wyników sesji (uruchamiany często w weekend wyścigowy, osobno od pełnych prognoz)."""
    import argparse

    from run import default_clients, resolve_season

    parser = argparse.ArgumentParser(description="Wyniki zakończonych sesji do Kalendarza")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--season", type=int, default=None, help="domyślnie: bieżący sezon")
    args = parser.parse_args(argv)
    now = datetime.now(timezone.utc)
    try:
        season = args.season or resolve_season(now, default_clients(now.year).jolpica)
        clients = default_clients(season)
        written = update_results(args.out, clients.jolpica.calendar(season), clients, now)
    except JolpicaError as exc:
        print(f"BŁĄD: {exc}. Nic nie zapisano.", file=sys.stderr)
        return 1
    print(f"Zapisano wyników: {written}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
