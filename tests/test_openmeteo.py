import json
from datetime import date
from pathlib import Path

import httpx
import pytest

from fetch.openmeteo import fetch_forecast, fetch_historical_rain_mm, wet_races
from schemas import HistoricRace

FIX = Path(__file__).parent / "fixtures"
TODAY = date(2026, 11, 12)


def client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def forecast_handler(request):
    return httpx.Response(200, json=json.loads((FIX / "openmeteo_forecast.json").read_text()))


def test_forecast_returns_rain_probability_as_fraction():
    f = fetch_forecast(36.11, -115.17, date(2026, 11, 21), http=client(forecast_handler), today=TODAY)
    assert f.rain_probability == pytest.approx(0.13)
    assert f.temperature_c == pytest.approx(16.1)


def test_forecast_none_beyond_16_days():
    def must_not_be_called(request):
        raise AssertionError("brak żądania HTTP dla daty poza zasięgiem prognozy")

    far = date(2026, 11, 29)  # 17 dni od TODAY
    assert fetch_forecast(36.11, -115.17, far, http=client(must_not_be_called), today=TODAY) is None


def test_forecast_none_on_http_error():
    http = client(lambda request: httpx.Response(500))
    assert fetch_forecast(36.11, -115.17, date(2026, 11, 21), http=http, today=TODAY) is None


def test_historical_rain_sum():
    archive = json.loads((FIX / "openmeteo_archive.json").read_text())
    http = client(lambda request: httpx.Response(200, json=archive))
    assert fetch_historical_rain_mm(43.73, 7.42, date(2024, 5, 26), http=http) == 0.0


def _race(season, rnd, day):
    return HistoricRace(season=season, round=rnd, circuit_id="c", date=day, lat=1.0, lon=2.0, results=[])


def test_wet_races_flags_by_threshold_and_skips_missing():
    rain = {"2024-05-26": 0.2, "2023-05-28": 3.0}  # 2022-05-29 celowo brak -> błąd HTTP

    def handler(request):
        day = request.url.params["start_date"]
        if day not in rain:
            return httpx.Response(500)
        return httpx.Response(200, json={"daily": {"time": [day], "precipitation_sum": [rain[day]]}})

    races = [_race(2024, 8, date(2024, 5, 26)), _race(2023, 6, date(2023, 5, 28)), _race(2022, 7, date(2022, 5, 29))]
    assert wet_races(races, http=client(handler)) == {(2024, 8): False, (2023, 6): True}


# --- temperatura w chwili startu (model v2) ---
from datetime import datetime, timezone   # noqa: E402


def hourly_handler(request):
    assert "temperature_2m" in request.url.params.get("hourly", "")      # prosimy o dane godzinowe
    return httpx.Response(200, json=json.loads((FIX / "openmeteo_forecast_hourly.json").read_text()))


START = datetime(2026, 11, 21, 4, 0, tzinfo=timezone.utc)


def test_start_temperature_taken_from_the_start_hour():
    f = fetch_forecast(36.11, -115.17, date(2026, 11, 21), http=client(hourly_handler), today=TODAY, start_utc=START)
    assert f.start_temperature_c == pytest.approx(13.6)                  # 04:00 UTC w prawdziwych danych
    assert f.rain_probability >= 0                                      # reszta prognozy działa jak dotąd


def test_start_temperature_none_without_start_time():
    f = fetch_forecast(36.11, -115.17, date(2026, 11, 21), http=client(forecast_handler), today=TODAY)
    assert f.start_temperature_c is None


def test_forecast_still_works_when_hourly_missing():
    f = fetch_forecast(36.11, -115.17, date(2026, 11, 21), http=client(forecast_handler), today=TODAY, start_utc=START)
    assert f is not None and f.start_temperature_c is None               # odpowiedź bez sekcji godzinowej


def test_start_hour_outside_returned_range_gives_none():
    far = datetime(2026, 11, 25, 4, 0, tzinfo=timezone.utc)
    f = fetch_forecast(36.11, -115.17, date(2026, 11, 21), http=client(hourly_handler), today=TODAY, start_utc=far)
    assert f.start_temperature_c is None


def test_hourly_request_never_asks_beyond_the_16_day_horizon():
    seen = {}

    def handler(request):
        seen.update(dict(request.url.params))
        return httpx.Response(200, json=json.loads((FIX / "openmeteo_forecast.json").read_text()))

    race_day = date(2026, 11, 28)                        # dokładnie 16 dni od TODAY
    fetch_forecast(36.11, -115.17, race_day, http=client(handler), today=TODAY, start_utc=datetime(2026, 11, 28, 4, tzinfo=timezone.utc))
    assert date.fromisoformat(seen["end_date"]) <= date(2026, 11, 28)           # TODAY + 16


def local_handler(request):
    """Odpowiedź z timezone=auto dla Las Vegas: czas lokalny (UTC-8), więc start 04:00 UTC to 20:00 poprzedniego dnia."""
    assert request.url.params["timezone"] == "auto"
    return httpx.Response(200, json={
        "utc_offset_seconds": -28800,
        "daily": {"time": ["2026-11-20", "2026-11-21", "2026-11-22"],
                  "precipitation_probability_max": [10, 4, 70], "temperature_2m_max": [18.0, 11.1, 12.0]},
        "hourly": {"time": ["2026-11-20T19:00", "2026-11-20T20:00", "2026-11-20T21:00", "2026-11-21T04:00"],
                   "temperature_2m": [11.0, 9.0, 8.5, 99.0]},
    })


def test_start_temperature_is_taken_at_the_local_start_hour_not_utc_hour():
    f = fetch_forecast(36.11, -115.17, date(2026, 11, 21), http=client(local_handler), today=TODAY, start_utc=START)
    assert f.start_temperature_c == pytest.approx(9.0)          # 20:00 w Las Vegas, a nie 04:00 (99.0) ani żadna inna godzina
    assert f.start_local_time == "20:00"


def test_rain_and_daily_max_are_for_the_local_race_day():
    f = fetch_forecast(36.11, -115.17, date(2026, 11, 21), http=client(local_handler), today=TODAY, start_utc=START)
    assert f.rain_probability == pytest.approx(0.10) and f.temperature_c == pytest.approx(18.0)      # dzień 20.11 lokalnie
