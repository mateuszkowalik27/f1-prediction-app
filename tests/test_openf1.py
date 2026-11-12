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
