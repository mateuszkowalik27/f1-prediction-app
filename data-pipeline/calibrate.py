"""Dopasowuje kalibrację szans na przewidywaniach poza próbką z testu wstecznego i zapisuje calibration.json.

Użycie:  python data-pipeline/calibrate.py [--out public/data]   (kosztowne: uruchamiane ręcznie, wynik commitujemy)
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import config
from calibration import Prediction, _brier, fit_tau
from evaluation import predict_rounds, prepare_seasons
from history_store import HistoryStore
from oos import weights_for_season
from schemas import Calibration


def main(argv: list[str] | None = None) -> int:
    from run import default_clients, resolve_season

    parser = argparse.ArgumentParser(description="Kalibracja szans na wygraną")
    parser.add_argument("--out", type=Path, default=Path("public/data"))
    parser.add_argument("--n", type=int, default=config.N_SIMULATIONS_TUNING)
    args = parser.parse_args(argv)
    now = datetime.now(timezone.utc)
    season = resolve_season(now, default_clients(now.year).jolpica)
    by_season = prepare_seasons(list(range(config.FIRST_BACKFILL_SEASON, season + 1)), default_clients(season),
                                HistoryStore(args.out / "history").all())
    base, bounds, locked = config.default_weights(), config.WEIGHT_BOUNDS, set(config.LOCKED_WEIGHTS)
    predictions: list[Prediction] = []
    for s in (x for x in config.TEST_SEASONS if x in by_season):
        weights = weights_for_season(by_season, s, base, bounds, locked, args.n)   # wagi bez znajomości sezonu s
        predictions += predict_rounds(by_season[s], weights, args.n)
    tau = fit_tau(predictions)
    print(f"Przewidywań poza próbką: {len(predictions)}; tau = {tau}")
    if predictions:
        print(f"Brier szans na wygraną: bez kalibracji {_brier(predictions, 1.0):.5f}, z kalibracją {_brier(predictions, tau):.5f}")
    (args.out / "calibration.json").write_text(
        Calibration(tau=tau, n_races=len(predictions), fitted_at=now).model_dump_json(), encoding="utf-8")
    print("Zapisano", args.out / "calibration.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
