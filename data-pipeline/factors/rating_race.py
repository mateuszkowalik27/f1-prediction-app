"""Ocena siły do wyścigu: dynamiczne oceny auta i kierowcy z całej kolejności mety (ratings.py), z rozgrzewką na wielu sezonach."""
from __future__ import annotations

import config
from factors.base import RaceContext, zscore
from ratings import build_ratings

MIN_RACES = 3


class RatingRace:
    name = "rating_race"

    def score(self, ctx: RaceContext) -> dict[str, float] | None:
        history = ctx.long_history or ctx.history
        if len(history) < MIN_RACES:
            return None
        ratings = build_ratings(history, config.RATING_ETA_CAR, config.RATING_ETA_DRIVER, config.RATING_CAR_KEEP,
                                config.RATING_DRIVER_KEEP)
        z = zscore({e.driver_id: ratings.strength(e.driver_id, e.team_id) for e in ctx.entries})
        return {e.driver_id: z[e.driver_id] for e in ctx.entries}
