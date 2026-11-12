"""Przewaga niedzielna: czy kierowca w wyścigu jest szybszy, niż wynika z jego kwalifikacji.

Dla wyścigu: (strata w kwalifikacjach względem mediany stawki) minus (tempo wyścigowe względem mediany stawki);
dodatnia wartość = w niedzielę szybszy niż w sobotę. Średnia z recency, przemnożona przez n/(n+K), żeby kierowca
z kilkoma wyścigami nie wyprzedzał kogoś, kto miał ich dużo.
"""
from __future__ import annotations

from collections import defaultdict
from statistics import median

import config
from factors.base import RaceContext, zscore


class RaceVsQuali:
    name = "race_vs_quali"

    def score(self, ctx: RaceContext) -> dict[str, float] | None:
        usable = [a for a in ctx.aggregates if a.quali_gap and a.race_pace]
        if len(usable) < config.AGGREGATE_MIN_RACES:
            return None
        weighted: dict[str, float] = defaultdict(float)
        total: dict[str, float] = defaultdict(float)
        count: dict[str, int] = defaultdict(int)
        clip = config.RACE_PACE_CLIP
        for age, agg in enumerate(reversed(usable)):          # age 0 = najnowszy wyścig
            w = 0.5 ** (age / config.FORM_HALF_LIFE_ROUNDS)
            gaps = {d: min(g, config.QUALI_GAP_CLIP) for d, g in agg.quali_gap.items()}
            field_median = median(gaps.values())
            for driver, gap in gaps.items():
                if driver not in agg.race_pace:
                    continue
                pace = max(-clip, min(clip, agg.race_pace[driver]))   # uszkodzone auto nie rządzi średnią
                weighted[driver] += w * ((gap - field_median) - pace)
                total[driver] += w
                count[driver] += 1
        shrunk = {d: (weighted[d] / total[d]) * count[d] / (count[d] + config.RACEQ_SHRINK_K) for d in total}
        z = zscore(shrunk)
        return {e.driver_id: z[e.driver_id] for e in ctx.entries if e.driver_id in z}
