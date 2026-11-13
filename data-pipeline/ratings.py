"""Dynamiczne oceny siły (model v3, etap 3): auto i kierowca osobno, uczone z całej kolejności mety.

Model Plackett-Luce: siła uczestnika to `ocena auta + poprawka kierowcy`, a kolejność mety jest sekwencją losowań "kto jest
najlepszy z pozostałych". Po każdym wyścigu robimy jeden krok gradientu (uogólnione Elo). Kierowcy, którzy nie dojechali do
mety, są pomijani w rankingu danego wyścigu (awaria nie jest wskaźnikiem umiejętności), a przy zmianie sezonu oceny są ściągane ku 0.
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from collections.abc import Callable
from dataclasses import dataclass, field
from statistics import mean

from schemas import HistoricRace


def finished(status: str) -> bool:
    """Dojechał do mety (także okrążony). Awarie, wypadki i dyskwalifikacje to nie jest wynik sportowy."""
    return status in ("Finished", "Lapped") or status.startswith("+")


@dataclass
class Ratings:
    car: dict[str, float] = field(default_factory=dict)
    driver: dict[str, float] = field(default_factory=dict)
    trend: dict[str, float] = field(default_factory=dict)    # wygładzona zmiana oceny auta po wyścigu (zespół przyspiesza / zwalnia)

    def strength(self, driver_id: str, team_id: str, trend_gain: float = 0.0) -> float:
        return self.car.get(team_id, 0.0) + trend_gain * self.trend.get(team_id, 0.0) + self.driver.get(driver_id, 0.0)


def update_race(ratings: Ratings, order: Sequence[tuple[str, str]], eta_car: float, eta_driver: float) -> None:
    """Jeden krok uczenia po wyścigu. `order`: (driver_id, team_id) od najlepszego do najgorszego."""
    if len(order) < 2:
        return
    strengths = [ratings.strength(d, t) for d, t in order]
    grad = [0.0] * len(order)
    for k in range(len(order) - 1):
        tail = strengths[k:]
        peak = max(tail)
        weights = [math.exp(s - peak) for s in tail]
        total = sum(weights)
        for offset, w in enumerate(weights):
            grad[k + offset] -= w / total          # kara za każdego, kto "mógł" być wybrany
        grad[k] += 1.0                             # nagroda dla faktycznie wybranego na tym miejscu
    team_grad: dict[str, float] = {}
    for (driver, team), g in zip(order, grad):
        ratings.driver[driver] = ratings.driver.get(driver, 0.0) + eta_driver * g
        team_grad[team] = team_grad.get(team, 0.0) + g
    for team, g in team_grad.items():
        ratings.car[team] = ratings.car.get(team, 0.0) + eta_car * g


def new_season(ratings: Ratings, car_keep: float, driver_keep: float) -> None:
    """Początek sezonu: samochody się zmieniają (mocne ściąganie), kierowcy zmieniają się wolniej."""
    for team in ratings.car:
        ratings.car[team] *= car_keep
    for driver in ratings.driver:
        ratings.driver[driver] *= driver_keep


def build_ratings(history: Sequence[HistoricRace], eta_car: float, eta_driver: float, car_keep: float,
                  driver_keep: float, *, trend_alpha: float = 0.0, lineage: dict[str, str] | None = None,
                  supplier_of: Callable[[int, str], str | None] | None = None, supplier_weight: float = 0.0) -> Ratings:
    """Oceny z wyników rozegranych wyścigów (kolejność wejścia bez znaczenia: sortujemy chronologicznie).

    Trend: po każdym wyścigu `trend = (1 - alpha) * trend + alpha * zmiana oceny auta` (na granicy sezonu x0,5).
    Dziedziczenie: zespół, którego nie było w poprzednim sezonie, a jego poprzednik (`lineage`) był, startuje z oceną poprzednika.
    Punkt startowy z dostawcy: zespół bez żadnej oceny dostaje `supplier_weight` x średnia ocen zespołów z tym samym silnikiem."""
    ratings = Ratings()
    season = None
    prev_teams: set[str] = set()
    cur_teams: set[str] = set()
    for race in sorted(history, key=lambda h: (h.season, h.round)):
        if season is not None and race.season != season:
            new_season(ratings, car_keep, driver_keep)
            ratings.trend = {t: v * 0.5 for t, v in ratings.trend.items()}
            prev_teams, cur_teams = cur_teams, set()
        season = race.season
        for team in {r.team_id for r in race.results} - cur_teams:          # pierwszy wyścig zespołu w tym sezonie
            predecessor = (lineage or {}).get(team)
            if predecessor and team not in prev_teams and predecessor in prev_teams and predecessor in ratings.car:
                ratings.car[team] = ratings.car[predecessor]
                ratings.trend[team] = ratings.trend.get(predecessor, 0.0)
            elif team not in ratings.car and supplier_of and supplier_weight > 0:
                supplier = supplier_of(season, team)
                mates = [v for t, v in ratings.car.items() if t != team and supplier and supplier_of(season, t) == supplier]
                if mates:
                    ratings.car[team] = supplier_weight * mean(mates)
            cur_teams.add(team)
        ranked = sorted((r for r in race.results if r.finish is not None and finished(r.status)), key=lambda r: r.finish)
        before = dict(ratings.car)
        update_race(ratings, [(r.driver_id, r.team_id) for r in ranked], eta_car, eta_driver)
        if trend_alpha > 0:
            for team in {r.team_id for r in ranked}:
                delta = ratings.car.get(team, 0.0) - before.get(team, 0.0)
                ratings.trend[team] = (1 - trend_alpha) * ratings.trend.get(team, 0.0) + trend_alpha * delta
    return ratings
