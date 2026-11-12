"""Atrapy źródeł danych: sezon 2027 (rundy 1-3) z poprzednim sezonem 2026."""
from datetime import datetime, timezone

from fetch.jolpica import JolpicaError
from helpers import hist_race, make_entries
from run import Clients
from schemas import PitStop, QualiTimes, Race, Session, StandingRow, Standings, WeatherForecast

UTC = timezone.utc

NOW = datetime(2027, 4, 1, 12, 0, tzinfo=UTC)          # po rundach 1-2, przed rundą 3
ROWS = [("d1", "t1", 1), ("d2", "t1", 2), ("d3", "t2", None), ("d4", "t2", 4)]
ENTRIES = make_entries(("d1", "t1"), ("d2", "t1"), ("d3", "t2"), ("d4", "t2"))


def mk_race(rnd, month, day, circuit=None):
    start = datetime(2027, month, day, 13, 0, tzinfo=UTC)
    return Race(season=2027, round=rnd, name=f"GP{rnd}", circuit_id=circuit or f"c{rnd}", country="X",
                lat=1.0, lon=2.0, is_sprint=False, sessions=[
                    Session(name="Qualifying", start_utc=start.replace(day=day - 1)),
                    Session(name="Race", start_utc=start)])


CALENDAR = [mk_race(1, 3, 14), mk_race(2, 3, 28), mk_race(3, 4, 11)]


class FakeJolpica:
    def __init__(self, fail=False, grid=None, with_history=True, empty_round=None, extra_entry=False,
                 completed=2, entries_current=True, empty_standings=False, fail_results=False, quali_entries=None,
                 fail_quali_times=False):
        self.fail, self.grid, self.with_history, self.empty_round = fail, grid, with_history, empty_round
        self.extra_entry = extra_entry
        self.completed = completed
        self.entries_current, self.empty_standings = entries_current, empty_standings
        self.fail_results, self.quali_entries = fail_results, quali_entries
        self.fail_quali_times = fail_quali_times

    def calendar(self, season):
        if self.fail:
            raise JolpicaError("awaria")
        return CALENDAR

    def standings(self, season):
        if self.empty_standings and season == 2027:
            return Standings(drivers=[], constructors=[])
        row = StandingRow(id="d1", name="D1", points=43, wins=1, position=1)
        return Standings(drivers=[row], constructors=[row.model_copy(update={"id": "t1"})])

    def entries(self, season):
        if season == 2026 and not self.entries_current:
            return ENTRIES                      # początek sezonu: klasyfikacja nowego roku jeszcze pusta
        if season != 2027 or not self.entries_current:
            return []
        return ENTRIES + make_entries(("gone", "t9")) if self.extra_entry else ENTRIES

    def season_results(self, season, up_to_round):
        if self.fail_results and up_to_round == 9999:        # tylko przygotowanie testu wstecznego
            raise JolpicaError("awaria przy ocenie")
        if not self.with_history:
            return []
        if season == 2026:
            return [hist_race(2026, r, ROWS, circuit_id=f"p{r}") for r in (23, 24)]
        if season != 2027:
            return []
        races = [hist_race(2027, r, ROWS, circuit_id=f"c{r}") for r in range(1, self.completed + 1) if r <= up_to_round]
        if self.empty_round:
            races.append(hist_race(2027, self.empty_round, [], circuit_id="cancelled"))
        return races

    def circuit_history(self, circuit_id, seasons):
        if not self.with_history:
            return []
        return [hist_race(y, 3, ROWS, circuit_id=circuit_id) for y in (2024, 2025)]

    def qualifying_grid(self, season, round):
        return self.grid

    def qualifying_times(self, season, round):
        if self.fail_quali_times:
            raise JolpicaError("awaria czasów kwalifikacji")
        return [QualiTimes(driver_id="d1", q1=80.0, q2=79.0, q3=78.0), QualiTimes(driver_id="d2", q1=80.4, q2=79.5, q3=78.6),
                QualiTimes(driver_id="d3", q1=80.8, q2=79.9), QualiTimes(driver_id="d4", q1=81.5)]

    def pit_stops(self, season, round):
        return [PitStop(driver_id=d, lap=10 + i, duration_s=s)
                for i, (d, s) in enumerate([("d1", 23.0), ("d2", 23.4), ("d3", 25.0), ("d4", 25.4)])]

    def qualifying_result(self, season, round):
        if not self.grid:
            return None
        entries = self.quali_entries or [e for e in ENTRIES if e.driver_id in self.grid]
        return self.grid, entries


class FakeOpenF1:
    def __init__(self, practice=None, broken=False, laps=None, weather=None, grid=None):
        self.practice = practice
        self.broken = broken
        self.laps, self.weather, self.grid = laps, weather, grid
        self.trace_requests = []
        self.calls = []                       # nazwy wywołanych nowych metod (model v2)

    def race_laps(self, race, entries):
        self.calls.append("race_laps")
        if self.broken:
            raise KeyError("lap_duration")
        return self.laps

    def race_weather(self, race):
        self.calls.append("race_weather")
        if self.broken:
            raise KeyError("air_temperature")
        return self.weather

    def starting_grid(self, race, entries):
        self.calls.append("starting_grid")
        if self.broken:
            raise KeyError("position")
        return self.grid

    def practice_pace(self, race, entries):
        if self.broken:
            raise KeyError("stint_number")     # zepsuta odpowiedź OpenF1
        return self.practice

    def safety_events(self, circuit_id, races):
        return None

    def tyre_history(self, circuit_id, races):
        return None

    def speed_trace(self, race):
        self.trace_requests.append(race)
        return None


def forecast(lat, lon, day):
    return WeatherForecast(rain_probability=0.1, temperature_c=20.0, fetched_at=NOW)


def clients(**kw):
    openf1 = kw.pop("openf1", FakeOpenF1())
    return Clients(jolpica=FakeJolpica(**kw), openf1=openf1, forecast=forecast,
                   wet=lambda races: {(h.season, h.round): False for h in races})
