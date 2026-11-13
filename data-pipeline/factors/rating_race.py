"""Ocena siły do wyścigu: dynamiczne oceny auta i kierowcy z całej kolejności mety (ratings.py), z rozgrzewką na wielu sezonach.

Etap 6: opcjonalnie trend (zespół przyspiesza lub zwalnia), dziedziczenie oceny po poprzedniej nazwie zespołu i punkt startowy z dostawcy silnika.
"""
from __future__ import annotations

import config
from engines import supplier_of
from factors.base import RaceContext, zscore
from ratings import build_ratings

MIN_RACES = 3


class RatingRace:
    """Parametry domyślnie z `config` (czytane przy każdym wywołaniu); można je podać wprost, np. do skanowania i bramek."""
    name = "rating_race"

    def __init__(self, eta_car: float | None = None, eta_driver: float | None = None, car_keep: float | None = None,
                 driver_keep: float | None = None, trend_gain: float | None = None, trend_alpha: float | None = None,
                 supplier_weight: float | None = None, use_lineage: bool | None = None):
        self._params = {"eta_car": eta_car, "eta_driver": eta_driver, "car_keep": car_keep, "driver_keep": driver_keep,
                        "trend_gain": trend_gain, "trend_alpha": trend_alpha, "supplier_weight": supplier_weight,
                        "use_lineage": use_lineage}

    def _resolved(self) -> dict:
        defaults = {"eta_car": config.RATING_ETA_CAR, "eta_driver": config.RATING_ETA_DRIVER,
                    "car_keep": config.RATING_CAR_KEEP, "driver_keep": config.RATING_DRIVER_KEEP,
                    "trend_gain": config.RATING_TREND_GAIN, "trend_alpha": config.RATING_TREND_ALPHA,
                    "supplier_weight": config.RATING_SUPPLIER_WEIGHT, "use_lineage": config.RATING_USE_LINEAGE}
        return {k: (v if v is not None else defaults[k]) for k, v in self._params.items()}

    def score(self, ctx: RaceContext) -> dict[str, float] | None:
        history = ctx.long_history or ctx.history
        if len(history) < MIN_RACES:
            return None
        p = self._resolved()
        ratings = build_ratings(
            history, p["eta_car"], p["eta_driver"], p["car_keep"], p["driver_keep"], trend_alpha=p["trend_alpha"],
            lineage=config.TEAM_LINEAGE if p["use_lineage"] else None,
            supplier_of=supplier_of if p["supplier_weight"] > 0 else None, supplier_weight=p["supplier_weight"])
        z = zscore({e.driver_id: ratings.strength(e.driver_id, e.team_id, trend_gain=p["trend_gain"]) for e in ctx.entries})
        return {e.driver_id: z[e.driver_id] for e in ctx.entries}
