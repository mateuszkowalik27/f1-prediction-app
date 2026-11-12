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

    return JolpicaClient(http=httpx.Client(transport=httpx.MockTransport(handler)), retry_delay=0, min_interval=0)


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

    c = JolpicaClient(http=httpx.Client(transport=httpx.MockTransport(handler)), retry_delay=0, min_interval=0)
    with pytest.raises(JolpicaError):
        c.calendar(2026)
    assert len(calls) == 3


def test_retries_then_succeeds():
    calls = []
    data = fixture("jolpica_calendar_2026.json")

    def handler(request):
        calls.append(1)
        return httpx.Response(500) if len(calls) < 3 else httpx.Response(200, json=data)

    c = JolpicaClient(http=httpx.Client(transport=httpx.MockTransport(handler)), retry_delay=0, min_interval=0)
    assert len(c.calendar(2026)) == 23
    assert len(calls) == 3


def test_qualifying_grid_maps_driver_to_position():
    c = make_client({"/2026/20/qualifying.json": fixture("jolpica_qualifying_2026_r20.json")})
    grid = c.qualifying_grid(2026, 20)
    assert grid["norris"] == 1
    assert sorted(grid.values()) == list(range(1, len(grid) + 1))


def test_qualifying_grid_none_before_qualifying():
    empty = {"MRData": {"total": "0", "RaceTable": {"Races": []}}}
    assert make_client({"/2026/21/qualifying.json": empty}).qualifying_grid(2026, 21) is None


def counting_client(tmp_path, immutable_before=2026, sleeps=None, min_interval=0.0, status_sequence=None):
    data = fixture("jolpica_calendar_2026.json")
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if status_sequence and len(calls) <= len(status_sequence):
            code, headers = status_sequence[len(calls) - 1]
            return httpx.Response(code, headers=headers)
        return httpx.Response(200, json=data)

    client = JolpicaClient(
        http=httpx.Client(transport=httpx.MockTransport(handler)), retry_delay=0, min_interval=min_interval,
        cache_dir=tmp_path, immutable_before=immutable_before,
        sleep=(sleeps.append if sleeps is not None else (lambda s: None)),
    )
    return client, calls


def test_cache_serves_finished_seasons_without_http_and_persists(tmp_path):
    client, calls = counting_client(tmp_path)
    client.calendar(2025)
    client.calendar(2025)
    assert len(calls) == 1                                   # drugi raz z dysku
    again, calls2 = counting_client(tmp_path)
    again.calendar(2025)
    assert calls2 == []                                      # nowy klient, ten sam katalog: nadal z dysku


def test_current_season_is_never_cached(tmp_path):
    client, calls = counting_client(tmp_path)
    client.calendar(2026)
    client.calendar(2026)
    assert len(calls) == 2


def test_honors_retry_after_header(tmp_path):
    sleeps = []
    client, calls = counting_client(tmp_path, sleeps=sleeps, status_sequence=[(429, {"Retry-After": "2"})])
    assert len(client.calendar(2026)) == 23
    assert 2.0 in sleeps and len(calls) == 2


def test_throttles_between_requests(tmp_path):
    sleeps = []
    client, _ = counting_client(tmp_path, sleeps=sleeps, min_interval=0.5)
    client.calendar(2026)
    client.calendar(2026)
    assert any(0 < s <= 0.5 for s in sleeps)


def test_qualifying_result_gives_real_lineup_with_teams():
    c = make_client({"/2026/20/qualifying.json": fixture("jolpica_qualifying_2026_r20.json")})
    grid, entries = c.qualifying_result(2026, 20)
    assert grid["norris"] == 1
    by_id = {e.driver_id: e for e in entries}
    assert by_id["norris"].team_id == "mclaren" and len(entries) == len(grid)


# --- czasy kwalifikacji i pit stopy (model v2) ---
def quali_client(mutate=None):
    data = fixture("jolpica_qualifying_2026_r20.json")
    if mutate:
        mutate(data["MRData"]["RaceTable"]["Races"][0]["QualifyingResults"])
    return make_client({"/2026/20/qualifying.json": data})


def test_qualifying_times_parses_minutes_and_seconds():
    times = {t.driver_id: t for t in quali_client().qualifying_times(2026, 20)}
    assert (times["norris"].q1, times["norris"].q2, times["norris"].q3) == (
        pytest.approx(90.939), pytest.approx(89.207), pytest.approx(87.470))


def test_driver_eliminated_in_q1_has_no_q2_q3():
    t = {x.driver_id: x for x in quali_client().qualifying_times(2026, 20)}["bortoleto"]
    assert t.q1 == pytest.approx(101.564) and t.q2 is None and t.q3 is None


def test_driver_eliminated_in_q2_has_no_q3():
    t = {x.driver_id: x for x in quali_client().qualifying_times(2026, 20)}["rafael_camara"]
    assert t.q2 == pytest.approx(91.515) and t.q3 is None


def test_empty_string_time_is_none():
    def blank(rows):
        rows[0]["Q2"] = ""

    t = {x.driver_id: x for x in quali_client(blank).qualifying_times(2026, 20)}["norris"]
    assert t.q2 is None and t.q3 is not None


def test_qualifying_times_none_when_not_held():
    empty = {"MRData": {"total": "0", "RaceTable": {"Races": []}}}
    assert make_client({"/2026/21/qualifying.json": empty}).qualifying_times(2026, 21) is None


def pit_client(mutate=None):
    data = fixture("jolpica_pitstops_2026_r20.json")
    if mutate:
        mutate(data["MRData"]["RaceTable"]["Races"][0]["PitStops"])
    return make_client({"/2026/20/pitstops.json": data})


def test_pit_stops_parsed_with_durations():
    stops = pit_client().pit_stops(2026, 20)
    assert len(stops) == 58
    assert (stops[0].driver_id, stops[0].lap, stops[0].duration_s) == ("hamilton", 14, pytest.approx(24.394))


def test_pit_stops_parses_minute_durations():
    def long_stop(rows):
        rows[0]["duration"] = "1:02.345"

    assert pit_client(long_stop).pit_stops(2026, 20)[0].duration_s == pytest.approx(62.345)


def test_pit_stops_empty_when_none():
    empty = {"MRData": {"total": "0", "RaceTable": {"Races": []}}}
    assert make_client({"/2026/21/pitstops.json": empty}).pit_stops(2026, 21) == []
