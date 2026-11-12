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
from evaluation import RoundCase, prepare_seasons, score_rounds
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


@dataclass(frozen=True)
class GateResult:
    with_scores: dict[int, float]
    without_scores: dict[int, float]
    keep: bool


def factor_gate(
    cases_by_season: dict[int, list[RoundCase]], factor: str, test_seasons: list[int], base: dict[str, float],
    bounds: dict[str, tuple[float, float]], locked: set[str], n: int = config.N_SIMULATIONS_TUNING,
) -> GateResult:
    """Porównuje wynik poza próbką z czynnikiem i bez niego (jego waga 0 i zablokowana)."""
    with_scores = walk_forward(cases_by_season, test_seasons, base, bounds, locked, n)
    without_scores = walk_forward(cases_by_season, test_seasons, {**base, factor: 0.0}, bounds, set(locked) | {factor}, n)
    return GateResult(with_scores, without_scores, keep_rule(with_scores, without_scores))


def write_oos(path: Path, scores: dict[int, float]) -> None:
    rows = [SeasonScore(season=s, brier=b).model_dump() for s, b in sorted(scores.items())]
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
    if args.factor:
        result = factor_gate(by_season, args.factor, test_seasons, base, bounds, locked, args.n)
        print(f"\nCzynnik {args.factor}: Brier poza próbką (mniej = lepiej)\nsezon      z       bez")
        for s in test_seasons:
            print(f"{s}   {result.with_scores[s]:.5f}  {result.without_scores[s]:.5f}")
        print(f"średnio {mean(result.with_scores.values()):.5f}  {mean(result.without_scores.values()):.5f}")
        print("DECYZJA:", "ZOSTAJE" if result.keep else "WYPADA (waga 0 i LOCKED_WEIGHTS)")
        return 0
    scores = walk_forward(by_season, test_seasons, base, bounds, locked, args.n)
    for s, b in scores.items():
        print(f"{s}: Brier {b:.5f}")
    write_oos(args.out / "oos.json", scores)
    print("Zapisano", args.out / "oos.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
