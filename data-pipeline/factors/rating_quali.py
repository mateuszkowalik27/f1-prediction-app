"""Ocena kwalifikacyjna: strata do pole rozłożona na AUTO (średnia zespołu) i KIEROWCĘ (odchylenie od kolegi z zespołu).

Przewaga kierowcy nad kolegą zostaje z nim, gdy zmienia zespół, a nowy kierowca w znanym zespole dostaje tempo auta, nie zero.
Obie części są ściągane osobno: auto do średniej stawki, poprawka kierowcy do zera (porównanie z kolegą jest zaszumione).
"""
from __future__ import annotations

from collections import defaultdict
from statistics import mean

import config
from factors.base import RaceContext, zscore


class RatingQuali:
    name = "rating_quali"

    def score(self, ctx: RaceContext) -> dict[str, float] | None:
        usable = [a for a in ctx.aggregates if a.quali_gap]
        if len(usable) < config.AGGREGATE_MIN_RACES:
            return None
        team_of = {(h.season, h.round): {r.driver_id: r.team_id for r in h.results} for h in (ctx.long_history or ctx.history)}
        car_w, car_t, car_n = defaultdict(float), defaultdict(float), defaultdict(int)
        off_w, off_t, off_n = defaultdict(float), defaultdict(float), defaultdict(int)
        for age, agg in enumerate(reversed(usable)):          # age 0 = najnowszy wyścig
            teams = team_of.get((agg.season, agg.round))
            if not teams:
                continue
            w = 0.5 ** (age / config.FORM_HALF_LIFE_ROUNDS)
            by_team: dict[str, dict[str, float]] = defaultdict(dict)
            for driver, gap in agg.quali_gap.items():
                if driver in teams:
                    by_team[teams[driver]][driver] = min(gap, config.QUALI_GAP_CLIP)
            for team, gaps in by_team.items():
                car = mean(gaps.values())
                car_w[team] += w * car
                car_t[team] += w
                car_n[team] += 1
                if len(gaps) >= 2:                              # poprawkę kierowcy da się policzyć tylko względem kolegi
                    for driver, gap in gaps.items():
                        off_w[driver] += w * (gap - car)
                        off_t[driver] += w
                        off_n[driver] += 1
        if not car_t:
            return None
        car_raw = {t: car_w[t] / car_t[t] for t in car_t}
        field = mean(car_raw.values())
        k_car, k_driver = config.AGG_SHRINK_K, config.RATING_QUALI_DRIVER_K
        car = {t: field + (v - field) * car_n[t] / (car_n[t] + k_car) for t, v in car_raw.items()}
        offset = {d: off_w[d] / off_t[d] * off_n[d] / (off_n[d] + k_driver) for d in off_t}
        raw = {e.driver_id: -(car.get(e.team_id, field) + offset.get(e.driver_id, 0.0)) for e in ctx.entries}   # mniejsza strata = lepiej
        z = zscore(raw)
        return {e.driver_id: z[e.driver_id] for e in ctx.entries}
