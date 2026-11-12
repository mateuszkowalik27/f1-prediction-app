"""Szybkość pit stopów zespołu: średnia różnica czasu postoju względem stawki, nowsze wyścigi ważą więcej."""
from __future__ import annotations

from collections import defaultdict

import config
from factors.base import RaceContext, zscore


class PitStopSpeed:
    name = "pit_stop"

    def score(self, ctx: RaceContext) -> dict[str, float] | None:
        usable = [a for a in ctx.aggregates if a.pit_delta]
        if len(usable) < config.AGGREGATE_MIN_RACES:
            return None
        weighted: dict[str, float] = defaultdict(float)
        total: dict[str, float] = defaultdict(float)
        clip = config.PIT_DELTA_CLIP
        for age, agg in enumerate(reversed(usable)):          # age 0 = najnowszy wyścig
            w = 0.5 ** (age / config.FORM_HALF_LIFE_ROUNDS)
            for team, delta in agg.pit_delta.items():
                weighted[team] += w * max(-clip, min(clip, delta))   # kłopotliwy postój nie rządzi średnią
                total[team] += w
        current = {e.team_id for e in ctx.entries}               # średnią stawki liczymy po obecnych zespołach
        raw = {t: -(weighted[t] / total[t]) for t in total if t in current}   # krótszy postój = lepiej
        if not raw:
            return None
        count = defaultdict(int)
        for agg in usable:
            for team in agg.pit_delta:
                count[team] += 1
        z = zscore(raw)
        k = config.AGG_SHRINK_K
        return {e.driver_id: z[e.team_id] * count[e.team_id] / (count[e.team_id] + k)    # debiutant: mało wyścigów, mało pewności
                for e in ctx.entries if e.team_id in z}
