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


def coverage_warnings(season: int, team_ids: Iterable[str]) -> list[str]:
    """Komunikaty o niepełnej tabeli silników: brak całego sezonu albo konkretnych zespołów (jeden wiersz na problem)."""
    if season not in config.ENGINE_SUPPLIER:
        return [f"brak tabeli ENGINE_SUPPLIER dla sezonu {season}: dodaj dostawców silników w config.py"]
    missing = uncovered_teams(season, team_ids)
    return [f"zespół {', '.join(missing)} nie ma dostawcy silnika w ENGINE_SUPPLIER[{season}]"] if missing else []
