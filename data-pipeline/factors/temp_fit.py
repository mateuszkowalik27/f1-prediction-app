"""Temperatura: które zespoły jeżdżą lepiej w upale, a które w chłodzie.

Ściągana regresja grzbietowa (FIT_RIDGE) wyniku zespołu w wyścigu względem temperatury powietrza, na wyścigach, dla
których mamy temperaturę (agregat) i wyniki (ctx.history). Wejściem jest temperatura POWIETRZA: prognoza (Open-Meteo)
podaje powietrze, a nie tor. Zastosowana do prognozowanej temperatury o godzinie startu.
"""
from __future__ import annotations

import numpy as np

import config
from factors.base import RaceContext
from factors.car_pace import team_result_z

EXTRAPOLATION_LIMIT = 2.0   # prognoza spoza typowego zakresu nie wyrzuci przewidywania poza +-2 odchylenia temperatury


class TempFit:
    name = "temp_fit"

    def score(self, ctx: RaceContext) -> dict[str, float] | None:
        now = ctx.weather.start_temperature_c if ctx.weather else None
        if now is None:
            return None
        races = {(h.season, h.round): h for h in ctx.history}
        rows = [(a.air_temp_c, team_result_z(ctx, races[(a.season, a.round)]))
                for a in ctx.aggregates if a.air_temp_c is not None and (a.season, a.round) in races]
        if len(rows) < config.FIT_MIN_RACES:
            return None
        temps = np.array([t for t, _ in rows])
        mean, std = temps.mean(), temps.std() or 1.0
        z = (temps - mean) / std
        current = float(np.clip((now - mean) / std, -EXTRAPOLATION_LIMIT, EXTRAPOLATION_LIMIT))

        team_pred: dict[str, float] = {}
        for team in {t for _, results in rows for t in results}:
            obs = [(z[i], results[team]) for i, (_, results) in enumerate(rows) if team in results]
            if len(obs) < config.FIT_MIN_RACES:
                continue
            x = np.array([o[0] for o in obs])
            y = np.array([o[1] for o in obs])
            xc = x - x.mean()
            beta = float(xc @ (y - y.mean()) / (xc @ xc + config.FIT_RIDGE))
            team_pred[team] = beta * (current - float(x.mean()))
        if not team_pred:
            return None
        return {e.driver_id: team_pred[e.team_id] for e in ctx.entries if e.team_id in team_pred}
