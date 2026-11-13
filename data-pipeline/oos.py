"""Ocena poza próbką: strojenie wag tylko na sezonach wcześniejszych niż oceniany, oraz bramka dla nowej zmiennej.

Użycie:
  python data-pipeline/oos.py                       # wynik bazowy; zapis public/data/oos.json
  python data-pipeline/oos.py --factor quali_gap    # czy czynnik poprawia wynik poza próbką? (bramka)
Strojenie bywa wolne (kilka minut): to narzędzie uruchamiane ręcznie, nie w robocie.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

import config
from dataclasses import replace
from typing import Literal

from evaluation import (
    RaceLevels, RoundCase, _predict_case, evaluate_levels, evaluate_quali, prepare_seasons, score_rounds,
)
from factors.rating_race import RatingRace
from scoring import Diff, paired_bootstrap, verdict
from history_store import HistoryStore
from schemas import SeasonScore
from tuning import tune_weights


def weights_for_season(
    cases_by_season: dict[int, list[RoundCase]], season: int, base: dict[str, float],
    bounds: dict[str, tuple[float, float]], locked: set[str], n: int = config.N_SIMULATIONS_TUNING,
) -> dict[str, float]:
    """Wagi dla sezonu `season`, dostrojone WYŁĄCZNIE na sezonach wcześniejszych."""
    factor_names = {name for cases in cases_by_season.values() for c in cases for name in c.factor_scores}
    train = [c for s in sorted(cases_by_season) if s < season for c in cases_by_season[s]]
    # czynnik bez żadnych danych w treningu nie ma na co wpływać: nie stroimy go
    untestable = {name for name in factor_names if all(c.factor_scores.get(name) is None for c in train)}
    return tune_weights(
        base, bounds, set(locked) | untestable, len(train),
        lambda w: mean(e.brier_win for e in score_rounds(train, w, n)),
    )


def walk_forward(
    cases_by_season: dict[int, list[RoundCase]], test_seasons: list[int], base: dict[str, float],
    bounds: dict[str, tuple[float, float]], locked: set[str], n: int = config.N_SIMULATIONS_TUNING,
) -> dict[int, float]:
    """Dla sezonu S: wagi strojone na sezonach < S, wynik = średni Brier sezonu S."""
    scores: dict[int, float] = {}
    for season in test_seasons:
        test = cases_by_season.get(season)
        if not test:
            continue
        tuned = weights_for_season(cases_by_season, season, base, bounds, locked, n)
        scores[season] = mean(e.brier_win for e in score_rounds(test, tuned, n))
    return scores


def keep_rule(with_scores: dict[int, float], without_scores: dict[int, float]) -> bool:
    """Czynnik zostaje, gdy średnio poprawia Brier i pogarsza go w najwyżej jednym sezonie testowym."""
    seasons = sorted(set(with_scores) & set(without_scores))
    if not seasons:
        return False
    better_on_average = mean(with_scores[s] for s in seasons) < mean(without_scores[s] for s in seasons)
    worse_seasons = sum(with_scores[s] > without_scores[s] for s in seasons)
    return better_on_average and worse_seasons <= 1


def walk_forward_levels(
    cases_by_season: dict[int, list[RoundCase]], test_seasons: list[int], base: dict[str, float],
    bounds: dict[str, tuple[float, float]], locked: set[str], n: int = config.N_SIMULATIONS_TUNING,
) -> dict[int, list[RaceLevels]]:
    """Jak `walk_forward`, ale wynik to ocena każdego wyścigu na trzech poziomach (RPS), a nie sam Brier."""
    out: dict[int, list[RaceLevels]] = {}
    for season in test_seasons:
        test = cases_by_season.get(season)
        if not test:
            continue
        tuned = weights_for_season(cases_by_season, season, base, bounds, locked, n)
        out[season] = evaluate_levels(test, tuned, n)
    return out


def _flat(levels: dict[int, list[RaceLevels]]) -> list[RaceLevels]:
    return [x for s in sorted(levels) for x in levels[s]]


def _diffs(a: list[RaceLevels], b: list[RaceLevels]) -> dict[str, Diff]:
    """Różnica `a - b` (ujemna = a lepsze) na każdym poziomie, tylko dla wyścigów, w których oba mają wynik."""
    out = {}
    for name, attr in (("pre", "rps_pre"), ("post", "rps_post"), ("quali", "rps_quali")):
        pairs = [(getattr(x, attr), getattr(y, attr)) for x, y in zip(a, b)
                 if getattr(x, attr) is not None and getattr(y, attr) is not None]
        if pairs:
            out[name] = paired_bootstrap([p for p, _ in pairs], [q for _, q in pairs])
    return out


def gate_verdict(with_levels: list[RaceLevels], without_levels: list[RaceLevels],
                 ) -> tuple[Literal["keep", "drop", "inconclusive"], dict[str, Diff]]:
    """Bramka z przedziałami: `keep`, gdy przed lub po kwalifikacjach jest wyraźna poprawa i nigdzie wyraźnego pogorszenia;
    `drop` przy wyraźnym pogorszeniu na którymś z tych dwóch poziomów; inaczej `inconclusive` (zostaje stan dotychczasowy)."""
    diffs = _diffs(with_levels, without_levels)
    verdicts = [verdict(diffs[k]) for k in ("pre", "post") if k in diffs]
    if "worse" in verdicts:
        return "drop", diffs
    if "better" in verdicts:
        return "keep", diffs
    return "inconclusive", diffs


def quali_noise_scan(cases: list[RoundCase], weights: dict[str, float], noises: list[float],
                     n: int = config.N_SIMULATIONS_TUNING) -> dict[float, float]:
    """Średni RPS kwalifikacji dla kolejnych wartości szumu (do wyboru `QUALIFYING_NOISE` na sezonach treningowych)."""
    scan = {}
    for noise in noises:
        values = [v for v in (evaluate_quali(c, {**weights, "quali_noise": noise}, n) for c in cases) if v is not None]
        if values:
            scan[noise] = float(mean(values))
    return scan


# Warianty wag do bramki (`oos.py --variant NAZWA`): nadpisania względem wag bazowych (suma wag wyścigu zachowana).
VARIANTS: dict[str, dict[str, float]] = {
    "rating_race": {"car_pace": 0.0, "driver_form": 0.0, "rating_race": 0.45},          # oceny zamiast punktów
    "rating_race_plus": {"car_pace": 0.15, "driver_form": 0.075, "rating_race": 0.225},  # oceny obok połowy starych czynników
    "pace_race": {"pace_race": 0.10, "car_pace": 0.25, "driver_form": 0.10},             # czyste tempo kosztem części punktów
    "rating_quali": {"q_quali_gap": 0.0, "q_rating_quali": 0.40},                        # kwalifikacje: rozkład auto + kierowca
    "rating_quali_plus": {"q_quali_gap": 0.20, "q_rating_quali": 0.20},                  # połowa starego quali_gap, połowa nowego
    "noise_model": {"chaos_base": 0.2, "chaos_mult": 3.0},                                # chaos tylko w wyścigu
    "noise_model_lite": {"chaos_base": 0.1, "chaos_mult": 3.0},
    "v3_core": {"car_pace": 0.12, "driver_form": 0.06, "rating_race": 0.17, "pace_race": 0.10},   # oceny + tempo + połowa starych
}


def variant_gate(cases_by_season: dict[int, list[RoundCase]], test_seasons: list[int], base: dict[str, float],
                 overrides: dict[str, float], n: int = config.N_SIMULATIONS_TUNING,
                 ) -> tuple[Literal["keep", "drop", "inconclusive"], dict[str, Diff]]:
    """Bramka wariantu: wagi `base` z nadpisaniami vs same `base`, stałe wagi (bez strojenia), trzy poziomy oceny."""
    cases = [c for s in test_seasons for c in cases_by_season.get(s, [])]
    return gate_verdict(evaluate_levels(cases, {**base, **overrides}, n), evaluate_levels(cases, base, n))


def rating_scan(cases: list[RoundCase], weights: dict[str, float], grid: list[dict[str, float]],
                n: int = config.N_SIMULATIONS_TUNING) -> dict[tuple, dict[str, float]]:
    """Średni RPS (przed / po kwalifikacjach) dla kombinacji hiperparametrów ocen; czynnik `rating_race` liczony od nowa."""
    out = {}
    for params in grid:
        factor = RatingRace(params.get("eta_car"), params.get("eta_driver"), params.get("car_keep"), params.get("driver_keep"))
        recomputed = [replace(c, factor_scores={**c.factor_scores, "rating_race": factor.score(c.ctx)}) for c in cases]
        levels = evaluate_levels(recomputed, weights, n)
        out[tuple(sorted(params.items()))] = {"pre": float(mean(x.rps_pre for x in levels)),
                                              "post": float(mean(x.rps_post for x in levels))}
    return out


def tail_report(cases: list[RoundCase], weights: dict[str, float], n: int = config.N_SIMULATIONS_TUNING) -> dict[str, dict]:
    """Czy ogony są uczciwe? Dla prognoz przed i po kwalifikacjach: ile wyścigów wygrał kierowca z szansą < 2%
    (faktycznie vs ile wynika z prognoz) oraz czy faworyci (> 35%) wygrywają tak często, jak im się przypisuje."""
    out = {}
    for level, known in (("pre", False), ("post", True)):
        expected = actual = fav_n = fav_hits = 0
        fav_pred = 0.0
        for case in cases:
            winner = next(d for d, f in case.actual_finish.items() if f == 1)
            for p in _predict_case(case, weights, n, grid_known=known):
                if p.win < 0.02:
                    expected += p.win
                    actual += p.driver_id == winner
                elif p.win > 0.35:
                    fav_n += 1
                    fav_pred += p.win
                    fav_hits += p.driver_id == winner
        out[level] = {"races": len(cases), "longshot_expected": float(expected), "longshot_actual": int(actual),
                      "fav_n": fav_n, "fav_pred": fav_pred / fav_n if fav_n else 0.0,
                      "fav_actual": fav_hits / fav_n if fav_n else 0.0}
    return out


def noise_scan(cases: list[RoundCase], weights: dict[str, float], grid: list[dict[str, float]],
               n: int = config.N_SIMULATIONS_TUNING) -> dict[tuple, dict]:
    """Dla kombinacji parametrów losowości: średni RPS (trzy poziomy), log-strata zwycięzcy i diagnostyka ogonów."""
    out = {}
    for params in grid:
        w = {**weights, **params}
        levels = evaluate_levels(cases, w, n)
        quali = [x.rps_quali for x in levels if x.rps_quali is not None]
        out[tuple(sorted(params.items()))] = {
            "rps_pre": float(mean(x.rps_pre for x in levels)), "rps_post": float(mean(x.rps_post for x in levels)),
            "rps_quali": float(mean(quali)) if quali else None,
            "logloss_pre": float(mean(x.logloss_win_pre for x in levels)),
            "logloss_post": float(mean(x.logloss_win_post for x in levels)),
            "tails": tail_report(cases, w, n),
        }
    return out


def level_report(
    cases_by_season: dict[int, list[RoundCase]], test_seasons: list[int], base: dict[str, float],
    bounds: dict[str, tuple[float, float]], locked: set[str], n: int = config.N_SIMULATIONS_TUNING,
) -> dict:
    """Trzy zestawy wag obok siebie na wyścigach testowych: bazowe, dostrojone (walk-forward) i sama siatka (siła = 0)."""
    tests = [(s, c) for s in test_seasons for c in cases_by_season.get(s, [])]
    cases = [c for _, c in tests]
    tuned_by_season = walk_forward_levels(cases_by_season, test_seasons, base, bounds, locked, n)
    levels = {
        "base": evaluate_levels(cases, base, n),
        "tuned": _flat(tuned_by_season),
        "grid_only": evaluate_levels([replace(c, factor_scores={}) for c in cases], base, n),
        "shared": evaluate_levels(cases, base, n, separate=False),     # dawny tryb: jedna siła do kwalifikacji i wyścigu
    }
    diffs = {"tuned_vs_base": _diffs(levels["tuned"], levels["base"]),
             "base_vs_grid_only": _diffs(levels["base"], levels["grid_only"]),
             "separate_vs_shared": _diffs(levels["base"], levels["shared"])}
    return {"levels": levels, "diffs": diffs, "tuned_by_season": tuned_by_season}


@dataclass(frozen=True)
class GateResult:
    with_scores: dict[int, float]
    without_scores: dict[int, float]
    keep: bool
    verdict: str = "inconclusive"
    diffs: dict | None = None


def factor_gate(
    cases_by_season: dict[int, list[RoundCase]], factor: str, test_seasons: list[int], base: dict[str, float],
    bounds: dict[str, tuple[float, float]], locked: set[str], n: int = config.N_SIMULATIONS_TUNING,
) -> GateResult:
    """Porównuje wynik poza próbką z czynnikiem i bez niego (jego waga 0 i zablokowana)."""
    with_scores = walk_forward(cases_by_season, test_seasons, base, bounds, locked, n)
    without_scores = walk_forward(cases_by_season, test_seasons, {**base, factor: 0.0}, bounds, set(locked) | {factor}, n)
    with_levels = walk_forward_levels(cases_by_season, test_seasons, base, bounds, locked, n)
    without_levels = walk_forward_levels(cases_by_season, test_seasons, {**base, factor: 0.0}, bounds, set(locked) | {factor}, n)
    result, diffs = gate_verdict(_flat(with_levels), _flat(without_levels))
    return GateResult(with_scores, without_scores, result == "keep", result, diffs)


def write_oos(path: Path, scores: dict[int, float], levels: dict[int, list[RaceLevels]] | None = None) -> None:
    def avg(season: int, attr: str) -> float | None:
        values = [getattr(x, attr) for x in (levels or {}).get(season, []) if getattr(x, attr) is not None]
        return float(mean(values)) if values else None

    rows = [SeasonScore(season=s, brier=b, rps_pre=avg(s, "rps_pre"), rps_post=avg(s, "rps_post"),
                        rps_quali=avg(s, "rps_quali")).model_dump() for s, b in sorted(scores.items())]
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")


def clients_with_wet_cache(clients, out: Path):
    """Klienci z cache'em mokrych wyścigów (jak w robocie), żeby nie odpytywać API pogody o setki wyścigów.
    Zwraca (klienci, funkcja zapisująca cache)."""
    from dataclasses import replace
    from run import _cached_wet, _load_model
    from schemas import WetCache

    stored = _load_model(out / "wet_cache.json", WetCache)
    flags = dict(stored.flags) if stored else {}

    def save() -> None:
        (out / "wet_cache.json").write_text(WetCache(flags=flags).model_dump_json(), encoding="utf-8")

    return replace(clients, wet=_cached_wet(clients.wet, flags)), save


def main(argv: list[str] | None = None) -> int:
    from run import default_clients, resolve_season  # import tutaj: run.py importuje moduły o podobnych zależnościach

    parser = argparse.ArgumentParser(description="Ocena poza próbką i bramka czynnika")
    parser.add_argument("--out", type=Path, default=Path("public/data"))
    parser.add_argument("--factor", default=None)
    parser.add_argument("--variant", default=None, choices=sorted(VARIANTS), help="bramka wariantu wag (VARIANTS)")
    parser.add_argument("--scan-noise", action="store_true",
                        help="dobór losowości (wspólny los zespołu, chaos): sezony 2022-2023 (wybór) i testowe (kontrola)")
    parser.add_argument("--scan-ratings", action="store_true",
                        help="dobór hiperparametrów ocen: sezony 2022-2023 (wybór) i testowe (kontrola)")
    parser.add_argument("--scan-quali-noise", action="store_true",
                        help="RPS kwalifikacji dla kilku wartości szumu: na sezonach 2022-2023 (wybór) i testowych (kontrola)")
    parser.add_argument("--n", type=int, default=config.N_SIMULATIONS_TUNING)
    args = parser.parse_args(argv)
    now = datetime.now(timezone.utc)
    season = resolve_season(now, default_clients(now.year).jolpica)
    clients, save_wet = clients_with_wet_cache(default_clients(season), args.out)
    by_season = prepare_seasons(list(range(config.FIRST_BACKFILL_SEASON, season + 1)), clients,
                                HistoryStore(args.out / "history").all())
    save_wet()
    test_seasons = [s for s in config.TEST_SEASONS if s in by_season]
    base, bounds, locked = config.default_weights(), config.WEIGHT_BOUNDS, set(config.LOCKED_WEIGHTS)
    print(f"Sezony z wyścigami: {sorted(by_season)}; testowe: {test_seasons}")
    if args.variant:
        result, diffs = variant_gate(by_season, test_seasons, base, VARIANTS[args.variant], args.n)
        print(f"\nWariant {args.variant}: RPS wariant - baza (ujemna = wariant lepszy), przedział 90%:")
        for name, d in diffs.items():
            print(f"  {name:6s} {d.mean:+.5f}  [{d.lo:+.5f}, {d.hi:+.5f}]  n={d.n}  -> {verdict(d)}")
        print("DECYZJA:", {"keep": "WCHODZI", "drop": "WYPADA", "inconclusive": "NIEJEDNOZNACZNE (zostaje stan dotychczasowy)"}[result])
        return 0
    if args.scan_noise:
        grid = [{"team_noise_share": ts, "chaos_base": cb, "chaos_mult": cm}
                for ts in (0.0, 0.2, 0.4) for cb in (0.0, 0.1, 0.2) for cm in (1.5, 2.0, 3.0) if not (cb == 0.0 and cm != 2.0)]
        for label, seasons in (("trening 2022-2023", [2022, 2023]), ("test 2024-2026", test_seasons)):
            cases = [c for s_ in seasons for c in by_season.get(s_, [])]
            print(f"\nLosowość ({label}, {len(cases)} wyścigów): suma RPS (przed+po+kwal.) | log-strata zw. przed/po | ogony przed: skreśleni wygrali / oczekiwano, faworyci prognoza / faktycznie")
            scan = noise_scan(cases, base, grid, args.n)
            rows = sorted(scan.items(), key=lambda kv: kv[1]["rps_pre"] + kv[1]["rps_post"] + (kv[1]["rps_quali"] or 0))
            for params, v in rows[:10]:
                t = v["tails"]["pre"]
                total = v["rps_pre"] + v["rps_post"] + (v["rps_quali"] or 0)
                print(f"  {dict(params)}  {total:.4f} | {v['logloss_pre']:.3f}/{v['logloss_post']:.3f} | "
                      f"{t['longshot_actual']} / {t['longshot_expected']:.1f}, {t['fav_pred']:.2f} / {t['fav_actual']:.2f}")
        return 0
    if args.scan_ratings:
        grid = [{"eta_car": ec, "eta_driver": ed, "car_keep": ck}
                for ec in (0.05, 0.1, 0.2, 0.35) for ed in (0.03, 0.08, 0.15) for ck in (0.4, 0.6, 0.8)]
        weights = {**base, **VARIANTS["rating_race"]}
        for label, seasons in (("trening 2022-2023", [2022, 2023]), ("test 2024-2026", test_seasons)):
            cases = [c for s_ in seasons for c in by_season.get(s_, [])]
            print(f"\nRPS ocen ({label}, {len(cases)} wyścigów): przed kwal. / po kwal. (mniej = lepiej)")
            scan = rating_scan(cases, weights, grid, args.n)
            for params, v in sorted(scan.items(), key=lambda kv: kv[1]["pre"] + kv[1]["post"])[:8]:
                print(f"  {dict(params)}  {v['pre']:.5f} / {v['post']:.5f}")
        return 0
    if args.scan_quali_noise:
        noises = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.2]
        for label, seasons in (("trening 2022-2023", [2022, 2023]), ("test 2024-2026", test_seasons)):
            cases = [c for s_ in seasons for c in by_season.get(s_, [])]
            print(f"\nRPS kwalifikacji ({label}, {len(cases)} wyścigów):")
            for noise, value in quali_noise_scan(cases, base, noises, args.n).items():
                print(f"  szum {noise:.1f}: {value:.5f}")
        return 0
    if args.factor:
        result = factor_gate(by_season, args.factor, test_seasons, base, bounds, locked, args.n)
        print(f"\nCzynnik {args.factor}: Brier zwycięzcy poza próbką (mniej = lepiej)\nsezon      z       bez")
        for s in test_seasons:
            print(f"{s}   {result.with_scores[s]:.5f}  {result.without_scores[s]:.5f}")
        print(f"średnio {mean(result.with_scores.values()):.5f}  {mean(result.without_scores.values()):.5f}")
        print("\nRPS całej kolejności, różnica z - bez (ujemna = czynnik pomaga), przedział 90%:")
        for name, d in (result.diffs or {}).items():
            print(f"  {name:6s} {d.mean:+.5f}  [{d.lo:+.5f}, {d.hi:+.5f}]  n={d.n}  -> {verdict(d)}")
        print("DECYZJA:", {"keep": "ZOSTAJE", "drop": "WYPADA (waga 0 i LOCKED_WEIGHTS)",
                           "inconclusive": "NIEJEDNOZNACZNE (zostaje stan dotychczasowy)"}[result.verdict])
        return 0
    report = level_report(by_season, test_seasons, base, bounds, locked, args.n)
    print("\nŚredni RPS na wyścig (mniej = lepiej):\nzestaw wag   przed kwal.  po kwal.  kwalifikacje   (shared = dawny wspólny tryb)")
    for name, rows in report["levels"].items():
        def avg(attr):
            values = [getattr(x, attr) for x in rows if getattr(x, attr) is not None]
            return f"{mean(values):.4f}" if values else "  -   "
        print(f"{name:11s}  {avg('rps_pre'):>10s}  {avg('rps_post'):>8s}  {avg('rps_quali'):>11s}")
    for pair, diffs in report["diffs"].items():
        print(f"\n{pair} (ujemna = pierwsze lepsze), przedział 90%:")
        for level, d in diffs.items():
            print(f"  {level:6s} {d.mean:+.5f}  [{d.lo:+.5f}, {d.hi:+.5f}]  n={d.n}  -> {verdict(d)}")
    scores = walk_forward(by_season, test_seasons, base, bounds, locked, args.n)
    for s, b in scores.items():
        print(f"{s}: Brier zwycięzcy {b:.5f}")
    write_oos(args.out / "oos.json", scores, levels=report["tuned_by_season"])
    print("Zapisano", args.out / "oos.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
