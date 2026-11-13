"""Ocena modelu: porównanie przewidywań z wynikami i test wsteczny (bez podglądania przyszłości).

Test wsteczny dla każdej rozegranej rundy buduje kontekst z samych wcześniejszych wyników, zakłada znaną
siatkę startową (jak w pipeline po kwalifikacjach) i symuluje wyścig. Pogoda, treningi i dane o safety carze
nie są dostępne historycznie, więc w teście wstecznym czynniki od nich zależne są wyłączone.
"""
from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import mean
from typing import TYPE_CHECKING

import config
from factors.base import RaceContext, combine, combine_side
from factors.context import build_context, race_from_history
from factors.registry import ALL_FACTORS
from factors.reliability import dnf_rates
from factors.track_profile import load_estimates
from factors.track_stats import compute_track_stats, default_track_stats
from fetch.jolpica import JolpicaError
from schemas import (
    DriverEntry, DriverProbability, Race, RaceAggregates, RaceEvaluation, TrackStats, WeatherForecast,
)
from scoring import ranking_rps
from simulate.qualifying import predict_qualifying
from simulate.race import apply_early_season, simulate_race
from simulate.strategy import predict_strategy

if TYPE_CHECKING:
    from run import Clients

HISTORY_SEASONS = 8


def evaluate(round: int, prediction: list[DriverProbability], actual_finish: dict[str, int | None]) -> RaceEvaluation:
    winner = next((d for d, f in actual_finish.items() if f == 1), None)
    if winner is None:
        raise ValueError(f"runda {round}: brak zwycięzcy")
    by_id = {p.driver_id: p for p in prediction}
    ranked = sorted(prediction, key=lambda p: (-p.win, -p.podium, p.driver_id))
    errors = [
        abs(sum((k + 1) * share for k, share in enumerate(by_id[d].position_distribution)) - finish)
        for d, finish in actual_finish.items() if finish is not None and d in by_id   # DNF pomijamy
    ]
    return RaceEvaluation(
        round=round,
        winner_prob=by_id[winner].win if winner in by_id else 0.0,
        winner_in_top3=winner in {p.driver_id for p in ranked[:3]},
        mean_abs_position_error=mean(errors) if errors else 0.0,
        brier_win=mean((p.win - (p.driver_id == winner)) ** 2 for p in prediction),
    )


@dataclass(frozen=True)
class RoundCase:
    """Wszystko, co niezależne od wag: pozwala ocenić wiele zestawów wag bez ponownego pobierania danych."""
    round: int
    ctx: RaceContext
    factor_scores: dict[str, dict[str, float] | None]
    dnf: dict[str, float]
    sim_track: TrackStats
    stops: int
    actual_finish: dict[str, int | None]
    actual_quali: dict[str, int] | None = None   # faktyczna kolejność kwalifikacji (bez kar); None = brak danych


class _Precomputed:
    def __init__(self, name: str, scores: dict[str, float] | None):
        self.name, self._scores = name, scores

    def score(self, ctx: RaceContext) -> dict[str, float] | None:
        return self._scores


def prepare_rounds(season: int, clients: "Clients", calendar: list[Race] | None = None,
                   aggregates: Sequence[RaceAggregates] = ()) -> list[RoundCase]:
    j = clients.jolpica
    calendar = calendar if calendar is not None else j.calendar(season)
    by_round = {r.round: r for r in calendar}
    results = sorted((h for h in j.season_results(season, 9999) if h.results), key=lambda h: h.round)
    past = [h for s in range(season - HISTORY_SEASONS, season) for h in j.season_results(s, 9999) if h.results]
    history_pool = [h for h in past if h.season == season - 1] + results
    wet = clients.wet(past + results)
    known = {e.driver_id: e for e in (j.entries(season) or j.entries(season - 1))}
    profiles = {**load_estimates(), **config.TRACK_PROFILE_OVERRIDES}

    own_temp = {(a.season, a.round): a.air_temp_c for a in aggregates if a.air_temp_c is not None}
    cases = []
    for result in results:
        if not any(r.finish == 1 for r in result.results):
            continue  # wyścig bez zwycięzcy (odwołany) nie nadaje się do oceny
        race = by_round.get(result.round) or race_from_history(result)
        entries = [known.get(r.driver_id) or DriverEntry(driver_id=r.driver_id, code=r.driver_id[:3].upper(),
                                                         name=r.driver_id, team_id=r.team_id)
                   for r in result.results]
        circuit_history = [h for h in past if h.circuit_id == race.circuit_id]
        grid = {r.driver_id: r.grid for r in result.results}
        # brak historycznych prognoz: zamiast nich faktyczna temperatura powietrza z tego wyścigu (lekko optymistyczne)
        temp = own_temp.get((season, result.round))
        standin = (WeatherForecast(rain_probability=0.0, temperature_c=temp, fetched_at=datetime.now(timezone.utc),
                                   start_temperature_c=temp) if temp is not None else None)
        pre = build_context(race, entries, history_pool, circuit_history, wet, standin, None, grid,
                            default_track_stats([], season), None, profiles, as_of_round=result.round,
                            aggregates=aggregates)
        track = compute_track_stats(race.circuit_id, pre.circuit_history, None, season,
                                    config.TRACK_OVERRIDES.get(race.circuit_id),
                                    default_track_stats(pre.history + pre.circuit_history, season))
        ctx = build_context(race, entries, history_pool, circuit_history, wet, standin, None, grid, track,
                            profiles.get(race.circuit_id), profiles, as_of_round=result.round,
                            aggregates=aggregates)
        dnf, sim_track = apply_early_season(dnf_rates(ctx), track, result.round)
        try:
            actual_quali = j.qualifying_grid(season, result.round)
        except JolpicaError:
            actual_quali = None      # brak kwalifikacji nie psuje oceny wyścigu: ten poziom jest wtedy pomijany
        cases.append(RoundCase(
            round=result.round, ctx=ctx,
            factor_scores={f.name: f.score(ctx) for f in ALL_FACTORS},
            dnf=dnf, sim_track=sim_track, stops=predict_strategy(track, None, None).primary.stops,
            actual_finish={r.driver_id: r.finish for r in result.results},
            actual_quali=actual_quali or None,
        ))
    return cases


def prepare_seasons(seasons: list[int], clients: "Clients", aggregates: Sequence[RaceAggregates] = (),
                    ) -> dict[int, list[RoundCase]]:
    """Przypadki testu wstecznego dla wielu sezonów; sezon bez rozegranych wyścigów jest pomijany."""
    by_season = {}
    for season in seasons:
        cases = prepare_rounds(season, clients, aggregates=aggregates)
        if cases:
            by_season[season] = cases
    return by_season


LEGACY_SHARED_QUALI_GAP = 0.10   # waga quali_gap w dawnym, wspólnym trybie (przed etapem 2 modelu v3), do porównań A/B


def _strengths(case: RoundCase, weights: dict[str, float], separate: bool):
    """(siła wyścigowa, siła kwalifikacyjna). `separate=False` to dawne zachowanie: jedna siła (z quali_gap) do obu."""
    factors = [_Precomputed(k, v) for k, v in case.factor_scores.items()]
    if separate:
        return (combine_side(case.ctx, factors, weights, "race").strength,
                combine_side(case.ctx, factors, weights, "quali").strength)
    shared = combine(case.ctx, factors, {**weights, "quali_gap": LEGACY_SHARED_QUALI_GAP}).strength
    return shared, shared


def _predict_case(case: RoundCase, weights: dict[str, float], n: int, grid_known: bool = True,
                  separate: bool = True) -> list[DriverProbability]:
    """`grid_known=False`: prognoza sprzed kwalifikacji (siatka losowana w każdej symulacji, z siły kwalifikacyjnej)."""
    race_strength, quali_strength = _strengths(case, weights, separate)
    return simulate_race(
        race_strength, case.ctx.grid if grid_known else None, case.sim_track, case.dnf, case.stops, n=n,
        grid_weight=weights.get("grid_base_weight", config.GRID_BASE_WEIGHT),
        noise_base=weights.get("race_noise_base", config.RACE_NOISE_BASE),
        qualifying_noise=(weights.get("quali_noise", config.QUALIFYING_NOISE) if separate else config.QUALIFYING_NOISE),
        quali_strength=quali_strength if separate else None,
    )


@dataclass(frozen=True)
class RaceLevels:
    """Ocena jednego wyścigu na trzech poziomach (RPS, mniej = lepiej)."""
    round: int
    rps_pre: float            # prognoza sprzed kwalifikacji (siatka nieznana)
    rps_post: float           # prognoza po kwalifikacjach (znana siatka)
    rps_quali: float | None   # przewidziana kolejność kwalifikacji; None bez danych
    brier_win_post: float     # dotychczasowa miara (zwycięzca) jako wskaźnik pomocniczy


def evaluate_levels(cases: list[RoundCase], weights: dict[str, float], n: int = config.N_SIMULATIONS_TUNING,
                    separate: bool = True) -> list[RaceLevels]:
    out = []
    for case in cases:
        post = _predict_case(case, weights, n, separate=separate)
        pre = _predict_case(case, weights, n, grid_known=False, separate=separate)
        quali = None
        if case.actual_quali:
            _, quali_strength = _strengths(case, weights, separate)
            noise = weights.get("quali_noise", config.QUALIFYING_NOISE) if separate else config.QUALIFYING_NOISE
            quali = ranking_rps(predict_qualifying(quali_strength, n=n, noise=noise).probabilities, case.actual_quali)
        out.append(RaceLevels(
            round=case.round, rps_pre=ranking_rps(pre, case.actual_finish), rps_post=ranking_rps(post, case.actual_finish),
            rps_quali=quali, brier_win_post=evaluate(case.round, post, case.actual_finish).brier_win,
        ))
    return out


def score_rounds(cases: list[RoundCase], weights: dict[str, float], n: int = config.N_SIMULATIONS_TUNING,
                 ) -> list[RaceEvaluation]:
    return [evaluate(case.round, _predict_case(case, weights, n), case.actual_finish) for case in cases]


def predict_rounds(cases: list[RoundCase], weights: dict[str, float], n: int = config.N_SIMULATIONS_TUNING,
                   ) -> list[tuple[list[DriverProbability], dict[str, int | None]]]:
    """Przewidywania (bez oceny) razem z faktycznym wynikiem: wejście dla kalibracji."""
    return [(_predict_case(case, weights, n), case.actual_finish) for case in cases]


def backtest(season: int, clients: "Clients", weights: dict[str, float], n: int = config.N_SIMULATIONS_TUNING,
             ) -> list[RaceEvaluation]:
    return score_rounds(prepare_rounds(season, clients), weights, n)


def evaluate_season(season: int, clients: "Clients", weights: dict[str, float], n: int = config.N_SIMULATIONS_TUNING,
                    ) -> list[RaceEvaluation]:
    """Ocena do pliku model.json: awaria źródła danych nie może zablokować reszty pipeline'u."""
    try:
        return backtest(season, clients, weights, n)
    except (JolpicaError, LookupError):
        return []


def main(argv: list[str] | None = None) -> int:
    from run import default_clients  # import tutaj, bo run.py importuje ten moduł

    parser = argparse.ArgumentParser(description="Test wsteczny modelu na zakończonych rundach sezonu")
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--n", type=int, default=config.N_SIMULATIONS)
    args = parser.parse_args(argv)
    evaluations = backtest(args.season, default_clients(args.season), config.default_weights(), n=args.n)
    if not evaluations:
        print("Brak rozegranych rund do oceny.")
        return 1
    print("runda  P(zwycięzcy)  top3  błąd pozycji   Brier")
    for e in evaluations:
        print(f"{e.round:>5}  {e.winner_prob:>11.1%}  {'tak' if e.winner_in_top3 else 'nie':>4}  "
              f"{e.mean_abs_position_error:>12.2f}  {e.brier_win:>6.4f}")
    cars = 22
    baseline = (1 - 1 / cars) / cars   # Brier modelu "każdy ma równą szansę"
    print(f"\nśrednio: P(zwycięzcy) {mean(e.winner_prob for e in evaluations):.1%} (losowo {1 / cars:.1%}), "
          f"top3 {sum(e.winner_in_top3 for e in evaluations)}/{len(evaluations)}, "
          f"błąd pozycji {mean(e.mean_abs_position_error for e in evaluations):.2f}, "
          f"Brier {mean(e.brier_win for e in evaluations):.4f} (losowo {baseline:.4f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
