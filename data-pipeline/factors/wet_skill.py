"""Umiejętność jazdy w deszczu: kierowca porównywany z partnerem z zespołu (bolid się skraca).

Dla każdego kierowcy: (średnia przewaga nad partnerem w mokrych wyścigach) minus (w suchych),
ściągnięta ku zeru im mniej mokrych wyścigów.
"""
from __future__ import annotations

from collections import defaultdict
from statistics import mean

import config
from factors.base import RaceContext, zscore
from schemas import DriverEntry, HistoricRace


def compute_wet_skill(
    races: list[HistoricRace], wet: dict[tuple[int, int], bool], entries: list[DriverEntry],
) -> dict[str, float]:
    gaps: dict[str, dict[bool, list[float]]] = {e.driver_id: {True: [], False: []} for e in entries}
    for race in races:
        is_wet = wet.get((race.season, race.round))
        if is_wet is None:
            continue  # nie wiemy, jaka była pogoda
        by_team = defaultdict(list)
        for r in race.results:
            by_team[r.team_id].append(r)
        for rows in by_team.values():
            for r in rows:
                if r.driver_id not in gaps or r.finish is None:
                    continue  # DNF pomijamy: przyczyną bywa awaria, nie umiejętność
                mates = [m.finish for m in rows if m.driver_id != r.driver_id and m.finish is not None]
                if mates:
                    gaps[r.driver_id][is_wet].append(mean(mates) - r.finish)  # dodatnie = lepszy od partnera
    skill = {}
    for driver_id, g in gaps.items():
        if g[True] and g[False]:
            n = len(g[True])
            skill[driver_id] = (mean(g[True]) - mean(g[False])) * n / (n + config.WET_SHRINK_K)
        else:
            skill[driver_id] = 0.0
    return skill


class WetSkill:
    name = "wet_skill"

    def score(self, ctx: RaceContext) -> dict[str, float] | None:
        if ctx.weather is None or ctx.weather.rain_probability < config.WET_MIN_RAIN_PROBABILITY:
            return None
        races = list({(r.season, r.round): r for r in ctx.history + ctx.circuit_history}.values())
        overrides = config.WET_SKILL_OVERRIDES
        if not any(ctx.wet.get((r.season, r.round)) for r in races) and not overrides:
            return None
        skill = compute_wet_skill(races, ctx.wet, ctx.entries)
        skill.update({d: v for d, v in overrides.items() if d in skill})
        return {d: ctx.weather.rain_probability * v for d, v in zscore(skill).items()}
