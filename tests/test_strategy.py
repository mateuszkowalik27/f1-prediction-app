from datetime import datetime, timezone

import config
from helpers import make_track
from schemas import TyreHistory, WeatherForecast
from simulate.strategy import predict_strategy


def weather(rain):
    return WeatherForecast(rain_probability=rain, temperature_c=20.0, fetched_at=datetime.now(timezone.utc))


def history(stops=2):
    return TyreHistory(median_stops=stops, dominant_compounds=["MEDIUM", "HARD"])


def test_default_stops_low_confidence_without_history():
    s = predict_strategy(make_track(), weather(0.0), None)
    assert s.primary.stops == config.DEFAULT_STOPS
    assert s.confidence == "low"
    assert len(s.primary.compounds) == s.primary.stops + 1


def test_uses_history_median_stops():
    s = predict_strategy(make_track(sc=0.2), weather(0.0), history(stops=1))
    assert s.primary.stops == 1
    assert s.primary.compounds == ["MEDIUM", "HARD"]
    assert s.confidence != "low"


def test_two_stops_alternate_between_the_two_main_compounds():
    s = predict_strategy(make_track(sc=0.2), weather(0.0), history(stops=2))
    assert s.primary.compounds == ["MEDIUM", "HARD", "MEDIUM"]


def test_heavy_rain_starts_on_intermediates():
    s = predict_strategy(make_track(), weather(config.RAIN_START_INTERMEDIATE + 0.1), history())
    assert s.primary.compounds[0] == "INTERMEDIATE"
    assert s.rain_risk == config.RAIN_START_INTERMEDIATE + 0.1


def test_light_rain_keeps_slicks():
    s = predict_strategy(make_track(), weather(0.2), history())
    assert "INTERMEDIATE" not in s.primary.compounds


def test_high_sc_odds_alternative_has_fewer_stops():
    s = predict_strategy(make_track(sc=config.SC_ALT_THRESHOLD + 0.1), weather(0.0), history(stops=2))
    assert s.alternative.stops == 1


def test_low_sc_odds_alternative_has_more_stops():
    s = predict_strategy(make_track(sc=0.2), weather(0.0), history(stops=2))
    assert s.alternative.stops == 3


def test_works_without_weather():
    s = predict_strategy(make_track(), None, history())
    assert s.rain_risk == 0.0
