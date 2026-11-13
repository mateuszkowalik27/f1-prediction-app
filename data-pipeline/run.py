"""Pipeline: pobiera dane, liczy predykcje i zapisuje pliki JSON dla aplikacji.

Użycie:  python data-pipeline/run.py --out public/data
Zasada: najpierw pobieramy i liczymy wszystko, dopiero potem zapisujemy. Awaria Jolpica = żaden plik
nie jest nadpisany i kod wyjścia 1. Brak opcjonalnych źródeł (OpenF1, Open-Meteo) tylko wyłącza czynniki.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Callable

import config
from backfill import ensure_aggregates
from calibration import apply_tau, load_calibration
from factors.base import combine_side
from factors.context import build_context, race_from_history  # noqa: F401  (build_context eksportowany dla testów)
from factors.registry import ALL_FACTORS
from factors.reliability import dnf_rates
from factors.track_profile import get_profile, load_estimates
from factors.track_stats import compute_track_stats, default_track_stats
from factors.tyre_deg_fit import track_deg_ratio
from evaluation import RoundCase, evaluate, prepare_rounds, score_rounds
from fetch.jolpica import JolpicaClient, JolpicaError
from history_store import HistoryStore
from results import update_results
from fetch.openf1 import OpenF1Client
from fetch.openmeteo import fetch_forecast, wet_races
from optional import optional as _optional
from schemas import (
    Calendar, DriverEntry, DriverProbability, FrozenPrediction, HistoricRace, Meta, ModelPayload, ProfileCache, Race,
    GridPenalty, SafetyCarOdds, SeasonScore, Session, TrackProfile, WeatherForecast, WeekendPayload, WeekendResponse, WetCache,
    WeightsFile,
)
from simulate.noise import chaos_prob_from
from simulate.qualifying import predict_qualifying
from simulate.race import apply_early_season, simulate_race
from simulate.strategy import predict_strategy
from statistics import mean
from tuning import MIN_ROUNDS, append_snapshot, tune_weights

RACE_DURATION = timedelta(hours=3)
QUALIFYING_DURATION = timedelta(hours=2)
SEASON_GRACE = timedelta(days=7)    # tyle czekamy po ostatnim wyścigu, zanim uznamy sezon za zamknięty (wyniki mogą się jeszcze zmienić)
HISTORY_SEASONS = 8                 # ile sezonów wstecz sięgamy po historię toru
MAX_PROFILE_FETCHES_PER_RUN = 3     # telemetria jest wolna: profile torów uzupełniamy stopniowo
EXTRA_WEIGHT_KEYS = ("grid_base_weight", "race_noise_base")


@dataclass
class Clients:
    jolpica: JolpicaClient
    openf1: OpenF1Client
    forecast: Callable[..., WeatherForecast | None] = fetch_forecast   # (lat, lon, dzień, start_utc=...)
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


def resolve_season(now_utc: datetime, jolpica) -> int:
    """Bieżący sezon: rok kalendarzowy, dopóki trwa (plus tydzień po ostatnim wyścigu, żeby wyniki były ostateczne
    zanim trafią do niezmiennego cache'u); potem następny, jeśli jego kalendarz jest już znany."""
    year = now_utc.year
    races = jolpica.calendar(year)
    if any((_race_start(r) is None) or _race_start(r) + SEASON_GRACE > now_utc for r in races):
        return year
    return year + 1 if jolpica.calendar(year + 1) else year


def actual_qualifying(race: Race, now_utc: datetime, jolpica) -> tuple[dict[str, int], list[DriverEntry]] | None:
    """Rzeczywista siatka i lista kierowców po kwalifikacjach (obejmuje zastępstwa), a wcześniej None."""
    quali = next((s.start_utc for s in race.sessions if s.name == "Qualifying"), None)
    if not quali or quali + QUALIFYING_DURATION > now_utc:
        return None
    try:
        return jolpica.qualifying_result(race.season, race.round)
    except JolpicaError:
        return None


@dataclass(frozen=True)
class StartGrid:
    grid: dict[str, int]            # siatka startowa wyścigu (z karami, gdy ją znamy)
    quali: dict[str, int]           # klasyfikacja kwalifikacji (bez kar)
    entries: list[DriverEntry]
    source: str                     # "official" | "qualifying"
    penalties: list[GridPenalty]


def resolve_start_grid(race: Race, now_utc: datetime, clients: Clients) -> StartGrid | None:
    """None przed kwalifikacjami. Po nich: oficjalna siatka z kar (OpenF1), a gdy jej brak lub źródło zawiodło,
    kolejność kwalifikacji. Kierowca bez miejsca w oficjalnej siatce (start z alei) trafia na koniec."""
    base = actual_qualifying(race, now_utc, clients.jolpica)
    if not base:
        return None
    quali, entries = base
    official, _ = _optional("siatka startowa (OpenF1)", clients.openf1.starting_grid, race, entries)
    if not official or sum(d in official for d in quali) < len(quali) - config.GRID_MAX_MISSING:
        # brak siatki albo niepełna/źle zmapowana (brakuje więcej kierowców niż start z alei): nie zgadujemy kar
        return StartGrid(quali, quali, entries, "qualifying", [])
    known = {e.driver_id for e in entries}
    ordered = sorted((d for d in official if d in known), key=lambda d: official[d])
    ordered += sorted((d for d in quali if d not in ordered), key=lambda d: quali[d])
    grid = {d: i + 1 for i, d in enumerate(ordered)}
    penalties = [GridPenalty(driver_id=d, from_pos=quali[d], to_pos=grid[d])
                 for d in sorted(grid, key=grid.get) if d in quali and grid[d] > quali[d]]
    return StartGrid(grid, quali, entries, "official", penalties)


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
            trace, _ = _optional("telemetria toru", openf1.speed_trace, needed[cid])
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
    defaults = config.default_weights()
    stored = _load_model(out_dir / "weights.json", WeightsFile)
    if stored is None:
        return WeightsFile(weights=defaults, history=[])
    return WeightsFile(weights={**defaults, **stored.weights}, history=stored.history)


def _predict_weekend(race: Race, season: int, now_utc: datetime, clients: Clients, weights: dict[str, float],
                     profile_cache: dict[str, TrackProfile], aggregates=()):
    j, f1 = clients.jolpica, clients.openf1
    entries: list[DriverEntry] = j.entries(season)
    lineup = "latest_race"
    if not entries:  # początek sezonu: klasyfikacja jeszcze pusta, składu nie znamy
        entries, lineup = j.entries(season - 1), "previous_season"
    if not entries:
        raise JolpicaError("brak listy kierowców")
    history = [h for h in j.season_results(season - 1, 99) + (j.season_results(season, race.round - 1)
                                                              if race.round > 1 else []) if h.results]
    older = [h for s in range(season - HISTORY_SEASONS, season - 1) for h in j.season_results(s, 99) if h.results]
    circuit_history = [h for h in j.circuit_history(race.circuit_id, list(range(season - HISTORY_SEASONS, season + 1)))
                       if h.results]
    latest = max(history, key=lambda h: (h.season, h.round), default=None)
    if latest:  # klasyfikacja zawiera też kierowców, którzy już nie jadą (zastępstwa): bierzemy ostatnią stawkę
        active = {r.driver_id for r in latest.results}
        entries = [e for e in entries if e.driver_id in active] or entries
    start_grid = resolve_start_grid(race, now_utc, clients)
    if start_grid:  # po kwalifikacjach znamy prawdziwy skład (także zastępstwa) i siatkę (z karami)
        actual_grid, entries = start_grid.grid, start_grid.entries
        lineup = "qualifying"
    else:
        actual_grid = None

    wet = clients.wet(history + circuit_history)
    start = _race_start(race)
    weather, weather_failed = (
        _optional("prognoza pogody", lambda: clients.forecast(race.lat, race.lon, start.date(), start_utc=start))
        if start else (None, False))
    practice, f1a = _optional("treningi OpenF1", f1.practice_pace, race, entries)
    safety, f1b = _optional("safety car OpenF1", f1.safety_events, race.circuit_id, circuit_history)
    tyre, f1c = _optional("opony OpenF1", f1.tyre_history, race.circuit_id, circuit_history)

    track = compute_track_stats(race.circuit_id, circuit_history, safety, season,
                                config.TRACK_OVERRIDES.get(race.circuit_id),
                                default_track_stats(history + circuit_history, season))
    needed = {h.circuit_id: race_from_history(h) for h in history}
    # nadchodzący weekend nie ma jeszcze sesji: telemetrię dla tego toru bierzemy z jego ostatniego wyścigu
    last_here = max(circuit_history, key=lambda h: (h.season, h.round), default=None)
    needed[race.circuit_id] = race_from_history(last_here) if last_here else race
    profiles, new_cache = _collect_profiles(f1, needed, profile_cache, race.circuit_id)

    ctx = build_context(race, entries, history, circuit_history, wet, weather, practice, None, track,
                        profiles.get(race.circuit_id), profiles, as_of_round=race.round, aggregates=aggregates,
                        long_history=older + history)
    combined = combine_side(ctx, ALL_FACTORS, weights, "race")            # siła wyścigowa
    quali_combined = combine_side(ctx, ALL_FACTORS, weights, "quali")     # siła kwalifikacyjna (jedno okrążenie)
    drivers = [e.driver_id for e in entries]

    rain = weather.rain_probability if weather else 0.0
    teams = {e.driver_id: e.team_id for e in entries}
    noise = {"teams": teams, "team_share": weights.get("team_noise_share", config.TEAM_NOISE_SHARE),
             "chaos_mult": weights.get("chaos_mult", config.CHAOS_MULT)}
    quali = predict_qualifying(quali_combined.strength, noise=weights.get("quali_noise", config.QUALIFYING_NOISE),
                               chaos_prob=chaos_prob_from(weights, sc=0.0, rain=rain), **noise)
    quali_rows = _actual_quali_rows(start_grid.quali, drivers) if start_grid else quali.probabilities
    dnf, sim_track = apply_early_season(dnf_rates(ctx), track, race.round)
    strategy = predict_strategy(track, weather, tyre, track_deg_ratio(ctx))
    race_rows = simulate_race(   # bez siatki (przed kwalifikacjami) losujemy ją w każdej symulacji
        combined.strength, actual_grid, sim_track, dnf, strategy.primary.stops,
        grid_weight=weights.get("grid_base_weight", config.GRID_BASE_WEIGHT),
        noise_base=weights.get("race_noise_base", config.RACE_NOISE_BASE),
        qualifying_noise=weights.get("quali_noise", config.QUALIFYING_NOISE),
        quali_strength=quali_combined.strength,     # siatka przed kwalifikacjami losowana z siły kwalifikacyjnej
        chaos_prob=chaos_prob_from(weights, sc=sim_track.sc_probability, rain=rain), **noise,
    )
    sources = {
        "open_meteo": "failed" if weather_failed else ("ok" if weather else "missing"),
        "openf1": "failed" if (f1a or f1b or f1c) else ("ok" if (practice or safety or tyre) else "missing"),
    }
    profile = profiles.get(race.circuit_id)
    payload = WeekendPayload(
        race=race, weather=weather, strategy=strategy,
        safety_car=SafetyCarOdds(sc=track.sc_probability, vsc=track.vsc_probability),
        qualifying=quali_rows, race_prediction=race_rows,
        factors_used=combined.used, factors_skipped=combined.skipped,
        low_data=combined.low_data or sources["openf1"] != "ok",   # brak OpenF1 = mało danych (spec §3)
        lineup=lineup, grid_source=start_grid.source if start_grid else "predicted",
        penalties=start_grid.penalties if start_grid else [], track_source=track.source, track_sample_size=track.sample_size,
        profile_source=profile.source if profile else None,
    )
    return payload, sources, new_cache


def _load_oos(out_dir: Path) -> list[SeasonScore]:
    try:
        return [SeasonScore(**row) for row in json.loads((out_dir / "oos.json").read_text(encoding="utf-8"))]
    except (OSError, ValueError, TypeError):
        return []


def _backfill_history(store: HistoryStore, clients: Clients, season: int, now: datetime) -> None:
    """Uzupełnia historię agregatów w ramach budżetu. To dodatek, nie warunek działania: każdy błąd (też Jolpica)
    tylko pomija uzupełnianie; o przerwaniu przebiegu decydują główne zapytania."""
    try:
        ensure_aggregates(store, clients, list(range(config.FIRST_BACKFILL_SEASON, season + 1)),
                          config.BACKFILL_RACES_PER_RUN, now=now)
    except Exception as exc:  # noqa: BLE001
        print(f"UWAGA: uzupełnianie historii nie zadziałało ({type(exc).__name__}: {exc}); pomijam.", file=sys.stderr)


def _update_results(out_dir: Path, calendar: list[Race], clients: Clients, now: datetime) -> None:
    """Wyniki sesji do Kalendarza: dodatek, każdy błąd tylko pomija uzupełnianie."""
    try:
        update_results(out_dir, calendar, clients, now)
    except Exception as exc:  # noqa: BLE001
        print(f"UWAGA: wyniki sesji nie zadziałały ({type(exc).__name__}: {exc}); pomijam.", file=sys.stderr)


def _live_evaluation(out_dir: Path, season: int, cases: list[RoundCase]):
    """Ocena przewidywań zapisanych tuż przed startem wyścigu (tych, które użytkownik faktycznie widział)."""
    result = []
    for case in cases:
        frozen = _load_model(out_dir / "predictions" / f"{season}-{case.round}.json", FrozenPrediction)
        if frozen:
            result.append(evaluate(case.round, frozen.race_prediction, case.actual_finish))
    return result


def _tuned_weights(out_dir: Path, cases: list[RoundCase], season: int) -> WeightsFile:
    """Wagi z weights.json; po każdej nowej rundzie (od MIN_ROUNDS) dostrajane od nowa z wartości z configu."""
    stored = _load_weights(out_dir)
    if not config.USE_TUNED_WEIGHTS:
        return stored.model_copy(update={"weights": config.default_weights()})   # historia strojenia zostaje, wagi bazowe
    if len(cases) < MIN_ROUNDS:
        return stored
    last_round = cases[-1].round
    if stored.history and (stored.history[-1].season, stored.history[-1].round) == (season, last_round):
        return stored
    # czynnik bez żadnych danych w teście wstecznym (pogoda, treningi) nie ma na co wpływać: nie stroimy go
    untestable = {name for name in config.FACTOR_WEIGHTS if all(c.factor_scores.get(name) is None for c in cases)}
    tuned = tune_weights(
        config.default_weights(), config.WEIGHT_BOUNDS, set(config.LOCKED_WEIGHTS) | untestable, len(cases),
        lambda w: mean(e.brier_win for e in score_rounds(cases, w, config.N_SIMULATIONS_TUNING)),
    )
    return append_snapshot(stored, tuned, last_round, season)


def _cached_wet(wet_fn, flags: dict[str, bool]):
    """Opakowuje wykrywanie mokrych wyścigów: odpytuje API tylko o wyścigi, których jeszcze nie znamy."""
    def wet(races: list[HistoricRace]) -> dict[tuple[int, int], bool]:
        missing = [h for h in races if f"{h.season}-{h.round}" not in flags]
        if missing:
            flags.update({f"{s}-{r}": v for (s, r), v in wet_fn(missing).items()})
        return {(h.season, h.round): flags[f"{h.season}-{h.round}"]
                for h in races if f"{h.season}-{h.round}" in flags}
    return wet


def run_pipeline(out_dir: Path, season: int, now_utc: datetime, clients: Clients) -> Meta:
    out_dir = Path(out_dir)
    wet_stored = _load_model(out_dir / "wet_cache.json", WetCache)
    wet_flags = dict(wet_stored.flags) if wet_stored else {}
    clients = replace(clients, wet=_cached_wet(clients.wet, wet_flags))
    calendar = clients.jolpica.calendar(season)       # awaria Jolpica kończy się tu, zanim cokolwiek zapiszemy
    standings = clients.jolpica.standings(season)
    if standings.drivers:
        standings = standings.model_copy(update={"season": season})
    else:  # nowy sezon bez wyników: pokazujemy ostatnią zakończoną tabelę z oznaczeniem sezonu
        previous = clients.jolpica.standings(season - 1)
        standings = previous.model_copy(update={"season": season - 1}) if previous.drivers else standings
    store = HistoryStore(out_dir / "history")
    _backfill_history(store, clients, season, now_utc)
    _update_results(out_dir, calendar, clients, now_utc)
    aggregates = store.all()
    cases = prepare_rounds(season, clients, calendar, aggregates)   # awaria Jolpica przerywa przebieg: pliki zostają nietknięte
    weights_file = _tuned_weights(out_dir, cases, season)
    cache = _load_model(out_dir / "track_profiles.json", ProfileCache)
    profile_cache = cache.profiles if cache else {}

    sources = {"jolpica": "ok", "open_meteo": "missing", "openf1": "missing"}
    race = select_next_race(calendar, now_utc)
    frozen = None
    if race is None:
        weekend = WeekendResponse(status="no_upcoming_race", payload=None)
        used, skipped, new_cache = [], [], profile_cache
    else:
        payload, extra, new_cache = _predict_weekend(race, season, now_utc, clients, weights_file.weights, profile_cache,
                                                     aggregates)
        calibration = load_calibration(out_dir / "calibration.json")
        # kalibracja była dopasowana na przewidywaniach ze znaną siatką: przed kwalifikacjami (siatka losowana) jej nie stosujemy
        if calibration and calibration.tau != 1.0 and payload.grid_source != "predicted":
            payload = payload.model_copy(update={"race_prediction": apply_tau(payload.race_prediction, calibration.tau)})
        weekend = WeekendResponse(status="ok", payload=payload)
        sources.update(extra)
        used, skipped = payload.factors_used, payload.factors_skipped
        start = _race_start(race)
        if start is None or now_utc < start:   # po starcie wyścigu przewidywania już nie nadpisujemy
            frozen = FrozenPrediction(season=season, round=race.round, saved_at=now_utc,
                                      race_prediction=payload.race_prediction)

    meta = Meta(generated_at=now_utc, season=season, data_sources=sources)
    evaluation = score_rounds(cases, weights_file.weights, config.N_SIMULATIONS_TUNING) if cases else []
    model = ModelPayload(weights=weights_file.weights, weight_history=weights_file.history,
                         factors_used=used, factors_skipped=skipped, evaluation=evaluation,
                         live_evaluation=_live_evaluation(out_dir, season, cases), out_of_sample=_load_oos(out_dir))

    out_dir.mkdir(parents=True, exist_ok=True)         # wszystko policzone i zwalidowane: zapisujemy
    _write(out_dir / "calendar.json", Calendar(season=season, races=calendar))
    _write(out_dir / "standings.json", standings)
    _write(out_dir / "weekend.json", weekend)
    _write(out_dir / "model.json", model)
    if frozen:
        (out_dir / "predictions").mkdir(exist_ok=True)
        _write(out_dir / "predictions" / f"{season}-{frozen.round}.json", frozen)
    if new_cache != profile_cache:
        _write(out_dir / "track_profiles.json", ProfileCache(profiles=new_cache))
    if weights_file != _load_model(out_dir / "weights.json", WeightsFile) and weights_file.history:
        _write(out_dir / "weights.json", weights_file)
    if wet_stored is None or wet_flags != wet_stored.flags:
        _write(out_dir / "wet_cache.json", WetCache(flags=wet_flags))
    _write(out_dir / "meta.json", meta)
    return meta


def main(argv: list[str] | None = None, clients: Clients | None = None) -> int:
    parser = argparse.ArgumentParser(description="Aktualizacja danych F1 Prediction App")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--season", type=int, default=None, help="domyślnie: wybierany automatycznie")
    args = parser.parse_args(argv)
    now = datetime.now(timezone.utc)
    try:
        if args.season is None:
            probe = clients or default_clients(now.year)
            season = resolve_season(now, probe.jolpica)
        else:
            season = args.season
        run_pipeline(args.out, season, now, clients or default_clients(season))
    except JolpicaError as exc:
        print(f"BŁĄD: {exc}. Pliki nie zostały zmienione.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
