"""Forma kierowcy: średnia punktów w ostatnich rundach."""
from __future__ import annotations

from collections import defaultdict

import config
from factors.base import RaceContext, chronological, race_points, zscore


class DriverForm:
    name = "driver_form"

    def score(self, ctx: RaceContext) -> dict[str, float] | None:
        recent = chronological(ctx.history)[-config.FORM_RACES:]
        if not recent:
            return None
        points: dict[str, list[int]] = defaultdict(list)
        for race in recent:
            for r in race.results:
                points[r.driver_id].append(race_points(r.finish))
        z = zscore({d: sum(p) / len(p) for d, p in points.items()})
        return {e.driver_id: z[e.driver_id] for e in ctx.entries if e.driver_id in z}
