"""Sygnały z sesji bieżącego weekendu (model v3, etap 5): tempo z długich przejazdów FP2, symulacja kwalifikacji z FP3,
strata w kwalifikacjach sprintu. Czyste funkcje (bez sieci); wszystkie wyniki w % względem mediany stawki (ujemne = szybciej)."""
from __future__ import annotations

from collections import defaultdict
from statistics import mean, median

import config
from aggregates import _clean_laps
from schemas import LapRecord


def _compound_offsets(by_compound: dict[str, dict[str, float]]) -> dict[str, float]:
    """Przesunięcie czasu każdej mieszanki względem referencyjnej (najliczniejszej; remis: alfabetycznie), liczone na kierowcach
    obecnych w obu. Mieszanka bez wspólnych kierowców z referencją jest pomijana (nie umiemy jej porównać)."""
    if not by_compound:
        return {}
    reference = sorted(by_compound, key=lambda c: (-len(by_compound[c]), c))[0]
    offsets = {reference: 0.0}
    for compound, times in by_compound.items():
        if compound == reference:
            continue
        shared = [times[d] - by_compound[reference][d] for d in times if d in by_compound[reference]]
        if shared:
            offsets[compound] = mean(shared)
    return offsets


def _relative(times: dict[str, float]) -> dict[str, float]:
    if not times:
        return {}
    field = median(times.values())
    return {d: (t / field - 1) * 100 for d, t in times.items()}


def long_run_pace(laps: list[LapRecord]) -> dict[str, float]:
    """Tempo z długich przejazdów: stinty min. PRACTICE_LONGRUN_MIN_LAPS czystych okrążeń na jednej mieszance, z korektą na paliwo,
    odrzuceniem okrążeń wolniejszych niż SLOW_LAP_RATIO x mediana stintu i przesunięciem między mieszankami."""
    by_driver: dict[str, list[LapRecord]] = defaultdict(list)
    for l in laps:
        by_driver[l.driver_id].append(l)
    stint_pace: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))   # kierowca -> mieszanka -> mediany stintów
    for driver, driver_laps in by_driver.items():
        stints: dict[tuple[str, int], list[LapRecord]] = defaultdict(list)
        for l in _clean_laps(driver_laps):
            if l.compound and l.tyre_age is not None:
                stints[(l.compound, l.tyre_age - l.lap)].append(l)
        for (compound, _), stint in stints.items():
            stint.sort(key=lambda l: l.lap)
            cap = config.SLOW_LAP_RATIO * median(l.duration_s for l in stint)
            kept = [l for l in stint if l.duration_s <= cap]
            if len(kept) < config.PRACTICE_LONGRUN_MIN_LAPS:
                continue
            start = kept[0].lap
            stint_pace[driver][compound].append(
                median(l.duration_s + config.FUEL_EFFECT_S_PER_LAP * (l.lap - start) for l in kept))
    by_compound: dict[str, dict[str, float]] = defaultdict(dict)
    for driver, per_compound in stint_pace.items():
        for compound, values in per_compound.items():
            by_compound[compound][driver] = mean(values)
    offsets = _compound_offsets(by_compound)
    adjusted: dict[str, list[float]] = defaultdict(list)
    for compound, times in by_compound.items():
        if compound in offsets:
            for driver, seconds in times.items():
                adjusted[driver].append(seconds - offsets[compound])
    return _relative({d: mean(v) for d, v in adjusted.items()})


def quali_sim_pace(laps: list[LapRecord]) -> dict[str, float]:
    """Symulacja kwalifikacji: najlepsze czyste okrążenie kierowcy po przesunięciu między mieszankami (najlepsze ze wszystkich mieszanek)."""
    by_driver: dict[str, list[LapRecord]] = defaultdict(list)
    for l in laps:
        by_driver[l.driver_id].append(l)
    by_compound: dict[str, dict[str, float]] = defaultdict(dict)
    for driver, driver_laps in by_driver.items():
        best: dict[str, float] = {}
        for l in _clean_laps(driver_laps):
            if l.compound:
                best[l.compound] = min(best.get(l.compound, l.duration_s), l.duration_s)
        for compound, seconds in best.items():
            by_compound[compound][driver] = seconds
    offsets = _compound_offsets(by_compound)
    adjusted: dict[str, float] = {}
    for compound, times in by_compound.items():
        if compound in offsets:
            for driver, seconds in times.items():
                adjusted[driver] = min(adjusted.get(driver, float("inf")), seconds - offsets[compound])
    return _relative(adjusted)


def gap_percent(best_times: dict[str, float]) -> dict[str, float]:
    """Strata do najszybszego w %, z najlepszych czasów kierowców."""
    if not best_times:
        return {}
    fastest = min(best_times.values())
    return {d: (t - fastest) / fastest * 100 for d, t in best_times.items()}
