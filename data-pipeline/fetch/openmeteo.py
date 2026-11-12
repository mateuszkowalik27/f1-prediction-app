"""Open-Meteo: prognoza pogody na dzień wyścigu i archiwalne opady (do wykrywania mokrych wyścigów)."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import httpx

import config
from schemas import HistoricRace, WeatherForecast

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_HORIZON_DAYS = 16


def _client(http: httpx.Client | None) -> httpx.Client:
    return http or httpx.Client(timeout=30)


def _local_start(data: dict, start_utc: datetime) -> datetime:
    """Godzina startu w czasie lokalnym toru (odpowiedź z timezone=auto podaje przesunięcie względem UTC)."""
    offset = int(data.get("utc_offset_seconds") or 0)
    return start_utc.astimezone(timezone.utc).replace(tzinfo=None) + timedelta(seconds=offset)


def _start_temperature(data: dict, local_start: datetime | None) -> float | None:
    """Temperatura powietrza z prognozy godzinowej dla pełnej godziny startu (czas lokalny); brak sekcji lub godziny -> None."""
    if local_start is None:
        return None
    try:
        hourly = data["hourly"]
        value = hourly["temperature_2m"][hourly["time"].index(local_start.strftime("%Y-%m-%dT%H:00"))]
        return None if value is None else float(value)
    except (KeyError, ValueError, IndexError, TypeError):
        return None


def fetch_forecast(
    lat: float, lon: float, race_date: date,
    http: httpx.Client | None = None, today: date | None = None, start_utc: datetime | None = None,
) -> WeatherForecast | None:
    """Prognoza na dzień wyścigu albo None (za daleko w przyszłości, w przeszłości lub błąd API)."""
    today = today or datetime.now(timezone.utc).date()
    days_ahead = (race_date - today).days
    if days_ahead < 0 or days_ahead > FORECAST_HORIZON_DAYS:
        return None
    params = {
        "latitude": lat, "longitude": lon, "timezone": "auto" if start_utc is not None else "UTC",   # auto: czas lokalny toru
        "daily": "precipitation_probability_max,temperature_2m_max",
        "start_date": race_date.isoformat(), "end_date": race_date.isoformat(),
    }
    if start_utc is not None:
        params["hourly"] = "temperature_2m"
        params["start_date"] = (race_date - timedelta(days=1)).isoformat()   # zapas: godzina startu bywa już nazajutrz w UTC
        params["end_date"] = min(race_date + timedelta(days=1), today + timedelta(days=FORECAST_HORIZON_DAYS)).isoformat()
    try:
        resp = _client(http).get(FORECAST_URL, params=params)
        resp.raise_for_status()
        data = resp.json()
        daily = data["daily"]
        local_start = _local_start(data, start_utc) if start_utc is not None else None
        day = local_start.date() if local_start is not None else race_date      # dzień wyścigu u siebie, nie w UTC
        if day.isoformat() not in daily["time"]:
            day = race_date
        i = daily["time"].index(day.isoformat())
        rain = daily["precipitation_probability_max"][i]
        temp = daily["temperature_2m_max"][i]
        if rain is None or temp is None:
            return None
        return WeatherForecast(
            rain_probability=rain / 100, temperature_c=temp, fetched_at=datetime.now(timezone.utc),
            start_temperature_c=_start_temperature(data, local_start),
            start_local_time=local_start.strftime("%H:%M") if local_start is not None else None,
        )
    except (httpx.HTTPError, KeyError, ValueError, IndexError):
        return None


def fetch_historical_rain_mm(
    lat: float, lon: float, day: date, http: httpx.Client | None = None,
) -> float | None:
    """Suma opadów (mm) w danym dniu albo None, gdy brak danych."""
    params = {
        "latitude": lat, "longitude": lon, "timezone": "UTC", "daily": "precipitation_sum",
        "start_date": day.isoformat(), "end_date": day.isoformat(),
    }
    try:
        resp = _client(http).get(ARCHIVE_URL, params=params)
        resp.raise_for_status()
        daily = resp.json()["daily"]
        value = daily["precipitation_sum"][daily["time"].index(day.isoformat())]
        return None if value is None else float(value)
    except (httpx.HTTPError, KeyError, ValueError, IndexError):
        return None


def wet_races(races: list[HistoricRace], http: httpx.Client | None = None) -> dict[tuple[int, int], bool]:
    """(sezon, runda) -> czy wyścig był mokry. Wyścigi bez danych o pogodzie są pomijane."""
    http = _client(http)
    result: dict[tuple[int, int], bool] = {}
    for race in races:
        mm = fetch_historical_rain_mm(race.lat, race.lon, race.date, http=http)
        if mm is not None:
            result[(race.season, race.round)] = mm >= config.WET_RACE_MM
    return result
