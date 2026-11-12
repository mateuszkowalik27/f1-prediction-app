"""Symulacja wyścigu Monte Carlo: tempo = siła - kara za pozycję startową (zależna od toru) + losowość."""
from __future__ import annotations

import numpy as np

import config
from schemas import DriverProbability, TrackStats


def apply_early_season(
    dnf: dict[str, float], track: TrackStats, round: int,
) -> tuple[dict[str, float], TrackStats]:
    """W pierwszych rundach sezonu ryzyko awarii i safety cara jest większe."""
    if round > config.EARLY_SEASON_ROUNDS:
        return dnf, track
    m = config.EARLY_SEASON_RISK_MULTIPLIER
    return (
        {d: min(1.0, p * m) for d, p in dnf.items()},
        track.model_copy(update={"sc_probability": min(1.0, track.sc_probability * m)}),
    )


def simulate_race(
    strength: dict[str, float],
    grid: dict[str, int] | None,
    track: TrackStats,
    dnf: dict[str, float],
    stops: int,
    n: int = config.N_SIMULATIONS,
    seed: int = config.RANDOM_SEED,
    grid_weight: float = config.GRID_BASE_WEIGHT,
    noise_base: float = config.RACE_NOISE_BASE,
    qualifying_noise: float = config.QUALIFYING_NOISE,
) -> list[DriverProbability]:
    """grid=None oznacza, że kwalifikacje jeszcze się nie odbyły: siatka jest losowana w każdej symulacji."""
    drivers = sorted(strength)
    count = len(drivers)
    base = np.array([strength[d] for d in drivers])
    rng = np.random.default_rng(seed)
    if grid is None:
        quali = base + rng.normal(0.0, qualifying_noise, size=(n, count))
        grid_pos = (-quali).argsort(axis=1, kind="stable").argsort(axis=1, kind="stable") + 1.0
    else:
        grid_pos = np.array([grid.get(d) or count for d in drivers], dtype=float)  # brak/0 = start z końca
    penalty = grid_weight * track.overtaking_difficulty * (grid_pos - 1)
    sigma = (noise_base * (1 + config.SC_NOISE_FACTOR * track.sc_probability)
             * (1 + config.PIT_NOISE * stops))
    default_dnf = float(np.mean(list(dnf.values()))) if dnf else config.DEFAULT_DNF_RATE
    p_dnf = np.array([dnf.get(d, default_dnf) for d in drivers])

    pace = base - penalty + rng.normal(0.0, sigma, size=(n, count))
    retired = rng.random((n, count)) < p_dnf
    pace = np.where(retired, -np.inf, pace)
    ranks = (-pace).argsort(axis=1, kind="stable").argsort(axis=1, kind="stable")  # 0 = zwycięzca
    finished = ~retired

    scoring_places = min(len(config.POINTS_TABLE), count)
    points_by_rank = np.zeros(count)
    points_by_rank[:scoring_places] = config.POINTS_TABLE[:scoring_places]

    result = []
    for i, driver in enumerate(drivers):
        r, ok = ranks[:, i], finished[:, i]
        result.append(DriverProbability(
            driver_id=driver,
            win=float(((r == 0) & ok).mean()),
            podium=float(((r < 3) & ok).mean()),
            points=float(((r < scoring_places) & ok).mean()),
            expected_points=float((points_by_rank[r] * ok).mean()),
            position_distribution=(np.bincount(r, minlength=count) / n).tolist(),
        ))
    return result
