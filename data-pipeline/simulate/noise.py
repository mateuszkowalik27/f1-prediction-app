"""Losowość symulacji (model v3, etap 4): wspólny wstrząs zespołu i chaos (mieszanka rozkładów).

Wstrząs zespołu: obaj kierowcy jednego auta dostają ten sam dobry lub zły dzień (ustawienia auta, charakterystyka toru).
Całkowita wariancja każdego kierowcy zostaje `sigma^2`: część `team_share` jest wspólna, reszta indywidualna.
Chaos: w części symulacji (deszcz, safety car, kolizje na starcie) cała losowość jest `chaos_mult` razy większa; to daje grube
ogony, czyli rzadkie, ale możliwe niespodzianki. Przy zerowych parametrach losowania są identyczne jak przed etapem 4.
"""
from __future__ import annotations

import numpy as np


def draw_noise(rng: np.random.Generator, n: int, drivers: list[str], sigma: float, teams: dict[str, str] | None = None,
               team_share: float = 0.0, chaos_prob: float = 0.0, chaos_mult: float = 1.0) -> np.ndarray:
    """Macierz (n symulacji x kierowcy) losowych odchyleń tempa."""
    count = len(drivers)
    if team_share <= 0.0 and chaos_prob <= 0.0:
        return rng.normal(0.0, sigma, size=(n, count))          # dokładnie jak dotychczas
    share = min(max(team_share, 0.0), 1.0)
    noise = np.sqrt(1.0 - share) * rng.normal(size=(n, count))
    if share > 0.0:
        index: dict[str, int] = {}
        columns = []
        for i, driver in enumerate(drivers):
            team = (teams or {}).get(driver, f"__solo_{driver}")    # kierowca bez zespołu ma własny, jednoosobowy wstrząs
            columns.append(index.setdefault(team, len(index)))
        shocks = rng.normal(size=(n, len(index)))
        noise = noise + np.sqrt(share) * shocks[:, columns]
    noise = noise * sigma
    if chaos_prob > 0.0:
        scale = np.where(rng.random(n) < chaos_prob, chaos_mult, 1.0)[:, None]
        noise = noise * scale
    return noise


def chaos_prob_from(weights: dict[str, float], sc: float = 0.0, rain: float = 0.0) -> float:
    """Prawdopodobieństwo chaosu w wyścigu: baza + składnik od ryzyka safety cara i szansy deszczu, w granicach [0, 0,6]."""
    p = weights.get("chaos_base", 0.0) + weights.get("chaos_sc", 0.0) * sc + weights.get("chaos_rain", 0.0) * rain
    return float(min(max(p, 0.0), 0.6))
