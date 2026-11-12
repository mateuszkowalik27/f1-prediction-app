"""Wyniki zakończonych sesji weekendu (public/data/results/<sezon>-<runda>.json), pokazywane w Kalendarzu.

Raz zapisanej tabeli sesji nie przeliczamy. Sesji kończącej się przed chwilą nie ruszamy (RESULTS_DELAY): źródła
dopisują dane z opóźnieniem, a zamrożenie połowicznych wyników byłoby na stałe. Awaria któregokolwiek źródła
tylko pomija daną sesję: to dodatek do prognoz, nie warunek ich działania.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
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


def _ended(race: Race, name: str, now: datetime) -> bool:
    session = next((s for s in race.sessions if s.name == name), None)
    if session is None or session.start_utc is None:
        return False
    end = session.start_utc + timedelta(hours=SESSION_LENGTH[name]) + timedelta(hours=config.RESULTS_DELAY_HOURS)
    return end <= now


def build_results(race: Race, now: datetime, clients: "Clients", existing: RoundResults | None) -> RoundResults | None:
    """Dokłada tabele brakujących, zakończonych sesji do już zapisanych. None = nic nowego."""
    have = dict(existing.sessions) if existing else {}
    tried = dict(existing.attempts) if existing else {}
    due = [s.name for s in race.sessions
           if s.name not in have and _ended(race, s.name, now) and tried.get(s.name, 0) < config.RESULTS_MAX_ATTEMPTS]
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
    for name in due:
        if name not in new:
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
        have, counts = (existing.sessions, existing.attempts) if existing else ({}, {})
        if not any(s.name not in have and _ended(race, s.name, now) and counts.get(s.name, 0) < config.RESULTS_MAX_ATTEMPTS
                   for s in race.sessions):
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
