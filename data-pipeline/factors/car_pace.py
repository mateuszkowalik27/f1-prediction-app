"""Siła bolidu: średnia punktów zespołu w ostatnich wyścigach (nowsze ważą więcej)."""
from __future__ import annotations

from collections import defaultdict

import config
from factors.base import RaceContext, chronological, race_points, zscore
from schemas import HistoricRace


def team_points(race: HistoricRace) -> dict[str, float]:
    points: dict[str, float] = defaultdict(float)
    for r in race.results:
        points[r.team_id] += race_points(r.finish)
    return dict(points)


def team_result_z(ctx: RaceContext, race: HistoricRace) -> dict[str, float]:
    """Wynik zespołów w jednym wyścigu jako z-score (wyższy = lepszy)."""
    return zscore(team_points(race))


class CarPace:
    name = "car_pace"

    def score(self, ctx: RaceContext) -> dict[str, float] | None:
        history = chronological(ctx.history)
        if not history:
            return None
        weighted: dict[str, float] = defaultdict(float)
        total: dict[str, float] = defaultdict(float)
        for age, race in enumerate(reversed(history)):  # age 0 = ostatni wyścig
            w = 0.5 ** (age / config.FORM_HALF_LIFE_ROUNDS)
            for team, pts in team_points(race).items():
                weighted[team] += w * pts
                total[team] += w
        z = zscore({t: weighted[t] / total[t] for t in total})
        return {e.driver_id: z[e.team_id] for e in ctx.entries if e.team_id in z}
