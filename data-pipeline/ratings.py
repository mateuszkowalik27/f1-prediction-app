"""Dynamiczne oceny siły (model v3, etap 3): auto i kierowca osobno, uczone z całej kolejności mety.

Model Plackett-Luce: siła uczestnika to `ocena auta + poprawka kierowcy`, a kolejność mety jest sekwencją losowań "kto jest
najlepszy z pozostałych". Po każdym wyścigu robimy jeden krok gradientu (uogólnione Elo). Kierowcy, którzy nie dojechali do
mety, są pomijani w rankingu danego wyścigu (awaria nie jest wskaźnikiem umiejętności), a przy zmianie sezonu oceny są ściągane ku 0.
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field

from schemas import HistoricRace


def finished(status: str) -> bool:
    """Dojechał do mety (także okrążony). Awarie, wypadki i dyskwalifikacje to nie jest wynik sportowy."""
    return status in ("Finished", "Lapped") or status.startswith("+")


@dataclass
class Ratings:
    car: dict[str, float] = field(default_factory=dict)
    driver: dict[str, float] = field(default_factory=dict)

    def strength(self, driver_id: str, team_id: str) -> float:
        return self.car.get(team_id, 0.0) + self.driver.get(driver_id, 0.0)


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
                  driver_keep: float) -> Ratings:
    """Oceny z wyników rozegranych wyścigów (kolejność wejścia bez znaczenia: sortujemy chronologicznie)."""
    ratings = Ratings()
    season = None
    for race in sorted(history, key=lambda h: (h.season, h.round)):
        if season is not None and race.season != season:
            new_season(ratings, car_keep, driver_keep)
        season = race.season
        ranked = sorted((r for r in race.results if r.finish is not None and finished(r.status)), key=lambda r: r.finish)
        update_race(ratings, [(r.driver_id, r.team_id) for r in ranked], eta_car, eta_driver)
    return ratings
