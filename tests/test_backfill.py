from datetime import datetime, timezone

import pytest

from backfill import BackfillReport, build_aggregates, ensure_aggregates
from fakes import ENTRIES, FakeJolpica, FakeOpenF1, clients
from fetch.jolpica import JolpicaError
from helpers import hist_race
from history_store import HistoryStore
from schemas import LapRecord, RaceAggregates, WeatherSample

ROWS = [("d1", "t1", 1), ("d2", "t1", 2), ("d3", "t2", None), ("d4", "t2", 4)]


def steady_laps():
    laps = []
    for driver, secs in (("d1", 90.0), ("d2", 90.5), ("d3", 91.0), ("d4", 91.5)):
        laps += [LapRecord(driver_id=driver, lap=n, duration_s=100.0 if n == 1 else secs, is_pit_out=False,
                           compound="MEDIUM", tyre_age=n - 1) for n in range(1, 14)]
    return laps


def test_creates_up_to_budget_newest_first(tmp_path):
    store = HistoryStore(tmp_path)
    report = ensure_aggregates(store, clients(completed=2), [2026, 2027], budget=3)
    assert report == BackfillReport(created=3, retry_later=0, remaining=1)
    assert [(a.season, a.round) for a in store.all()] == [(2026, 24), (2027, 1), (2027, 2)]   # bez 2026-23, najstarszego


def test_second_run_is_idempotent(tmp_path):
    store = HistoryStore(tmp_path)
    ensure_aggregates(store, clients(completed=2), [2026, 2027], budget=10)
    before = {p.name: p.read_text() for p in tmp_path.iterdir()}
    report = ensure_aggregates(store, clients(completed=2), [2026, 2027], budget=10)
    assert report == BackfillReport(created=0, retry_later=0, remaining=0)
    assert {p.name: p.read_text() for p in tmp_path.iterdir()} == before


def test_failed_openf1_is_not_saved_and_counted(tmp_path):
    store = HistoryStore(tmp_path)
    c = clients(completed=2, openf1=FakeOpenF1(broken=True))
    report = ensure_aggregates(store, c, [2026, 2027], budget=10)
    assert report == BackfillReport(created=0, retry_later=4, remaining=4)
    assert store.all() == [] and not list(tmp_path.glob("*.tmp"))


def test_missing_openf1_is_saved_with_legitimately_empty_fields(tmp_path):
    store = HistoryStore(tmp_path)
    ensure_aggregates(store, clients(completed=2), [2027], budget=10)       # FakeOpenF1 zwraca None = brak danych
    agg = store.load(2027, 2)
    assert agg.sources == {"jolpica": "ok", "openf1": "missing"}
    assert agg.race_pace == {} and agg.tyre_deg == {} and agg.official_grid is None and agg.air_temp_c is None
    assert agg.quali_gap and agg.pit_delta                                    # część z Jolpica jest


def test_season_before_2023_never_calls_openf1():
    f1 = FakeOpenF1()
    agg = build_aggregates(hist_race(2022, 5, ROWS), ENTRIES, clients(openf1=f1))
    assert f1.calls == [] and agg.sources["openf1"] == "missing" and agg.quali_gap


def test_jolpica_failure_raises_and_writes_nothing(tmp_path):
    store = HistoryStore(tmp_path)
    with pytest.raises(JolpicaError):
        ensure_aggregates(store, clients(completed=2, fail_quali_times=True), [2026, 2027], budget=10)
    assert store.all() == []


def test_existing_file_never_overwritten_and_not_counted(tmp_path):
    store = HistoryStore(tmp_path)
    store.save(RaceAggregates(
        season=2027, round=2, circuit_id="c2", computed_at=datetime(2027, 1, 1, tzinfo=timezone.utc),
        quali_gap={"d1": 123.0}, pit_delta={}, race_pace={}, tyre_deg={}, track_deg=None, air_temp_c=None,
        track_temp_c=None, official_grid=None, sources={"jolpica": "ok", "openf1": "ok"}))
    report = ensure_aggregates(store, clients(completed=2), [2027], budget=10)
    assert report.created == 1                                                # tylko 2027-1
    assert store.load(2027, 2).quali_gap == {"d1": 123.0}


def test_race_without_results_is_skipped(tmp_path):
    store = HistoryStore(tmp_path)
    ensure_aggregates(store, clients(completed=2, empty_round=3), [2027], budget=10)   # runda 3 = odwołana, bez wyników
    assert [(a.season, a.round) for a in store.all()] == [(2027, 1), (2027, 2)]


def test_aggregate_fields_are_filled_from_sources():
    f1 = FakeOpenF1(laps=steady_laps(), weather=WeatherSample(air_c=21.0, track_c=33.0), grid={"d1": 2, "d2": 1})
    agg = build_aggregates(hist_race(2027, 2, ROWS), ENTRIES, clients(openf1=f1))
    assert agg.sources == {"jolpica": "ok", "openf1": "ok"}
    assert agg.quali_gap["d1"] == pytest.approx(0.0)
    assert set(agg.pit_delta) == {"t1", "t2"}
    assert agg.race_pace["d1"] < 0 < agg.race_pace["d4"]
    assert (agg.air_temp_c, agg.track_temp_c) == (21.0, 33.0)
    assert agg.official_grid == {"d1": 2, "d2": 1}
    assert agg.circuit_id == "c"


def test_transient_openf1_error_that_returns_none_is_failed_not_missing(tmp_path):
    f1 = FakeOpenF1(transient=True)                     # metoda zwraca None, ale licznik błędów rośnie
    store = HistoryStore(tmp_path)
    report = ensure_aggregates(store, clients(completed=2, openf1=f1), [2027], budget=10)
    assert report.created == 0 and report.retry_later == 2 and store.all() == []
