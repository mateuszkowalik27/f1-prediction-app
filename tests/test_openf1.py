from datetime import date, datetime, timezone
from urllib.parse import unquote

import httpx

from fetch.openf1 import OpenF1Client
from schemas import DriverEntry, HistoricRace, Race, SafetyEvent, Session

UTC = timezone.utc


def sess(key, name, day):
    return {"session_key": key, "session_name": name, "date_start": f"{day}T13:00:00+00:00"}


def make_client(routes, log=None):
    """routes: {ścieżka: callable(query: str) -> (status, data)}"""

    def handler(request: httpx.Request) -> httpx.Response:
        query = unquote(request.url.query.decode())
        if log is not None:
            log.append(query)
        path = request.url.path.removeprefix("/v1")
        status, data = routes[path](query) if path in routes else (404, {"detail": "No results found."})
        return httpx.Response(status, json=data)

    return OpenF1Client(http=httpx.Client(transport=httpx.MockTransport(handler)),
                        min_interval=0, sleep=lambda s: None)


def race(day=datetime(2024, 5, 26, 13, 0, tzinfo=UTC)):
    return Race(season=2024, round=8, name="Monaco GP", circuit_id="monaco", country="Monaco",
                lat=0.0, lon=0.0, is_sprint=False, sessions=[Session(name="Race", start_utc=day)])


ENTRIES = [
    DriverEntry(driver_id="leclerc", code="LEC", name="Charles Leclerc", team_id="ferrari"),
    DriverEntry(driver_id="max_verstappen", code="VER", name="Max Verstappen", team_id="red_bull"),
]


def lap(num, number, dur, pit_out=False):
    return {"driver_number": number, "lap_number": num, "lap_duration": dur,
            "is_pit_out_lap": pit_out, "date_start": "2024-05-24T15:00:00+00:00"}


def practice_routes():
    return {
        "/sessions": lambda q: (200, [sess(1, "Practice 1", "2024-05-24"), sess(9, "Race", "2024-05-26")]),
        "/drivers": lambda q: (200, [{"driver_number": 16, "name_acronym": "LEC"},
                                     {"driver_number": 1, "name_acronym": "VER"}]),
        "/stints": lambda q: (200, [
            {"driver_number": 16, "stint_number": 1, "lap_start": 1, "lap_end": 5, "compound": "SOFT"},
            {"driver_number": 1, "stint_number": 1, "lap_start": 1, "lap_end": 5, "compound": "MEDIUM"}]),
        "/laps": lambda q: (200, [
            lap(1, 16, 123.5, pit_out=True), lap(2, 16, 80.5), lap(3, 16, 80.2), lap(4, 16, 80.9), lap(5, 16, 81.0),
            lap(1, 1, 123.9, pit_out=True), lap(2, 1, 81.0), lap(3, 1, 81.2), lap(4, 1, 81.1), lap(5, 1, 81.5)]),
    }


def test_practice_pace_maps_codes_to_driver_ids():
    data = make_client(practice_routes()).practice_pace(race(), ENTRIES)
    assert data.best_runs["leclerc"] == [("SOFT", 80.5)]            # mediana 3 najszybszych: 80.2, 80.5, 80.9
    assert data.best_runs["max_verstappen"] == [("MEDIUM", 81.1)]   # okrążenie wyjazdowe z boksu pominięte


def test_returns_none_on_http_error():
    c = make_client({"/sessions": lambda q: (500, {})})
    assert c.practice_pace(race(), ENTRIES) is None
    assert c.speed_trace(race()) is None


def test_returns_none_when_no_matching_session():
    c = make_client({})  # wszystko zwraca 404 "No results found"
    assert c.practice_pace(race(), ENTRIES) is None


def test_retries_after_rate_limit():
    routes = practice_routes()
    original = routes["/sessions"]
    calls = []

    def limited(q):
        calls.append(1)
        return (429, {"detail": "Rate limit exceeded"}) if len(calls) == 1 else original(q)

    routes["/sessions"] = limited
    assert make_client(routes).practice_pace(race(), ENTRIES) is not None
    assert len(calls) == 2


def history(season, day):
    return HistoricRace(season=season, round=6, circuit_id="monaco", date=day, lat=0.0, lon=0.0, results=[])


def test_safety_events_grouped_by_season():
    def sessions(q):
        if "2023-" in q:
            return 200, [sess(9001, "Race", "2023-05-28")]
        if "2024-" in q:
            return 200, [sess(9002, "Race", "2024-05-26")]
        return 404, {"detail": "No results found."}

    def race_control(q):
        if "session_key=9001" in q:
            return 200, [{"category": "SafetyCar", "message": "SAFETY CAR DEPLOYED", "lap_number": 12},
                         {"category": "SafetyCar", "message": "VIRTUAL SAFETY CAR DEPLOYED", "lap_number": 30}]
        return 404, {"detail": "No results found."}  # sesja istnieje, ale bez zdarzeń SC

    c = make_client({"/sessions": sessions, "/race_control": race_control})
    result = c.safety_events("monaco", [history(2022, date(2022, 5, 29)), history(2023, date(2023, 5, 28)),
                                        history(2024, date(2024, 5, 26))])
    assert result == {
        2023: [SafetyEvent(season=2023, kind="SC", lap=12), SafetyEvent(season=2023, kind="VSC", lap=30)],
        2024: [],
    }


def test_speed_trace_returns_samples_in_order():
    log = []
    laps = [
        {"driver_number": 16, "lap_number": 3, "lap_duration": 80.0, "is_pit_out_lap": False,
         "date_start": "2024-05-25T14:10:00+00:00"},
        {"driver_number": 1, "lap_number": 4, "lap_duration": 80.4, "is_pit_out_lap": False,
         "date_start": "2024-05-25T14:20:00+00:00"},
    ]
    rows = [{"date": f"2024-05-25T14:10:{i:02d}.000000+00:00", "speed": 100 + i} for i in range(60)]
    c = make_client({
        "/sessions": lambda q: (200, [sess(5, "Qualifying", "2024-05-25")]),
        "/laps": lambda q: (200, laps),
        "/car_data": lambda q: (200, list(reversed(rows))),
    }, log)
    trace = c.speed_trace(race())
    assert trace == [float(100 + i) for i in range(60)]
    assert any("driver_number=16" in q for q in log)  # najszybsze okrążenie: kierowca nr 16


def test_tyre_history_median_stops_and_compounds():
    def stint(number, n, compound):
        return {"driver_number": number, "stint_number": n, "compound": compound}

    stints = [stint(1, 1, "MEDIUM"), stint(1, 2, "HARD"),
              stint(4, 1, "MEDIUM"), stint(4, 2, "HARD"),
              stint(44, 1, "SOFT"), stint(44, 2, "MEDIUM"), stint(44, 3, "HARD")]
    c = make_client({
        "/sessions": lambda q: (200, [sess(9, "Race", "2024-05-26")]),
        "/stints": lambda q: (200, stints),
    })
    th = c.tyre_history("monaco", [history(2024, date(2024, 5, 26))])
    assert th.median_stops == 1
    assert sorted(th.dominant_compounds[:2]) == ["HARD", "MEDIUM"]


# --- okrążenia wyścigu i pogoda (model v2) ---
def stint(num, n, start, end, compound, age):
    return {"driver_number": num, "stint_number": n, "lap_start": start, "lap_end": end, "compound": compound,
            "tyre_age_at_start": age}


def race_lap_routes(laps=None, stints=None):
    return {
        "/sessions": lambda q: (200, [sess(9, "Race", "2024-05-26"), sess(5, "Qualifying", "2024-05-25")]),
        "/drivers": lambda q: (200, [{"driver_number": 16, "name_acronym": "LEC"},
                                     {"driver_number": 1, "name_acronym": "VER"},
                                     {"driver_number": 99, "name_acronym": "XXX"}]),
        "/stints": lambda q: (200, stints if stints is not None else [
            stint(16, 1, 1, 10, "MEDIUM", 0), stint(16, 2, 11, 0, "HARD", 2), stint(1, 1, 1, 0, "SOFT", 1)]),
        "/laps": lambda q: (200, laps if laps is not None else [
            lap(9, 16, 91.0), lap(12, 16, 90.5), lap(1, 16, 100.0, pit_out=False), lap(3, 1, 92.0),
            lap(4, 99, 93.0)]),
    }


def test_race_laps_join_stint_compound_and_tyre_age():
    records = make_client(race_lap_routes()).race_laps(race(), ENTRIES)
    by = {(r.driver_id, r.lap): r for r in records}
    assert (by[("leclerc", 9)].compound, by[("leclerc", 9)].tyre_age) == ("MEDIUM", 8)     # 0 + (9 - 1)
    assert (by[("leclerc", 12)].compound, by[("leclerc", 12)].tyre_age) == ("HARD", 3)     # 2 + (12 - 11); lap_end 0 = trwa
    assert (by[("max_verstappen", 3)].compound, by[("max_verstappen", 3)].tyre_age) == ("SOFT", 3)


def test_race_laps_maps_codes_to_driver_ids_and_skips_unknown_drivers():
    records = make_client(race_lap_routes()).race_laps(race(), ENTRIES)
    assert {r.driver_id for r in records} == {"leclerc", "max_verstappen"}   # kod XXX nie ma wpisu
    assert all(isinstance(r.duration_s, float) for r in records)


def test_race_laps_none_on_http_error():
    assert make_client({"/sessions": lambda q: (500, {})}).race_laps(race(), ENTRIES) is None


def test_race_laps_none_without_race_session():
    routes = race_lap_routes()
    routes["/sessions"] = lambda q: (200, [sess(5, "Qualifying", "2024-05-25")])
    assert make_client(routes).race_laps(race(), ENTRIES) is None


def weather_rows(airs, tracks=None):
    tracks = tracks or [None] * len(airs)
    return [{"date": f"2024-05-26T12:{i:02d}:00+00:00", "air_temperature": a, "track_temperature": t}
            for i, (a, t) in enumerate(zip(airs, tracks))]


def weather_client(rows):
    return make_client({"/sessions": lambda q: (200, [sess(9, "Race", "2024-05-26")]),
                        "/weather": lambda q: (200, rows) if rows else (404, {"detail": "No results found."})})


def test_race_weather_uses_median():
    w = weather_client(weather_rows([20.0, 22.0, 30.0], [30.0, 34.0, 50.0])).race_weather(race())
    assert (w.air_c, w.track_c) == (22.0, 34.0)


def test_race_weather_track_temp_is_optional():
    w = weather_client(weather_rows([20.0, 22.0, 24.0])).race_weather(race())
    assert w.air_c == 22.0 and w.track_c is None


def test_race_weather_none_without_rows():
    assert weather_client([]).race_weather(race()) is None


# --- oficjalna siatka startowa (model v2) ---
def _fixture(name):
    import json
    from pathlib import Path
    return json.loads((Path(__file__).parent / "fixtures" / name).read_text())


def grid_client(grid=None, status=200, log=None, sessions=None):
    drivers = _fixture("openf1_drivers_2026_r20.json")
    rows = _fixture("openf1_starting_grid_2026_r20.json") if grid is None else grid
    return make_client({
        "/sessions": lambda q: (200, sessions if sessions is not None else
                                [sess(11408, "Qualifying", "2024-05-25"), sess(11412, "Race", "2024-05-26")]),
        "/drivers": lambda q: (200, drivers),
        "/starting_grid": lambda q: (status, rows) if status == 200 else (status, {"detail": "x"}),
    }, log)


def grid_entries():
    return [DriverEntry(driver_id=d["name_acronym"].lower(), code=d["name_acronym"], name=d["full_name"], team_id="t")
            for d in _fixture("openf1_drivers_2026_r20.json")]


def test_starting_grid_maps_codes_to_driver_ids():
    grid = grid_client().starting_grid(race(), grid_entries())
    assert grid["nor"] == 1                                   # numer 1 = NOR, pozycja 1 (prawdziwe dane)
    assert sorted(grid.values()) == list(range(1, 23))


def test_starting_grid_asks_for_the_qualifying_session():
    log = []
    grid_client(log=log).starting_grid(race(), grid_entries())
    assert any("session_key=11408" in q for q in log)          # klucz sesji kwalifikacji...
    assert not any("session_key=11412" in q for q in log)      # ...a nie wyścigu


def test_starting_grid_none_when_endpoint_empty():
    assert grid_client(status=404).starting_grid(race(), grid_entries()) is None


def test_starting_grid_none_on_http_error():
    assert grid_client(status=500).starting_grid(race(), grid_entries()) is None


def test_starting_grid_none_without_qualifying_session():
    only_race = [sess(11412, "Race", "2024-05-26")]
    assert grid_client(sessions=only_race).starting_grid(race(), grid_entries()) is None


# --- licznik błędów: odróżnia "brak danych" od "źródło chwilowo nie działa" ---
def test_errors_counter_counts_unavailable_but_not_empty_results():
    c = make_client({"/sessions": lambda q: (500, {})})
    assert c.errors == 0
    assert c.race_laps(race(), ENTRIES) is None
    assert c.errors == 1                                    # awaria serwera

    empty = make_client({})                                 # 404 "No results found" = legalny brak danych
    assert empty.race_laps(race(), ENTRIES) is None and empty.race_weather(race()) is None
    assert empty.errors == 0


def test_errors_counter_increments_for_each_failing_public_method():
    c = make_client({"/sessions": lambda q: (500, {})})
    c.race_laps(race(), ENTRIES); c.race_weather(race()); c.starting_grid(race(), ENTRIES)
    assert c.errors == 3
