"""Różnica czasów w kwalifikacjach: średnia strata kierowcy do pole (w %), nowsze wyścigi ważą więcej."""
from __future__ import annotations

from collections import defaultdict

import config
from factors.base import RaceContext, zscore


class QualiGap:
    name = "quali_gap"

    def score(self, ctx: RaceContext) -> dict[str, float] | None:
        usable = [a for a in ctx.aggregates if a.quali_gap]
        if len(usable) < config.AGGREGATE_MIN_RACES:
            return None
        weighted: dict[str, float] = defaultdict(float)
        total: dict[str, float] = defaultdict(float)
        for age, agg in enumerate(reversed(usable)):          # age 0 = najnowszy wyścig
            w = 0.5 ** (age / config.FORM_HALF_LIFE_ROUNDS)
            for driver, gap in agg.quali_gap.items():
                weighted[driver] += w * min(gap, config.QUALI_GAP_CLIP)   # jedno nieudane okrążenie nie rządzi średnią
                total[driver] += w
        z = zscore({d: -(weighted[d] / total[d]) for d in total})          # mniejsza strata = lepiej
        return {e.driver_id: z[e.driver_id] for e in ctx.entries if e.driver_id in z}
