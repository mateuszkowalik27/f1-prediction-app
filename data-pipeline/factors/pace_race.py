"""Czyste tempo wyścigowe: średnie (ważone nowością) tempo okrążeń kierowcy względem stawki, bez wpływu pecha (kolizje, safety car)."""
from __future__ import annotations

from collections import defaultdict

import config
from factors.base import RaceContext, zscore


class PaceRace:
    name = "pace_race"

    def score(self, ctx: RaceContext) -> dict[str, float] | None:
        usable = [a for a in ctx.aggregates if a.race_pace]
        if len(usable) < config.AGGREGATE_MIN_RACES:
            return None
        clip = config.RACE_PACE_CLIP
        weighted: dict[str, float] = defaultdict(float)
        total: dict[str, float] = defaultdict(float)
        count: dict[str, int] = defaultdict(int)
        for age, agg in enumerate(reversed(usable)):          # age 0 = najnowszy wyścig
            w = 0.5 ** (age / config.FORM_HALF_LIFE_ROUNDS)
            for driver, pace in agg.race_pace.items():
                weighted[driver] += w * max(-clip, min(clip, pace))    # uszkodzone auto nie rządzi średnią
                total[driver] += w
                count[driver] += 1
        current = {e.driver_id for e in ctx.entries}
        raw = {d: -(weighted[d] / total[d]) for d in total if d in current}       # szybciej (ujemne %) = lepiej
        if not raw:
            return None
        z = zscore(raw)
        k = config.AGG_SHRINK_K
        return {d: z[d] * count[d] / (count[d] + k) for d in z}                   # mało wyścigów: ściągnięte ku zeru
