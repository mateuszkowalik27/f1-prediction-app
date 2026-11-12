"""Strategia opon: najbardziej prawdopodobna liczba pit-stopów i mieszanki, plus alternatywa.

Reguły (progi w config.py): deszcz powyżej progu = start na przejściówkach; wysokie ryzyko safety cara
= alternatywa z mniejszą liczbą postojów; w przeciwnym razie alternatywa z większą.
"""
from __future__ import annotations

import config
from schemas import Strategy, StrategyPrediction, TrackStats, TyreHistory, WeatherForecast

DEFAULT_COMPOUNDS = ["MEDIUM", "HARD"]


def _main_compounds(history: TyreHistory | None) -> list[str]:
    compounds = list(history.dominant_compounds[:2]) if history and history.dominant_compounds else []
    if not compounds:
        return list(DEFAULT_COMPOUNDS)
    if len(compounds) == 1:  # przepisy wymagają dwóch różnych mieszanek
        compounds.append("HARD" if compounds[0] != "HARD" else "MEDIUM")
    return compounds


def _sequence(compounds: list[str], stops: int) -> list[str]:
    return [compounds[i % 2] for i in range(stops + 1)]


def predict_strategy(
    track: TrackStats, weather: WeatherForecast | None, tyre_history: TyreHistory | None,
    deg_ratio: float | None = None,
) -> StrategyPrediction:
    """deg_ratio: poziom zużycia opon na torze względem średniej (>= DEG_HIGH_RATIO = opony cierpią)."""
    stops = tyre_history.median_stops if tyre_history else config.DEFAULT_STOPS
    compounds = _main_compounds(tyre_history)
    rain = weather.rain_probability if weather else 0.0

    primary = _sequence(compounds, stops)
    if rain >= config.RAIN_START_INTERMEDIATE:
        primary[0] = "INTERMEDIATE"

    alt_stops = max(1, stops - 1) if track.sc_probability >= config.SC_ALT_THRESHOLD else stops + 1
    alternative = _sequence(compounds[::-1], alt_stops)  # inna kolejność mieszanek niż strategia główna

    if tyre_history is None:
        confidence = "low"
    elif weather is not None and rain < config.RAIN_START_INTERMEDIATE:
        confidence = "high"
    else:
        confidence = "medium"
    if deg_ratio is not None and deg_ratio >= config.DEG_HIGH_RATIO:
        alt_stops = stops + 1   # duże zużycie: realna alternatywa to dodatkowy postój (ma pierwszeństwo przed regułą safety car)
        confidence = {"high": "medium", "medium": "low", "low": "low"}[confidence]
        alternative = _sequence(compounds[::-1], alt_stops)
    return StrategyPrediction(
        primary=Strategy(stops=stops, compounds=primary),
        alternative=Strategy(stops=alt_stops, compounds=alternative),
        rain_risk=rain,
        confidence=confidence,
    )
