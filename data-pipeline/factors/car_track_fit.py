"""Dopasowanie bolidu do toru: na jakich typach zakrętów dany zespół jest mocny.

Dla każdego zespołu regresja grzbietowa: wynik zespołu w wyścigu ~ [udział wolnych, udział szybkich zakrętów]
(średnie wynikają z reszty). Zastosowana do profilu bieżącego toru.
"""
from __future__ import annotations

import numpy as np

import config
from factors.base import RaceContext, chronological
from factors.car_pace import team_result_z

EXTRAPOLATION_LIMIT = 2.0  # tor nietypowy nie może wyrzucić przewidywania poza ±2 odchylenia cech


class CarTrackFit:
    name = "car_track_fit"

    def score(self, ctx: RaceContext) -> dict[str, float] | None:
        if ctx.profile is None:
            return None
        rows: list[tuple[list[float], dict[str, float]]] = []
        for race in chronological(ctx.history):
            profile = ctx.profiles.get(race.circuit_id)
            if profile is not None:
                rows.append(([profile.slow, profile.fast], team_result_z(ctx, race)))
        if len(rows) < config.FIT_MIN_RACES:
            return None

        X = np.array([r[0] for r in rows])
        mean, std = X.mean(axis=0), X.std(axis=0)
        std[std == 0] = 1.0
        Z = (X - mean) / std
        current = np.clip((np.array([ctx.profile.slow, ctx.profile.fast]) - mean) / std,
                          -EXTRAPOLATION_LIMIT, EXTRAPOLATION_LIMIT)

        team_pred: dict[str, float] = {}
        for team in {t for _, z in rows for t in z}:
            obs = [(i, z[team]) for i, (_, z) in enumerate(rows) if team in z]
            if len(obs) < config.FIT_MIN_RACES:
                continue
            Zt = Z[[i for i, _ in obs]]
            y = np.array([v for _, v in obs])
            Zc = Zt - Zt.mean(axis=0)
            beta = np.linalg.solve(Zc.T @ Zc + config.FIT_RIDGE * np.eye(2), Zc.T @ (y - y.mean()))
            team_pred[team] = float(beta @ (current - Zt.mean(axis=0)))
        if not team_pred:
            return None
        return {e.driver_id: team_pred[e.team_id] for e in ctx.entries if e.team_id in team_pred}
