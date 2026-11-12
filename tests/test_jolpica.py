import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from fetch.jolpica import JolpicaClient, JolpicaError, NoResultsError

FIX = Path(__file__).parent / "fixtures"
PREFIX = "/ergast/f1"


def fixture(name):
    return json.loads((FIX / name).read_text())


def make_client(routes):
    """routes: {ścieżka bez prefiksu: dict | callable(request) -> dict}"""

    def handler(request: httpx.Request) -> httpx.Response:
        key = request.url.path.removeprefix(PREFIX)
        if key not in routes:
            return httpx.Response(404, json={})
        value = routes[key]
        return httpx.Response(200, json=value(request) if callable(value) else value)

    return JolpicaClient(http=httpx.Client(transport=httpx.MockTransport(handler)), retry_delay=0)


def calendar_client(mutate=None):
    data = fixture("jolpica_calendar_2026.json")
    if mutate:
        mutate(data["MRData"]["RaceTable"]["Races"])
    return make_client({"/2026.json": data})


def test_calendar_converts_to_utc():
    races = calendar_client().calendar(2026)
    assert len(races) == 23
    r1 = races[0]
    assert (r1.round, r1.name, r1.circuit_id) == (1, "Australian Grand Prix", "albert_park")
    race = next(s for s in r1.sessions if s.name == "Race")
    assert race.start_utc == datetime(2026, 3, 8, 4, 0, tzinfo=timezone.utc)
    assert r1.lat == pytest.approx(-37.8497)


def test_sprint_weekend_flag():
    races = calendar_client().calendar(2026)
    assert races[0].is_sprint is False
    assert races[1].is_sprint is True
    names = [s.name for s in races[1].sessions]
    assert "Sprint" in names and "SprintQualifying" in names and "FP2" not in names


def test_missing_session_time_is_none():
    def drop_times(races):
        del races[0]["Qualifying"]["time"]
        del races[0]["time"]

    r1 = calendar_client(drop_times).calendar(2026)[0]
    by_name = {s.name: s.start_utc for s in r1.sessions}
    assert by_name["Qualifying"] is None
    assert by_name["Race"] is None
    assert by_name["FP1"] is not None


def test_standings_parsed():
    c = make_client({
        "/2026/driverstandings.json": fixture("jolpica_driverstandings_2026.json"),
        "/2026/constructorstandings.json": fixture("jolpica_constructorstandings_2026.json"),
    })
    st = c.standings(2026)
    top = st.drivers[0]
    assert (top.id, top.position, top.points, top.wins) == ("antonelli", 1, 390.0, 9)
    assert st.constructors[0].id == "mercedes"
    assert st.constructors[0].points == 652.0


def test_entries_from_standings_use_latest_team():
    c = make_client({"/2026/driverstandings.json": fixture("jolpica_driverstandings_2026.json")})
    entries = {e.driver_id: e for e in c.entries(2026)}
    ant = entries["antonelli"]
    assert (ant.code, ant.team_id, ant.name) == ("ANT", "mercedes", "Andrea Kimi Antonelli")


def test_race_results_parsed_with_non_classified_as_none():
    c = make_client({"/2026/1/results.json": fixture("jolpica_results_2026_r1.json")})
    race = c.race_results(2026, 1)
    assert race.circuit_id == "albert_park"
    assert (race.lat, race.lon) == (pytest.approx(-37.8497), pytest.approx(144.968))
    first = race.results[0]
    assert (first.driver_id, first.team_id, first.grid, first.finish) == ("russell", "mercedes", 1, 1)
    hul = next(r for r in race.results if r.driver_id == "hulkenberg")
    assert hul.finish is None


def test_race_results_raises_when_no_results_yet():
    data = fixture("jolpica_results_2026_r1.json")
    data["MRData"]["RaceTable"]["Races"] = []
    c = make_client({"/2026/1/results.json": data})
    with pytest.raises(NoResultsError):
        c.race_results(2026, 1)


def test_circuit_history_spans_seasons():
    c = make_client({
        "/2023/circuits/monaco/results.json": fixture("jolpica_monaco_2023.json"),
        "/2024/circuits/monaco/results.json": fixture("jolpica_monaco_2024.json"),
        "/2025/circuits/monaco/results.json": {"MRData": {"total": "0", "RaceTable": {"Races": []}}},
    })
    hist = c.circuit_history("monaco", [2023, 2024, 2025])
    assert [h.season for h in hist] == [2023, 2024]
    assert hist[0].results[0].driver_id == "max_verstappen"


def _synthetic_season(rounds=3, drivers=40):
    """Sztuczny sezon: 40 wierszy na rundę, więc strona po 100 wierszy dzieli rundę 3 na dwie części."""
    races = []
    for rnd in range(1, rounds + 1):
        results = [{
            "position": str(i + 1), "positionText": str(i + 1), "grid": str(i + 1),
            "status": "Finished",
            "Driver": {"driverId": f"d{i}"}, "Constructor": {"constructorId": f"t{i // 2}"},
        } for i in range(drivers)]
        races.append({
            "season": "2026", "round": str(rnd), "raceName": f"GP{rnd}", "date": f"2026-0{rnd}-01",
            "Circuit": {"circuitId": f"c{rnd}", "Location": {"lat": "1.0", "long": "2.0", "country": "X"}},
            "Results": results,
        })
    return races


def test_season_results_stops_at_round_and_merges_pages():
    rows = [(r, res) for r in _synthetic_season() for res in r["Results"]]

    def pager(request):
        limit = int(request.url.params["limit"])
        offset = int(request.url.params.get("offset", 0))
        page = rows[offset:offset + limit]
        grouped = {}
        for race, res in page:
            r = grouped.setdefault(race["round"], {**{k: v for k, v in race.items() if k != "Results"}, "Results": []})
            r["Results"].append(res)
        return {"MRData": {"total": str(len(rows)), "RaceTable": {"Races": list(grouped.values())}}}

    c = make_client({"/2026/results.json": pager})
    hist = c.season_results(2026, up_to_round=2)
    assert [h.round for h in hist] == [1, 2]
    assert all(len(h.results) == 40 for h in hist)
    full = c.season_results(2026, up_to_round=3)
    assert len(full[2].results) == 40  # runda 3 złożona z dwóch stron


def test_retries_then_raises_on_http_500():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(500)

    c = JolpicaClient(http=httpx.Client(transport=httpx.MockTransport(handler)), retry_delay=0)
    with pytest.raises(JolpicaError):
        c.calendar(2026)
    assert len(calls) == 3


def test_retries_then_succeeds():
    calls = []
    data = fixture("jolpica_calendar_2026.json")

    def handler(request):
        calls.append(1)
        return httpx.Response(500) if len(calls) < 3 else httpx.Response(200, json=data)

    c = JolpicaClient(http=httpx.Client(transport=httpx.MockTransport(handler)), retry_delay=0)
    assert len(c.calendar(2026)) == 23
    assert len(calls) == 3
