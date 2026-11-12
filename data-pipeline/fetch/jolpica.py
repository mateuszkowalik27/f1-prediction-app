"""Klient Jolpica F1 API (następca Ergast): kalendarz, wyniki, klasyfikacje, historia torów."""
from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime
from pathlib import Path

import httpx

from schemas import (
    Calendar, DriverEntry, HistoricRace, HistoricResult, Race, Session, StandingRow, Standings,
)

BASE_URL = "https://api.jolpi.ca/ergast/f1"
PAGE_LIMIT = 100

# Klucze sesji w odpowiedzi API -> nasze nazwy
SESSION_KEYS = {
    "FirstPractice": "FP1",
    "SecondPractice": "FP2",
    "ThirdPractice": "FP3",
    "SprintQualifying": "SprintQualifying",
    "Sprint": "Sprint",
    "Qualifying": "Qualifying",
}


class JolpicaError(RuntimeError):
    """API Jolpica nie odpowiada poprawnie po kilku próbach."""


class NoResultsError(LookupError):
    """Wyścig jeszcze się nie odbył (albo został odwołany): brak wyników."""


def _utc(date_str: str, time_str: str | None) -> datetime | None:
    if not time_str:
        return None
    return datetime.fromisoformat(f"{date_str}T{time_str}".replace("Z", "+00:00"))


class JolpicaClient:
    """Klient z odstępem między zapytaniami (limit Jolpica: ~4/s i ~200/h) oraz cache'em na dysku.

    Cache obejmuje tylko zakończone sezony (rok < immutable_before): ich dane już się nie zmieniają.
    """

    def __init__(
        self, http: httpx.Client | None = None, retry_delay: float = 1.0, attempts: int = 3,
        min_interval: float = 0.3, cache_dir: Path | None = None, immutable_before: int | None = None,
        sleep=time.sleep,
    ):
        self._http = http or httpx.Client(timeout=30)
        self._retry_delay = retry_delay
        self._attempts = attempts
        self._min_interval = min_interval
        self._cache_dir = Path(cache_dir) if cache_dir else None
        self._immutable_before = immutable_before
        self._sleep = sleep
        self._last_request = 0.0

    # --- cache ---
    def _cache_file(self, path: str, params: dict | None) -> Path | None:
        if self._cache_dir is None or self._immutable_before is None:
            return None
        match = re.match(r"^/(\d{4})[/.]", path)
        if not match or int(match.group(1)) >= self._immutable_before:
            return None
        key = hashlib.sha1(f"{path}?{sorted((params or {}).items())}".encode()).hexdigest()[:16]
        return self._cache_dir / f"{path.strip('/').replace('/', '_')}_{key}.json"

    # --- niskopoziomowe pobieranie ---
    def _throttle(self) -> None:
        wait = self._min_interval - (time.monotonic() - self._last_request)
        if wait > 0:
            self._sleep(wait)
        self._last_request = time.monotonic()

    def _get(self, path: str, params: dict | None = None) -> dict:
        cached = self._cache_file(path, params)
        if cached is not None and cached.exists():
            return json.loads(cached.read_text())
        last: Exception | None = None
        for attempt in range(self._attempts):
            delay = self._retry_delay * (attempt + 1)
            try:
                self._throttle()
                resp = self._http.get(f"{BASE_URL}{path}", params=params)
                if resp.status_code >= 500 or resp.status_code == 429:
                    retry_after = resp.headers.get("Retry-After", "")
                    delay = float(retry_after) if retry_after.replace(".", "", 1).isdigit() else delay
                    raise httpx.HTTPStatusError("retryable", request=resp.request, response=resp)
                resp.raise_for_status()
                data = resp.json()["MRData"]
                if cached is not None:
                    cached.parent.mkdir(parents=True, exist_ok=True)
                    cached.write_text(json.dumps(data))
                return data
            except httpx.HTTPStatusError as exc:
                last = exc
                if exc.response.status_code < 500 and exc.response.status_code != 429:
                    break  # błąd 4xx nie ma sensu powtarzać
            except (httpx.HTTPError, KeyError, ValueError) as exc:
                last = exc
            if attempt < self._attempts - 1:
                self._sleep(delay)
        raise JolpicaError(f"Jolpica: {path} nie odpowiada ({last})")

    def _all_races(self, path: str) -> list[dict]:
        """Pobiera wszystkie strony i skleja wyścigi podzielone między stronami."""
        merged: dict[tuple[str, str], dict] = {}
        offset = 0
        while True:
            data = self._get(path, {"limit": PAGE_LIMIT, "offset": offset})
            for race in data["RaceTable"]["Races"]:
                key = (race["season"], race["round"])
                if key in merged:
                    merged[key].setdefault("Results", []).extend(race.get("Results", []))
                else:
                    merged[key] = race
            offset += PAGE_LIMIT
            if offset >= int(data["total"]):
                break
        return list(merged.values())

    # --- parsowanie ---
    @staticmethod
    def _to_race(raw: dict) -> Race:
        sessions = []
        for key, name in SESSION_KEYS.items():
            if key in raw:
                sessions.append(Session(name=name, start_utc=_utc(raw[key]["date"], raw[key].get("time"))))
        sessions.append(Session(name="Race", start_utc=_utc(raw["date"], raw.get("time"))))
        sessions.sort(key=lambda s: (s.start_utc is None, s.start_utc or datetime.max))
        loc = raw["Circuit"]["Location"]
        return Race(
            season=int(raw["season"]), round=int(raw["round"]), name=raw["raceName"],
            circuit_id=raw["Circuit"]["circuitId"], country=loc["country"],
            lat=float(loc["lat"]), lon=float(loc["long"]),
            sessions=sessions, is_sprint="Sprint" in raw,
        )

    @staticmethod
    def _to_historic(raw: dict) -> HistoricRace:
        loc = raw["Circuit"]["Location"]
        results = [
            HistoricResult(
                driver_id=r["Driver"]["driverId"],
                team_id=r["Constructor"]["constructorId"],
                grid=int(r["grid"]),
                finish=int(r["position"]) if r["positionText"].isdigit() else None,
                status=r["status"],
            )
            for r in raw.get("Results", [])
        ]
        return HistoricRace(
            season=int(raw["season"]), round=int(raw["round"]), circuit_id=raw["Circuit"]["circuitId"],
            date=raw["date"], lat=float(loc["lat"]), lon=float(loc["long"]), results=results,
        )

    # --- publiczne API ---
    def calendar(self, season: int) -> list[Race]:
        data = self._get(f"/{season}.json", {"limit": PAGE_LIMIT})
        return [self._to_race(r) for r in data["RaceTable"]["Races"]]

    def entries(self, season: int) -> list[DriverEntry]:
        lists = self._get(f"/{season}/driverstandings.json", {"limit": PAGE_LIMIT})["StandingsTable"]["StandingsLists"]
        if not lists:
            return []
        return [
            DriverEntry(
                driver_id=row["Driver"]["driverId"], code=row["Driver"]["code"],
                name=f'{row["Driver"]["givenName"]} {row["Driver"]["familyName"]}',
                team_id=row["Constructors"][-1]["constructorId"],
            )
            for row in lists[0]["DriverStandings"]
        ]

    def standings(self, season: int) -> Standings:
        d = self._get(f"/{season}/driverstandings.json", {"limit": PAGE_LIMIT})["StandingsTable"]["StandingsLists"]
        c = self._get(f"/{season}/constructorstandings.json", {"limit": PAGE_LIMIT})["StandingsTable"]["StandingsLists"]
        drivers = [
            StandingRow(
                id=r["Driver"]["driverId"], name=f'{r["Driver"]["givenName"]} {r["Driver"]["familyName"]}',
                points=float(r["points"]), wins=int(r["wins"]), position=int(r["position"]),
            )
            for r in (d[0]["DriverStandings"] if d else [])
        ]
        constructors = [
            StandingRow(
                id=r["Constructor"]["constructorId"], name=r["Constructor"]["name"],
                points=float(r["points"]), wins=int(r["wins"]), position=int(r["position"]),
            )
            for r in (c[0]["ConstructorStandings"] if c else [])
        ]
        return Standings(drivers=drivers, constructors=constructors)

    def race_results(self, season: int, round: int) -> HistoricRace:
        races = self._all_races(f"/{season}/{round}/results.json")
        if not races or not races[0].get("Results"):
            raise NoResultsError(f"brak wyników: {season} runda {round}")
        return self._to_historic(races[0])

    def qualifying_grid(self, season: int, round: int) -> dict[str, int] | None:
        """driver_id -> pozycja w kwalifikacjach albo None, gdy kwalifikacje jeszcze się nie odbyły."""
        data = self._get(f"/{season}/{round}/qualifying.json", {"limit": PAGE_LIMIT})
        races = data["RaceTable"]["Races"]
        if not races or not races[0].get("QualifyingResults"):
            return None
        return {r["Driver"]["driverId"]: int(r["position"]) for r in races[0]["QualifyingResults"]}

    def season_results(self, season: int, up_to_round: int) -> list[HistoricRace]:
        races = [self._to_historic(r) for r in self._all_races(f"/{season}/results.json")]
        return sorted((r for r in races if r.round <= up_to_round), key=lambda r: r.round)

    def circuit_history(self, circuit_id: str, seasons: list[int]) -> list[HistoricRace]:
        history: list[HistoricRace] = []
        for season in seasons:
            for raw in self._all_races(f"/{season}/circuits/{circuit_id}/results.json"):
                history.append(self._to_historic(raw))
        return history
