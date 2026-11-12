"""Matematyka agregatów wyścigu: czyste funkcje liczące cechy z surowych danych (bez sieci)."""
from __future__ import annotations

from collections import defaultdict
from statistics import median

import config
import numpy as np

from schemas import LapRecord, PitStop, QualiTimes


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


def _clean_laps(driver_laps: list[LapRecord]) -> list[LapRecord]:
    """Czyste okrążenia jednego kierowcy: bez 1. okrążenia, wyjazdów z boksu i okrążeń wjazdowych."""
    pit_out = {l.lap for l in driver_laps if l.is_pit_out}
    in_laps = {n - 1 for n in pit_out}
    return [l for l in driver_laps if l.duration_s and l.lap > 1 and l.lap not in pit_out and l.lap not in in_laps]


def compute_race_pace(laps: list[LapRecord]) -> dict[str, float]:
    """driver_id -> tempo wyścigowe w % względem mediany stawki (ujemne = szybciej).

    Dla kierowcy: mediana czystych okrążeń, bez okrążeń wolniejszych niż SLOW_LAP_RATIO x jego mediana
    (safety car, żółte flagi, błędy). Kierowca z mniej niż RACE_PACE_MIN_LAPS takimi okrążeniami pominięty.
    """
    by_driver: dict[str, list[LapRecord]] = defaultdict(list)
    for l in laps:
        by_driver[l.driver_id].append(l)
    medians: dict[str, float] = {}
    for driver, driver_laps in by_driver.items():
        clean = [l.duration_s for l in _clean_laps(driver_laps)]
        if len(clean) < config.RACE_PACE_MIN_LAPS:
            continue
        first = median(clean)
        kept = [t for t in clean if t <= config.SLOW_LAP_RATIO * first]
        if len(kept) >= config.RACE_PACE_MIN_LAPS:
            medians[driver] = median(kept)
    if not medians:
        return {}
    field = median(medians.values())
    return {d: (m / field - 1) * 100 for d, m in medians.items()}


def compute_tyre_deg(laps: list[LapRecord], team_of: dict[str, str]) -> tuple[dict[str, float], float | None]:
    """(team_id -> zużycie opon, poziom zużycia toru).

    Stint rozpoznajemy po stałej wartości (wiek opony - numer okrążenia). W stincie (>= MIN_STINT_LAPS czystych
    okrążeń) dopasowujemy prostą: czas okrążenia skorygowany o paliwo (+FUEL_EFFECT x okrążenie) względem wieku opony;
    nachylenie to zużycie w s/okrążenie. Zużycie zespołu = mediana (nachylenie minus mediana nachyleń tej samej
    mieszanki w wyścigu), więc twarde i miękkie nie mieszają się. Poziom toru = mediana wszystkich nachyleń.
    """
    by_driver: dict[str, list[LapRecord]] = defaultdict(list)
    for l in laps:
        by_driver[l.driver_id].append(l)
    stints: dict[tuple[str, str, int], list[LapRecord]] = defaultdict(list)
    for driver, driver_laps in by_driver.items():
        for l in _clean_laps(driver_laps):
            if l.compound and l.tyre_age is not None:
                stints[(driver, l.compound, l.tyre_age - l.lap)].append(l)
    slopes: list[tuple[str, str, float]] = []
    for (driver, compound, _), stint in stints.items():
        if len(stint) < config.MIN_STINT_LAPS:
            continue
        first = median(l.duration_s for l in stint)
        stint = [l for l in stint if l.duration_s <= config.SLOW_LAP_RATIO * first]
        if len(stint) < config.MIN_STINT_LAPS:
            continue
        x = np.array([l.tyre_age for l in stint], dtype=float)
        y = np.array([l.duration_s + config.FUEL_EFFECT_S_PER_LAP * l.lap for l in stint])
        if x.max() == x.min():
            continue
        slopes.append((driver, compound, float(np.polyfit(x, y, 1)[0])))
    if not slopes:
        return {}, None
    by_compound: dict[str, list[float]] = defaultdict(list)
    for _, compound, slope in slopes:
        by_compound[compound].append(slope)
    compound_median = {c: median(v) for c, v in by_compound.items()}
    per_team: dict[str, list[float]] = defaultdict(list)
    for driver, compound, slope in slopes:
        team = team_of.get(driver)
        if team:
            per_team[team].append(slope - compound_median[compound])
    return {t: median(v) for t, v in per_team.items()}, median(s for _, _, s in slopes)
