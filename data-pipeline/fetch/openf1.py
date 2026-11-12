"""Klient OpenF1 (nieoficjalne, darmowe API): treningi, opony, safety car, telemetria.

Każda metoda publiczna zwraca None, gdy danych brak albo API zawiodło: ten klient jest opcjonalny,
a czynniki od niego zależne po prostu się wtedy wyłączają.
"""
from __future__ import annotations

import statistics
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from urllib.parse import quote

import httpx

from schemas import (
    DriverEntry, HistoricRace, LapRecord, PracticeData, Race, SafetyEvent, SessionRow, SessionTable, TyreHistory,
    WeatherSample,
)

BASE_URL = "https://api.openf1.org/v1"
SLOW_LAP_RATIO = 1.07          # okrążenia wolniejsze niż 107% najlepszego w sesji są odrzucane
MIN_SPEED_SAMPLES = 50
DRY_COMPOUNDS = {"SOFT", "MEDIUM", "HARD"}
BEST_LAP_SESSIONS = {"Practice 1": "FP1", "Practice 2": "FP2", "Practice 3": "FP3",
                     "Sprint Qualifying": "SprintQualifying", "Sprint Shootout": "SprintQualifying"}


class OpenF1Unavailable(RuntimeError):
    pass


def _race_day(race: Race) -> date | None:
    for s in race.sessions:
        if s.name == "Race" and s.start_utc:
            return s.start_utc.date()
    known = [s.start_utc for s in race.sessions if s.start_utc]
    return max(known).date() if known else None


def _compound_at(stints: list[dict], driver_number: int, lap_number: int) -> str | None:
    for st in stints:
        if st.get("driver_number") != driver_number:
            continue
        end = st.get("lap_end") or 10_000  # 0/None = stint jeszcze trwa
        if st["lap_start"] <= lap_number <= end:
            return st.get("compound")
    return None


class OpenF1Client:
    def __init__(self, http: httpx.Client | None = None, min_interval: float = 0.5, sleep=time.sleep):
        self._http = http or httpx.Client(timeout=60)
        self._min_interval = min_interval  # API: maks. 3 zapytania na sekundę
        self._sleep = sleep
        self._last = 0.0
        self.errors = 0   # ile razy źródło zawiodło (nie: brak danych); pozwala odróżnić awarię od legalnej pustki

    def _get(self, path: str, query: dict) -> list[dict]:
        qs = "&".join(f"{k}={quote(str(v), safe=':-')}" for k, v in query.items())
        url = f"{BASE_URL}{path}?{qs}"
        for attempt in range(5):
            wait = self._min_interval - (time.monotonic() - self._last)
            if wait > 0:
                self._sleep(wait)
            self._last = time.monotonic()
            resp = self._http.get(url)
            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After", "")
                wait_s = float(retry_after) if retry_after.replace(".", "", 1).isdigit() else 2.0 * (attempt + 1)
                self._sleep(min(wait_s, 30.0))      # słuchamy serwera, ale nie czekamy dłużej niż pół minuty
                continue
            if resp.status_code == 404:
                return []  # OpenF1 zwraca 404 "No results found" zamiast pustej listy
            if resp.status_code >= 400:
                raise OpenF1Unavailable(f"{path}: HTTP {resp.status_code}")
            return resp.json()
        raise OpenF1Unavailable(f"{path}: limit zapytań")

    def _sessions(self, day: date, before: int = 3, after: int = 1) -> list[dict]:
        lo, hi = day - timedelta(days=before), day + timedelta(days=after)
        rows = self._get("/sessions", {"date_start>": lo.isoformat(), "date_start<": (hi + timedelta(days=1)).isoformat()})
        return [r for r in rows if lo <= datetime.fromisoformat(r["date_start"]).date() <= hi]

    # --- publiczne API ---
    def practice_pace(self, race: Race, entries: list[DriverEntry]) -> PracticeData | None:
        try:
            day = _race_day(race)
            if day is None:
                return None
            sessions = [s for s in self._sessions(day) if s["session_name"].startswith("Practice")]
            code_to_id = {e.code: e.driver_id for e in entries}
            laps_by: dict[tuple[str, str], list[float]] = defaultdict(list)
            for s in sessions:
                key = s["session_key"]
                num_to_id = {d["driver_number"]: code_to_id.get(d["name_acronym"])
                             for d in self._get("/drivers", {"session_key": key})}
                stints = self._get("/stints", {"session_key": key})
                valid = [l for l in self._get("/laps", {"session_key": key})
                         if l.get("lap_duration") and not l.get("is_pit_out_lap")]
                if not valid:
                    continue
                best = min(l["lap_duration"] for l in valid)
                for l in valid:
                    if l["lap_duration"] > best * SLOW_LAP_RATIO:
                        continue
                    driver_id = num_to_id.get(l["driver_number"])
                    compound = _compound_at(stints, l["driver_number"], l["lap_number"])
                    if driver_id and compound:
                        laps_by[(driver_id, compound)].append(l["lap_duration"])
            runs: dict[str, list[tuple[str, float]]] = {}
            for (driver_id, compound), durations in laps_by.items():
                runs.setdefault(driver_id, []).append((compound, statistics.median(sorted(durations)[:3])))
            return PracticeData(best_runs=runs) if runs else None
        except (OpenF1Unavailable, httpx.HTTPError, KeyError, ValueError):
            self.errors += 1
            return None

    def _race_sessions(self, races: list[HistoricRace]):
        """Dla każdego dawnego wyścigu (od 2023) zwraca (wyścig, klucz sesji wyścigu)."""
        for r in races:
            if r.season < 2023:
                continue  # OpenF1 ma dane dopiero od 2023
            try:
                found = [s for s in self._sessions(r.date, before=0, after=0) if s["session_name"] == "Race"]
            except (OpenF1Unavailable, httpx.HTTPError, KeyError, ValueError):
                self.errors += 1
                continue
            if found:
                yield r, found[0]["session_key"]

    def safety_events(self, circuit_id: str, races: list[HistoricRace]) -> dict[int, list[SafetyEvent]] | None:
        out: dict[int, list[SafetyEvent]] = {}
        for r, key in self._race_sessions(races):
            try:
                rows = self._get("/race_control", {"session_key": key, "category": "SafetyCar"})
            except (OpenF1Unavailable, httpx.HTTPError, ValueError):
                self.errors += 1
                continue
            events = out.setdefault(r.season, [])
            for row in rows:
                text = row.get("message", "").upper()
                kind = "VSC" if "VIRTUAL SAFETY CAR DEPLOYED" in text else "SC" if "SAFETY CAR DEPLOYED" in text else None
                if kind:
                    events.append(SafetyEvent(season=r.season, kind=kind, lap=row.get("lap_number") or 0))
        return out or None

    def tyre_history(self, circuit_id: str, races: list[HistoricRace]) -> TyreHistory | None:
        stops: list[int] = []
        compounds: Counter[str] = Counter()
        for _, key in self._race_sessions(races):
            try:
                stints = self._get("/stints", {"session_key": key})
            except (OpenF1Unavailable, httpx.HTTPError, ValueError):
                self.errors += 1
                continue
            per_driver: dict[int, int] = {}
            for st in stints:
                per_driver[st["driver_number"]] = max(per_driver.get(st["driver_number"], 0), st["stint_number"])
                if st.get("compound") in DRY_COMPOUNDS:
                    compounds[st["compound"]] += 1
            stops.extend(n - 1 for n in per_driver.values())
        if not stops:
            return None
        return TyreHistory(
            median_stops=max(1, round(statistics.median(stops))),
            dominant_compounds=[c for c, _ in compounds.most_common(3)],
        )

    def speed_trace(self, race: Race) -> list[float] | None:
        try:
            day = _race_day(race)
            if day is None:
                return None
            sessions = self._sessions(day)
            chosen = ([s for s in sessions if s["session_name"] == "Qualifying"]
                      or [s for s in sessions if s["session_name"] == "Race"])
            if not chosen:
                return None
            key = chosen[0]["session_key"]
            valid = [l for l in self._get("/laps", {"session_key": key})
                     if l.get("lap_duration") and not l.get("is_pit_out_lap") and l.get("date_start")]
            if not valid:
                return None
            fastest = min(valid, key=lambda l: l["lap_duration"])
            start = datetime.fromisoformat(fastest["date_start"])
            end = start + timedelta(seconds=fastest["lap_duration"])
            rows = self._get("/car_data", {"session_key": key, "driver_number": fastest["driver_number"],
                                           "date>": start.isoformat(), "date<": end.isoformat()})
            speeds = [float(r["speed"]) for r in sorted(rows, key=lambda r: r["date"])]
            return speeds if len(speeds) >= MIN_SPEED_SAMPLES else None
        except (OpenF1Unavailable, httpx.HTTPError, KeyError, ValueError):
            self.errors += 1
            return None

    # --- model v2: okrążenia wyścigu i pogoda ---
    def _race_session_key(self, race: Race) -> int | None:
        day = _race_day(race)
        if day is None:
            return None
        found = [s for s in self._sessions(day, before=0, after=0) if s["session_name"] == "Race"]
        return found[0]["session_key"] if found else None

    def race_laps(self, race: Race, entries: list[DriverEntry]) -> list[LapRecord] | None:
        """Okrążenia sesji Race z mieszanką i wiekiem opon (z /stints). Brak danych lub błąd -> None."""
        try:
            key = self._race_session_key(race)
            if key is None:
                return None
            code_to_id = {e.code: e.driver_id for e in entries}
            num_to_id = {d["driver_number"]: code_to_id.get(d["name_acronym"])
                         for d in self._get("/drivers", {"session_key": key})}
            stints: dict[int, list[dict]] = defaultdict(list)
            for st in self._get("/stints", {"session_key": key}):
                stints[st["driver_number"]].append(st)
            records = []
            for row in self._get("/laps", {"session_key": key}):
                driver_id = num_to_id.get(row.get("driver_number"))
                if not driver_id:
                    continue
                compound = tyre_age = None
                for st in stints.get(row["driver_number"], []):
                    end = st.get("lap_end") or 10_000   # 0/None = stint jeszcze trwa
                    if st["lap_start"] <= row["lap_number"] <= end:
                        compound = st.get("compound")
                        tyre_age = (st.get("tyre_age_at_start") or 0) + (row["lap_number"] - st["lap_start"])
                        break
                records.append(LapRecord(
                    driver_id=driver_id, lap=row["lap_number"], duration_s=row.get("lap_duration"),
                    is_pit_out=bool(row.get("is_pit_out_lap")), compound=compound, tyre_age=tyre_age,
                ))
            return records or None
        except (OpenF1Unavailable, httpx.HTTPError, KeyError, ValueError, TypeError):
            self.errors += 1
            return None

    def race_weather(self, race: Race) -> WeatherSample | None:
        """Mediana temperatury powietrza i toru w trakcie sesji Race albo None."""
        try:
            key = self._race_session_key(race)
            if key is None:
                return None
            rows = self._get("/weather", {"session_key": key})
            air = [r["air_temperature"] for r in rows if r.get("air_temperature") is not None]
            track = [r["track_temperature"] for r in rows if r.get("track_temperature") is not None]
            if not air:
                return None
            return WeatherSample(air_c=statistics.median(air), track_c=statistics.median(track) if track else None)
        except (OpenF1Unavailable, httpx.HTTPError, KeyError, ValueError, TypeError):
            self.errors += 1
            return None

    def starting_grid(self, race: Race, entries: list[DriverEntry]) -> dict[str, int] | None:
        """Oficjalna siatka startowa Z KARAMI (driver_id -> pozycja). W OpenF1 kluczem jest sesja KWALIFIKACJI.
        Brak danych, błąd albo brak sesji -> None."""
        try:
            day = _race_day(race)
            if day is None:
                return None
            qualifying = [s for s in self._sessions(day) if s["session_name"] == "Qualifying"]
            if not qualifying:
                return None
            key = qualifying[-1]["session_key"]
            rows = self._get("/starting_grid", {"session_key": key})
            if not rows:
                return None
            code_to_id = {e.code: e.driver_id for e in entries}
            num_to_id = {d["driver_number"]: code_to_id.get(d["name_acronym"])
                         for d in self._get("/drivers", {"session_key": key})}
            grid = {num_to_id[r["driver_number"]]: int(r["position"])
                    for r in rows if num_to_id.get(r.get("driver_number"))}
            return grid or None
        except (OpenF1Unavailable, httpx.HTTPError, KeyError, ValueError, TypeError):
            self.errors += 1
            return None

    # --- wyniki sesji: najlepsze okrążenia z treningów i sprint-kwalifikacji ---
    def best_laps(self, race: Race, entries: list[DriverEntry]) -> dict[str, SessionTable] | None:
        """Tabele (kierowca -> najlepsze okrążenie, od najszybszego) dla treningów i sprint-kwalifikacji weekendu.
        Brak danych lub błąd -> None; sesja bez żadnego czasu jest pomijana."""
        try:
            day = _race_day(race)
            if day is None:
                return None
            code_to_id = {e.code: e.driver_id for e in entries}
            out: dict[str, SessionTable] = {}
            for s in self._sessions(day):
                name = BEST_LAP_SESSIONS.get(s["session_name"])
                if not name:
                    continue
                key = s["session_key"]
                num_to_id = {d["driver_number"]: code_to_id.get(d["name_acronym"])
                             for d in self._get("/drivers", {"session_key": key})}
                best: dict[str, float] = {}
                for lap in self._get("/laps", {"session_key": key}):
                    driver_id, duration = num_to_id.get(lap.get("driver_number")), lap.get("lap_duration")
                    if driver_id and duration and duration < best.get(driver_id, float("inf")):
                        best[driver_id] = float(duration)
                if best:
                    ranked = sorted(best.items(), key=lambda kv: kv[1])
                    out[name] = SessionTable(kind="practice", rows=[
                        SessionRow(driver_id=d, position=i + 1, best_s=t) for i, (d, t) in enumerate(ranked)])
            return out or None
        except (OpenF1Unavailable, httpx.HTTPError, KeyError, ValueError, TypeError):
            self.errors += 1
            return None
