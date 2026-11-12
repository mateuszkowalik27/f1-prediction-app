"""Historia kierowcy na danym torze: ważona (nowsze lata) średnia pozycja na mecie."""
from __future__ import annotations

from collections import defaultdict

import config
from factors.base import RaceContext, zscore


class TrackHistory:
    name = "track_history"

    def score(self, ctx: RaceContext) -> dict[str, float] | None:
        weighted: dict[str, float] = defaultdict(float)
        total: dict[str, float] = defaultdict(float)
        for race in ctx.circuit_history:
            w = 0.5 ** ((ctx.season - race.season) / config.RECENCY_HALF_LIFE_YEARS)
            for r in race.results:
                position = r.finish if r.finish is not None else len(race.results)  # DNF = ostatnie miejsce
                weighted[r.driver_id] += w * position
                total[r.driver_id] += w
        if not total:
            return None
        z = zscore({d: -(weighted[d] / total[d]) for d in total})  # niższa pozycja = lepiej
        return {e.driver_id: z[e.driver_id] for e in ctx.entries if e.driver_id in z}
