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
