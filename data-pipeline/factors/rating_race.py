"""Ocena siły do wyścigu: dynamiczne oceny auta i kierowcy z całej kolejności mety (ratings.py), z rozgrzewką na wielu sezonach."""
from __future__ import annotations

import config
from factors.base import RaceContext, zscore
from ratings import build_ratings

MIN_RACES = 3


class RatingRace:
    """Parametry domyślnie z `config` (czytane przy każdym wywołaniu); można je podać wprost, np. do skanowania."""
    name = "rating_race"

    def __init__(self, eta_car: float | None = None, eta_driver: float | None = None, car_keep: float | None = None,
                 driver_keep: float | None = None):
        self._params = (eta_car, eta_driver, car_keep, driver_keep)

    def score(self, ctx: RaceContext) -> dict[str, float] | None:
        history = ctx.long_history or ctx.history
        if len(history) < MIN_RACES:
            return None
        defaults = (config.RATING_ETA_CAR, config.RATING_ETA_DRIVER, config.RATING_CAR_KEEP, config.RATING_DRIVER_KEEP)
        eta_car, eta_driver, car_keep, driver_keep = (p if p is not None else d for p, d in zip(self._params, defaults))
        ratings = build_ratings(history, eta_car, eta_driver, car_keep, driver_keep)
        z = zscore({e.driver_id: ratings.strength(e.driver_id, e.team_id) for e in ctx.entries})
        return {e.driver_id: z[e.driver_id] for e in ctx.entries}
