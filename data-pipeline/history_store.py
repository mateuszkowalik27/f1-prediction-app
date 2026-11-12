"""Magazyn agregatów zakończonych wyścigów: jeden plik JSON na wyścig, zapisywany raz i atomowo."""
from __future__ import annotations

import os
from pathlib import Path

from schemas import RaceAggregates


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

    def save(self, agg: RaceAggregates) -> bool:
        """Zapisuje agregat. Poprawnego pliku nigdy nie nadpisuje (zwraca False); uszkodzony zastępuje."""
        if self.load(agg.season, agg.round) is not None:
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

    @staticmethod
    def _load_path(path: Path) -> RaceAggregates | None:
        try:
            return RaceAggregates.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
