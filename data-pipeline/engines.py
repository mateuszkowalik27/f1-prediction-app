"""Dostawcy silników i linie zespołów (model v3, etap 6). Tabele są RĘCZNE: co sezon sprawdź `ENGINE_SUPPLIER` w `config.py`
(robot ostrzega na stderr o zespole bez dostawcy)."""
from __future__ import annotations

from collections.abc import Iterable

import config


def supplier_of(season: int, team_id: str) -> str | None:
    """Dostawca silnika zespołu w danym sezonie albo None (nieznany sezon lub zespół)."""
    for supplier, teams in config.ENGINE_SUPPLIER.get(season, {}).items():
        if team_id in teams:
            return supplier
    return None


def predecessor_of(team_id: str) -> str | None:
    """Poprzednia nazwa tego samego zespołu (Audi po Sauberze, RB po AlphaTauri...) albo None."""
    return config.TEAM_LINEAGE.get(team_id)


def uncovered_teams(season: int, team_ids: Iterable[str]) -> list[str]:
    """Zespoły z listy, które nie mają dostawcy w tabeli danego sezonu (do ostrzeżenia i testu pokrycia)."""
    return [t for t in team_ids if supplier_of(season, t) is None]
