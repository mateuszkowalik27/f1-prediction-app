"""Niezawodność: odsetek wyścigów bez klasyfikacji (DNF) zespołu i kierowcy, ściągany ku średniej."""
from __future__ import annotations

from collections import defaultdict

import config
from factors.base import RaceContext, zscore


def _counts(ctx: RaceContext):
    team = defaultdict(lambda: [0, 0])    # [awarie, starty]
    driver = defaultdict(lambda: [0, 0])
    for race in ctx.history:
        for r in race.results:
            dnf = r.finish is None
            for bucket, key in ((team, r.team_id), (driver, r.driver_id)):
                bucket[key][0] += dnf
                bucket[key][1] += 1
    starts = sum(v[1] for v in team.values())
    global_rate = sum(v[0] for v in team.values()) / starts if starts else config.DEFAULT_DNF_RATE
    return team, driver, global_rate, starts


def _team_rate(team, team_id: str, global_rate: float) -> float:
    k = config.DNF_PRIOR_STRENGTH
    dnf, starts = team.get(team_id, (0, 0))
    return (dnf + k * global_rate) / (starts + k)


def dnf_rates(ctx: RaceContext) -> dict[str, float]:
    """driver_id -> prawdopodobieństwo DNF (0-1). Debiutant dostaje wskaźnik swojego zespołu."""
    team, driver, global_rate, _ = _counts(ctx)
    k = config.DNF_PRIOR_STRENGTH
    rates = {}
    for e in ctx.entries:
        prior = _team_rate(team, e.team_id, global_rate)
        dnf, starts = driver.get(e.driver_id, (0, 0))
        rates[e.driver_id] = min(1.0, max(0.0, (dnf + k * prior) / (starts + k)))
    return rates


class Reliability:
    name = "reliability"

    def score(self, ctx: RaceContext) -> dict[str, float] | None:
        team, _, global_rate, starts = _counts(ctx)
        if starts == 0:
            return None
        z = zscore({e.team_id: -_team_rate(team, e.team_id, global_rate) for e in ctx.entries})
        return {e.driver_id: z[e.team_id] for e in ctx.entries}
