"""Matematyka agregatów wyścigu: czyste funkcje liczące cechy z surowych danych (bez sieci)."""
from __future__ import annotations

from collections import defaultdict
from statistics import median

import config
from schemas import PitStop, QualiTimes


def _session_gaps(times: list[QualiTimes], session: str) -> dict[str, float]:
    """Strata każdego kierowcy do najszybszego w TEJ SESJI, w procentach."""
    values = {t.driver_id: getattr(t, session) for t in times if getattr(t, session) is not None}
    if not values:
        return {}
    fastest = min(values.values())
    return {d: (v - fastest) / fastest * 100 for d, v in values.items()}


def _median_shift(upper: dict[str, float], lower: dict[str, float]) -> float:
    """Mediana (strata w sesji późniejszej minus we wcześniejszej) kierowców startujących w obu."""
    shifts = [upper[d] - lower[d] for d in upper if d in lower]
    return median(shifts) if shifts else 0.0


def link_session_gaps(times: list[QualiTimes]) -> dict[str, float]:
    """Jedna liczba na kierowcę: strata do pole w %, z "sklejonych" sesji Q1/Q2/Q3.

    Kierowca z Q3 ma stratę z Q3. Kierowca odpadły w Q2 dostaje stratę z Q2 plus typowe przesunięcie Q2->Q3
    (mediana różnic kierowców, którzy byli w obu), a odpadły w Q1: stratę z Q1 plus przesunięcia Q1->Q2 i Q2->Q3.
    Dzięki temu strata odpadniętych jest w skali Q3, mimo że ich czas pochodzi z wcześniejszej, "wolniejszej" sesji.
    """
    g1, g2, g3 = (_session_gaps(times, s) for s in ("q1", "q2", "q3"))
    d23 = _median_shift(g3, g2)
    d12 = _median_shift(g2, g1)
    result: dict[str, float] = {}
    for t in times:
        d = t.driver_id
        if d in g3:
            result[d] = g3[d]
        elif d in g2:
            result[d] = g2[d] + d23
        elif d in g1:
            result[d] = g1[d] + d12 + d23
    return result


def compute_pit_deltas(stops: list[PitStop], team_of: dict[str, str]) -> dict[str, float]:
    """team_id -> mediana (czas postoju minus mediana wyścigu). Odrzuca postoje odstające (czerwona flaga,
    kary) i zespoły z mniej niż 2 postojami."""
    if not stops:
        return {}
    raw_median = median(s.duration_s for s in stops)
    kept = [s for s in stops if s.duration_s <= config.PIT_OUTLIER_RATIO * raw_median]
    if not kept:
        return {}
    race_median = median(s.duration_s for s in kept)
    per_team: dict[str, list[float]] = defaultdict(list)
    for s in kept:
        team = team_of.get(s.driver_id)
        if team:
            per_team[team].append(s.duration_s - race_median)
    return {team: median(v) for team, v in per_team.items() if len(v) >= 2}
