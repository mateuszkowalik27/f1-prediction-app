from datetime import datetime, timedelta, timezone

import config
from fakes import CALENDAR, NOW, FakeOpenF1, clients
from results import build_results, load_results, results_path, update_results
from schemas import Race, RoundResults, Session, SessionRow, SessionTable

UTC = timezone.utc
FP = SessionTable(kind="practice", rows=[SessionRow(driver_id="d1", position=1, best_s=79.5)])


def weekend(start=datetime(2027, 3, 12, 10, 0, tzinfo=UTC), names=("FP1", "Qualifying", "Race")):
    sessions = [Session(name=n, start_utc=start + timedelta(days=i)) for i, n in enumerate(names)]
    return Race(season=2027, round=1, name="GP", circuit_id="c1", country="X", lat=0, lon=0, is_sprint=False,
                sessions=sessions)


def test_finished_sessions_get_tables_of_the_right_kind():
    c = clients(openf1=FakeOpenF1())
    c.openf1.practice_tables = {"FP1": FP}
    r = build_results(weekend(), NOW, c, None)
    assert set(r.sessions) == {"FP1", "Qualifying", "Race"}
    assert r.sessions["Race"].kind == "race" and r.sessions["Race"].rows[1].time == "+5.123"
    q = r.sessions["Qualifying"]
    assert q.kind == "qualifying" and q.rows[0].q3 == 78.0 and q.rows[1].q2 is None   # odpadł w Q1
    assert r.sessions["FP1"].rows[0].best_s == 79.5


def test_sessions_that_have_not_happened_are_left_out():
    future = weekend(start=NOW + timedelta(days=3))
    assert build_results(future, NOW, clients(openf1=FakeOpenF1()), None) is None


def test_results_appear_minutes_after_the_session_ends_not_before():
    c = clients(openf1=FakeOpenF1())
    c.openf1.practice_tables = {"FP1": FP}
    start = NOW - timedelta(hours=1, minutes=5)                   # trening trwa godzinę: skończył się 5 min temu
    race = weekend(start=start, names=("FP1",))
    assert build_results(race, NOW, c, None) is None
    assert "FP1" in build_results(race, NOW + timedelta(minutes=6), c, None).sessions


def test_fresh_table_is_refreshed_until_it_settles_and_then_left_alone():
    f1 = FakeOpenF1()
    f1.practice_tables = {"FP1": FP}
    c = clients(openf1=f1)
    race = weekend(start=NOW - timedelta(hours=1, minutes=30), names=("FP1",))      # skończył się 30 min temu
    first = build_results(race, NOW, c, None)
    more = SessionTable(kind="practice", rows=FP.rows + [SessionRow(driver_id="d2", position=2, best_s=80.0)])
    f1.practice_tables = {"FP1": more}
    refreshed = build_results(race, NOW + timedelta(minutes=10), c, first)
    assert len(refreshed.sessions["FP1"].rows) == 2                 # źródło dopisało drugiego kierowcę
    final = build_results(race, NOW + timedelta(hours=4), c, refreshed)            # ostatnie odświeżenie po czasie na ustabilizowanie
    assert build_results(race, NOW + timedelta(hours=5), c, final) is None          # od teraz bez zmian


def test_existing_tables_are_kept_and_not_refetched():
    existing = RoundResults(season=2027, round=1, generated_at=NOW, sessions={"Race": SessionTable(kind="race", rows=[
        SessionRow(driver_id="old", position=1, time="1:00:00.000")])})
    f1 = FakeOpenF1()
    f1.practice_tables = {"FP1": FP}
    r = build_results(weekend(), NOW, clients(openf1=f1), existing)
    assert r.sessions["Race"].rows[0].driver_id == "old" and "FP1" in r.sessions


def test_openf1_failure_skips_only_practice():
    r = build_results(weekend(), NOW, clients(openf1=FakeOpenF1(broken=False)), None)   # best_laps zwraca None
    assert set(r.sessions) == {"Qualifying", "Race"}


def test_jolpica_failure_skips_those_sessions_without_raising():
    c = clients(openf1=FakeOpenF1())
    c.jolpica.fail_tables = True
    r = build_results(weekend(names=("Qualifying", "Race")), NOW, c, None)
    assert r.sessions == {} and r.attempts == {"Qualifying": 1, "Race": 1}      # nic nie zapisano, próba policzona


def test_update_writes_files_atomically_and_second_run_changes_nothing(tmp_path):
    c = clients(openf1=FakeOpenF1())
    assert update_results(tmp_path, CALENDAR[:1], c, NOW) == 1
    path = results_path(tmp_path, 2027, 1)
    before = path.read_text()
    assert load_results(path).sessions.keys() >= {"Qualifying", "Race"} and not list(tmp_path.rglob("*.tmp"))
    assert update_results(tmp_path, CALENDAR[:1], c, NOW) == 0 and path.read_text() == before


def test_update_respects_budget_and_goes_newest_first(tmp_path):
    assert update_results(tmp_path, CALENDAR[:2], clients(openf1=FakeOpenF1()), NOW, budget=1) == 1
    assert results_path(tmp_path, 2027, 2).exists() and not results_path(tmp_path, 2027, 1).exists()


def test_corrupt_file_is_replaced(tmp_path):
    path = results_path(tmp_path, 2027, 1)
    path.parent.mkdir(parents=True)
    path.write_text("{nie json")
    assert update_results(tmp_path, CALENDAR[:1], clients(openf1=FakeOpenF1()), NOW) == 1
    assert load_results(path) is not None


def test_pipeline_writes_results_and_survives_their_failure(tmp_path):
    from run import run_pipeline
    run_pipeline(tmp_path, 2027, NOW, clients(openf1=FakeOpenF1()))
    assert results_path(tmp_path, 2027, 1).exists()
    other = tmp_path / "b"
    run_pipeline(other, 2027, NOW, clients(openf1=FakeOpenF1(), fail_tables=True))
    assert (other / "weekend.json").exists()


def test_missing_session_is_retried_a_limited_number_of_times(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RESULTS_MAX_ATTEMPTS", 2)
    race = weekend(names=("FP1",))
    c = clients(openf1=FakeOpenF1())                       # best_laps zwraca None: brak danych z OpenF1
    for _ in range(4):
        update_results(tmp_path, [race], c, NOW)
    assert c.openf1.calls.count("best_laps") == 2          # po dwóch próbach rezygnujemy
    assert load_results(results_path(tmp_path, 2027, 1)).attempts == {"FP1": 2}


def test_later_session_is_still_fetched_after_an_earlier_one_exhausted_its_attempts(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RESULTS_MAX_ATTEMPTS", 1)
    race = weekend(names=("FP1", "Race"), start=NOW - timedelta(days=1, hours=5))
    c = clients(openf1=FakeOpenF1())
    update_results(tmp_path, [race], c, NOW)
    r = load_results(results_path(tmp_path, 2027, 1))
    assert "Race" in r.sessions and "FP1" not in r.sessions and r.attempts == {"FP1": 1}
