"""Pipeline: pobiera dane, liczy predykcje i zapisuje pliki JSON dla aplikacji.

Użycie:  python data-pipeline/run.py --out public/data
Zasada: najpierw pobieramy i liczymy wszystko, dopiero potem zapisujemy. Awaria Jolpica = żaden plik
nie jest nadpisany i kod wyjścia 1. Brak opcjonalnych źródeł (OpenF1, Open-Meteo) tylko wyłącza czynniki.
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Callable

import config
from factors.base import RaceContext, combine
from factors.car_pace import CarPace
from factors.car_track_fit import CarTrackFit
from factors.driver_form import DriverForm
from factors.practice_pace import PracticePace, WeekendShift
from factors.reliability import Reliability, dnf_rates
from factors.track_history import TrackHistory
from factors.track_profile import get_profile, load_estimates
from factors.track_stats import compute_track_stats, default_track_stats
from factors.wet_skill import WetSkill
from fetch.jolpica import JolpicaClient, JolpicaError
from fetch.openf1 import OpenF1Client
from fetch.openmeteo import fetch_forecast, wet_races
from schemas import (
    Calendar, DriverEntry, DriverProbability, HistoricRace, Meta, ModelPayload, ProfileCache, Race,
    SafetyCarOdds, Session, TrackProfile, WeatherForecast, WeekendPayload, WeekendResponse,
    WeightsFile,
)
from simulate.qualifying import predict_qualifying
from simulate.race import apply_early_season, simulate_race
from simulate.strategy import predict_strategy

RACE_DURATION = timedelta(hours=3)
QUALIFYING_DURATION = timedelta(hours=2)
HISTORY_SEASONS = 8                 # ile sezonów wstecz sięgamy po historię toru
MAX_PROFILE_FETCHES_PER_RUN = 3     # telemetria jest wolna: profile torów uzupełniamy stopniowo
EXTRA_WEIGHT_KEYS = ("grid_base_weight", "race_noise_base")


@dataclass
class Clients:
    jolpica: JolpicaClient
    openf1: OpenF1Client
    forecast: Callable[[float, float, date], WeatherForecast | None] = fetch_forecast
    wet: Callable[[list[HistoricRace]], dict[tuple[int, int], bool]] = wet_races


CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache" / "jolpica"


def default_clients(season: int) -> Clients:
    # Zakończone sezony (rok < bieżący) są niezmienne: trzymamy je na dysku, żeby nie przekraczać limitu Jolpica.
    return Clients(jolpica=JolpicaClient(cache_dir=CACHE_DIR, immutable_before=season), openf1=OpenF1Client())


# --- wybór rundy i siatki ---
def _race_start(race: Race) -> datetime | None:
    for s in race.sessions:
        if s.name == "Race" and s.start_utc:
            return s.start_utc
    known = [s.start_utc for s in race.sessions if s.start_utc]
    return max(known) if known else None


def select_next_race(races: list[Race], now_utc: datetime) -> Race | None:
    """Pierwsza runda, której wyścig jeszcze się nie skończył. Runda bez żadnych godzin jest nadchodząca."""
    for race in sorted(races, key=lambda r: r.round):
        start = _race_start(race)
        if start is None or start + RACE_DURATION > now_utc:
            return race
    return None


def resolve_grid(race: Race, now_utc: datetime, jolpica, predicted: dict[str, int]) -> tuple[dict[str, int], str]:
    quali = next((s.start_utc for s in race.sessions if s.name == "Qualifying"), None)
    if quali and quali + QUALIFYING_DURATION <= now_utc:
        try:
            actual = jolpica.qualifying_grid(race.season, race.round)
        except JolpicaError:
            actual = None
        if actual:
            return actual, "actual"
    return predicted, "predicted"


def _actual_quali_rows(grid: dict[str, int], drivers: list[str]) -> list[DriverProbability]:
    count = len(drivers)
    rows = []
    for d in sorted(drivers):
        pos = grid.get(d) or count
        dist = [0.0] * count
        dist[min(pos, count) - 1] = 1.0
        rows.append(DriverProbability(driver_id=d, win=float(pos == 1), podium=float(pos <= 3), points=0.0,
                                      expected_points=0.0, position_distribution=dist))
    return rows


# --- kontekst ---
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


def _race_from_history(h: HistoricRace) -> Race:
    return Race(season=h.season, round=h.round, name=f"{h.season} R{h.round}", circuit_id=h.circuit_id,
                country="", lat=h.lat, lon=h.lon, is_sprint=False,
                sessions=[Session(name="Race", start_utc=datetime.combine(h.date, time(13, 0), tzinfo=timezone.utc))])


def _collect_profiles(openf1, needed: dict[str, Race], cache: dict[str, TrackProfile], current: str):
    """Profile torów: nadpisanie > cache z telemetrii > świeża telemetria (limit na przebieg) > szacunek."""
    estimates = load_estimates()
    profiles: dict[str, TrackProfile] = {}
    new_cache = dict(cache)
    fetches = 0
    for cid in [current] + [c for c in needed if c != current]:
        if cid in config.TRACK_PROFILE_OVERRIDES:
            profiles[cid] = config.TRACK_PROFILE_OVERRIDES[cid]
            continue
        if cid in cache:
            profiles[cid] = cache[cid]
            continue
        trace = None
        if fetches < MAX_PROFILE_FETCHES_PER_RUN:
            fetches += 1
            trace = openf1.speed_trace(needed[cid])
        profile = get_profile(cid, trace, estimates, None)
        if profile is not None:
            profiles[cid] = profile
            if profile.source == "telemetry":
                new_cache[cid] = profile
    return profiles, new_cache


# --- pliki ---
def _write(path: Path, model) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(model.model_dump_json(), encoding="utf-8")
    os.replace(tmp, path)


def _load_model(path: Path, model_type):
    try:
        return model_type.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _load_weights(out_dir: Path) -> WeightsFile:
    defaults = {**config.FACTOR_WEIGHTS, "grid_base_weight": config.GRID_BASE_WEIGHT,
                "race_noise_base": config.RACE_NOISE_BASE}
    stored = _load_model(out_dir / "weights.json", WeightsFile)
    if stored is None:
        return WeightsFile(weights=defaults, history=[])
    return WeightsFile(weights={**defaults, **stored.weights}, history=stored.history)


FACTORS = [CarPace(), DriverForm(), TrackHistory(), PracticePace(), WeekendShift(), CarTrackFit(), WetSkill(),
           Reliability()]


def _predict_weekend(race: Race, season: int, now_utc: datetime, clients: Clients, weights: dict[str, float],
                     profile_cache: dict[str, TrackProfile]):
    j, f1 = clients.jolpica, clients.openf1
    entries: list[DriverEntry] = j.entries(season) or j.entries(season - 1)
    if not entries:
        raise JolpicaError("brak listy kierowców")
    history = [h for h in j.season_results(season - 1, 99) + (j.season_results(season, race.round - 1)
                                                              if race.round > 1 else []) if h.results]
    circuit_history = [h for h in j.circuit_history(race.circuit_id, list(range(season - HISTORY_SEASONS, season + 1)))
                       if h.results]
    latest = max(history, key=lambda h: (h.season, h.round), default=None)
    if latest:  # klasyfikacja zawiera też kierowców, którzy już nie jadą (zastępstwa): bierzemy ostatnią stawkę
        active = {r.driver_id for r in latest.results}
        entries = [e for e in entries if e.driver_id in active] or entries

    wet = clients.wet(history + circuit_history)
    start = _race_start(race)
    weather = clients.forecast(race.lat, race.lon, start.date()) if start else None
    practice = f1.practice_pace(race, entries)
    safety = f1.safety_events(race.circuit_id, circuit_history)
    tyre = f1.tyre_history(race.circuit_id, circuit_history)

    track = compute_track_stats(race.circuit_id, circuit_history, safety, season,
                                config.TRACK_OVERRIDES.get(race.circuit_id),
                                default_track_stats(history + circuit_history, season))
    needed = {h.circuit_id: _race_from_history(h) for h in history}
    # nadchodzący weekend nie ma jeszcze sesji: telemetrię dla tego toru bierzemy z jego ostatniego wyścigu
    last_here = max(circuit_history, key=lambda h: (h.season, h.round), default=None)
    needed[race.circuit_id] = _race_from_history(last_here) if last_here else race
    profiles, new_cache = _collect_profiles(f1, needed, profile_cache, race.circuit_id)

    ctx = build_context(race, entries, history, circuit_history, wet, weather, practice, None, track,
                        profiles.get(race.circuit_id), profiles, as_of_round=race.round)
    combined = combine(ctx, FACTORS, weights)
    drivers = [e.driver_id for e in entries]

    quali = predict_qualifying(combined.strength)
    grid, grid_source = resolve_grid(race, now_utc, j, quali.predicted_grid)
    quali_rows = _actual_quali_rows(grid, drivers) if grid_source == "actual" else quali.probabilities

    dnf, sim_track = apply_early_season(dnf_rates(replace(ctx, grid=grid)), track, race.round)
    strategy = predict_strategy(track, weather, tyre)
    race_rows = simulate_race(
        combined.strength, grid, sim_track, dnf, strategy.primary.stops,
        grid_weight=weights.get("grid_base_weight", config.GRID_BASE_WEIGHT),
        noise_base=weights.get("race_noise_base", config.RACE_NOISE_BASE),
    )
    payload = WeekendPayload(
        race=race, weather=weather, strategy=strategy,
        safety_car=SafetyCarOdds(sc=track.sc_probability, vsc=track.vsc_probability),
        qualifying=quali_rows, race_prediction=race_rows,
        factors_used=combined.used, factors_skipped=combined.skipped, low_data=combined.low_data,
    )
    sources = {"open_meteo": "ok" if weather else "missing",
               "openf1": "ok" if (practice or safety or tyre) else "missing"}
    return payload, sources, new_cache


def run_pipeline(out_dir: Path, season: int, now_utc: datetime, clients: Clients) -> Meta:
    out_dir = Path(out_dir)
    calendar = clients.jolpica.calendar(season)       # awaria Jolpica kończy się tu, zanim cokolwiek zapiszemy
    standings = clients.jolpica.standings(season)
    weights_file = _load_weights(out_dir)
    cache = _load_model(out_dir / "track_profiles.json", ProfileCache)
    profile_cache = cache.profiles if cache else {}

    sources = {"jolpica": "ok", "open_meteo": "missing", "openf1": "missing"}
    race = select_next_race(calendar, now_utc)
    if race is None:
        weekend = WeekendResponse(status="no_upcoming_race", payload=None)
        used, skipped, new_cache = [], [], profile_cache
    else:
        payload, extra, new_cache = _predict_weekend(race, season, now_utc, clients, weights_file.weights, profile_cache)
        weekend = WeekendResponse(status="ok", payload=payload)
        sources.update(extra)
        used, skipped = payload.factors_used, payload.factors_skipped

    meta = Meta(generated_at=now_utc, season=season, data_sources=sources)
    model = ModelPayload(weights=weights_file.weights, weight_history=weights_file.history,
                         factors_used=used, factors_skipped=skipped, evaluation=[])

    out_dir.mkdir(parents=True, exist_ok=True)         # wszystko policzone i zwalidowane: zapisujemy
    _write(out_dir / "calendar.json", Calendar(season=season, races=calendar))
    _write(out_dir / "standings.json", standings)
    _write(out_dir / "weekend.json", weekend)
    _write(out_dir / "model.json", model)
    if new_cache != profile_cache:
        _write(out_dir / "track_profiles.json", ProfileCache(profiles=new_cache))
    _write(out_dir / "meta.json", meta)
    return meta


def main(argv: list[str] | None = None, clients: Clients | None = None) -> int:
    parser = argparse.ArgumentParser(description="Aktualizacja danych F1 Prediction App")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--season", type=int, default=config.SEASON)
    args = parser.parse_args(argv)
    try:
        run_pipeline(args.out, args.season, datetime.now(timezone.utc), clients or default_clients(args.season))
    except JolpicaError as exc:
        print(f"BŁĄD: {exc}. Pliki nie zostały zmienione.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
