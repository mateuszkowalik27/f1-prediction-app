"""Zużycie opon dopasowane do toru: zespół o małym zużyciu zyskuje na torach, które opony zjadają.

score(zespół) = -z(zużycie zespołu) x poziom_toru_z. Na torze o dużym zużyciu (poziom > 0) oszczędny zespół dostaje
plus, na łagodnym (poziom < 0) efekt się odwraca. Poziom toru liczymy z historii tego toru względem wszystkich torów.
"""
from __future__ import annotations

from collections import defaultdict
from statistics import mean, pstdev

import config
from factors.base import RaceContext, zscore

LEVEL_CLIP = 2.0


def _usable(ctx: RaceContext):
    return [a for a in ctx.aggregates if a.tyre_deg and a.track_deg is not None]


def _circuit_degs(ctx: RaceContext, usable) -> list[float]:
    return [a.track_deg for a in usable if a.circuit_id == ctx.race.circuit_id]


def track_deg_ratio(ctx: RaceContext) -> float | None:
    """Średnie zużycie na tym torze / średnie na wszystkich torach (1 = przeciętnie, > 1 = opony cierpią)."""
    usable = _usable(ctx)
    here = _circuit_degs(ctx, usable)
    if not here:
        return None
    overall = mean(a.track_deg for a in usable)
    return mean(here) / overall if overall > 0 else None


class TyreDegFit:
    name = "tyre_deg_fit"

    def score(self, ctx: RaceContext) -> dict[str, float] | None:
        usable = _usable(ctx)
        if len(usable) < config.TYRE_FIT_MIN_RACES:
            return None
        here = _circuit_degs(ctx, usable)
        if not here:
            return None
        all_degs = [a.track_deg for a in usable]
        spread = pstdev(all_degs)
        level = 0.0 if spread == 0 else max(-LEVEL_CLIP, min(LEVEL_CLIP, (mean(here) - mean(all_degs)) / spread))

        weighted: dict[str, float] = defaultdict(float)
        total: dict[str, float] = defaultdict(float)
        for age, agg in enumerate(reversed(usable)):          # age 0 = najnowszy wyścig
            w = 0.5 ** (age / config.FORM_HALF_LIFE_ROUNDS)
            for team, deg in agg.tyre_deg.items():
                weighted[team] += w * deg
                total[team] += w
        team_z = zscore({t: weighted[t] / total[t] for t in total})    # wyższe = gorsze zużycie
        scores = {t: -z * level for t, z in team_z.items()}
        return {e.driver_id: scores[e.team_id] for e in ctx.entries if e.team_id in scores}
