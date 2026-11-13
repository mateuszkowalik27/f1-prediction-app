"""Czynniki z sesji bieżącego weekendu (model v3, etap 5): z-score tempa z jednej sesji; brak danych = czynnik pominięty."""
from __future__ import annotations

from factors.base import RaceContext, zscore


class _SessionFactor:
    name = ""
    field = ""

    def score(self, ctx: RaceContext) -> dict[str, float] | None:
        values = getattr(ctx.signals, self.field) if ctx.signals else {}
        current = {e.driver_id for e in ctx.entries}
        raw = {d: -v for d, v in values.items() if d in current}          # szybciej (ujemne %) / mniejsza strata = lepiej
        if not raw:
            return None
        return zscore(raw)


class Fp2LongRun(_SessionFactor):
    """Tempo z długich przejazdów FP2 (tempo wyścigowe, korekta na paliwo i mieszanki): do siły wyścigowej."""
    name = "fp2_long_run"
    field = "long_run"


class Fp3QualiSim(_SessionFactor):
    """Najlepsze okrążenie z FP3 po przesunięciu między mieszankami (symulacja kwalifikacji): do siły kwalifikacyjnej."""
    name = "fp3_quali_sim"
    field = "quali_sim"


class SprintPace(_SessionFactor):
    """Czyste tempo okrążeń ze sprintu (weekendy sprinterskie): do siły wyścigowej."""
    name = "sprint_pace"
    field = "sprint_pace"


class SqQuali(_SessionFactor):
    """Strata w kwalifikacjach sprintu (weekendy sprinterskie): do siły kwalifikacyjnej głównych kwalifikacji."""
    name = "sq_quali"
    field = "sq_gap"
