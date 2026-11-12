"""Tempo z piątkowych treningów i wykrywanie zmiany formy zespołu w danym weekendzie."""
from __future__ import annotations

from collections import defaultdict
from statistics import mean

from factors.base import RaceContext, zscore
from factors.car_pace import CarPace
from schemas import PracticeData

SHIFT_CLIP = 2.0


def adjusted_practice(practice: PracticeData) -> dict[str, float]:
    """driver_id -> czas (s) sprowadzony do wspólnej mieszanki opon (mniejszy = szybszy)."""
    by_compound: dict[str, dict[str, float]] = defaultdict(dict)
    for driver, runs in practice.best_runs.items():
        for compound, seconds in runs:
            by_compound[compound][driver] = seconds
    if not by_compound:
        return {}
    reference = sorted(by_compound, key=lambda c: (-len(by_compound[c]), c))[0]
    offsets = {reference: 0.0}
    for compound, times in by_compound.items():
        if compound == reference:
            continue
        shared = [times[d] - by_compound[reference][d] for d in times if d in by_compound[reference]]
        if shared:  # bez wspólnych kierowców nie umiemy porównać mieszanek: pomijamy ją
            offsets[compound] = mean(shared)
    adjusted: dict[str, list[float]] = defaultdict(list)
    for compound, times in by_compound.items():
        if compound in offsets:
            for driver, seconds in times.items():
                adjusted[driver].append(seconds - offsets[compound])
    return {d: mean(v) for d, v in adjusted.items()}


def _team_practice_z(ctx: RaceContext) -> dict[str, float] | None:
    adj = adjusted_practice(ctx.practice) if ctx.practice else {}
    team_times: dict[str, list[float]] = defaultdict(list)
    for e in ctx.entries:
        if e.driver_id in adj:
            team_times[e.team_id].append(adj[e.driver_id])
    if not team_times:
        return None
    return zscore({t: -mean(v) for t, v in team_times.items()})  # szybciej = lepiej


class PracticePace:
    name = "practice_pace"

    def score(self, ctx: RaceContext) -> dict[str, float] | None:
        adj = adjusted_practice(ctx.practice) if ctx.practice else {}
        if not adj:
            return None
        z = zscore({d: -t for d, t in adj.items()})
        return {e.driver_id: z[e.driver_id] for e in ctx.entries if e.driver_id in z}


class WeekendShift:
    """Tempo zespołu w treningach minus jego tempo sezonowe: ślad poprawek bolidu."""

    name = "weekend_shift"

    def score(self, ctx: RaceContext) -> dict[str, float] | None:
        practice_z = _team_practice_z(ctx)
        season = CarPace().score(ctx)
        if practice_z is None or season is None:
            return None
        team_of = {e.driver_id: e.team_id for e in ctx.entries}
        season_z = {team_of[d]: s for d, s in season.items()}
        shift = {
            t: max(-SHIFT_CLIP, min(SHIFT_CLIP, practice_z[t] - season_z[t]))
            for t in practice_z if t in season_z
        }
        return {e.driver_id: shift[e.team_id] for e in ctx.entries if e.team_id in shift}
