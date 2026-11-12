"""Magazyn agregatów zakończonych wyścigów: jeden plik JSON na wyścig, zapisywany raz i atomowo."""
from __future__ import annotations

import os
from pathlib import Path

import config
from schemas import RaceAggregates


def needs_retry(agg: RaceAggregates) -> bool:
    """Agregat niekompletny (brak którejś z części) i jeszcze nie wyczerpał prób dopełnienia."""
    if agg.attempts >= config.MAX_AGGREGATE_ATTEMPTS:
        return False
    incomplete = not agg.quali_gap or not agg.pit_delta
    if agg.season >= config.OPENF1_FIRST_SEASON:
        incomplete = incomplete or not agg.race_pace or agg.air_temp_c is None or not agg.official_grid
    return incomplete


class HistoryStore:
    def __init__(self, root: Path):
        self.root = Path(root)

    def path(self, season: int, round: int) -> Path:
        return self.root / f"{season}-{round}.json"

    def load(self, season: int, round: int) -> RaceAggregates | None:
        try:
            return RaceAggregates.model_validate_json(self.path(season, round).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None  # brak pliku albo uszkodzony: traktujemy jak brakujący

    def save(self, agg: RaceAggregates, overwrite: bool = False) -> bool:
        """Zapisuje agregat. Poprawnego pliku nadpisuje tylko na wyraźne polecenie (`overwrite`, przy dopełnianiu
        niekompletnego); inaczej zwraca False. Uszkodzony zastępuje zawsze."""
        if self.load(agg.season, agg.round) is not None and not overwrite:
            return False
        target = self.path(agg.season, agg.round)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + ".tmp")
        tmp.write_text(agg.model_dump_json(), encoding="utf-8")
        os.replace(tmp, target)
        return True

    def all(self) -> list[RaceAggregates]:
        if not self.root.is_dir():
            return []
        loaded = (self._load_path(p) for p in self.root.glob("*-*.json"))
        return sorted((a for a in loaded if a is not None), key=lambda a: (a.season, a.round))

    def missing(self, races: list[tuple[int, int]]) -> list[tuple[int, int]]:
        return [(s, r) for s, r in races if self.load(s, r) is None]

    def pending(self, races: list[tuple[int, int]]) -> list[tuple[int, int]]:
        """Wyścigi bez agregatu albo z niekompletnym, który warto jeszcze dopełnić."""
        out = []
        for s, r in races:
            agg = self.load(s, r)
            if agg is None or needs_retry(agg):
                out.append((s, r))
        return out

    @staticmethod
    def _load_path(path: Path) -> RaceAggregates | None:
        try:
            return RaceAggregates.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
