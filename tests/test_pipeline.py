import json
from datetime import datetime, timezone

import pytest

import config
from fakes import CALENDAR, ENTRIES, NOW, ROWS, FakeJolpica, FakeOpenF1, clients
from fetch.jolpica import JolpicaError
from helpers import hist_race, make_entries
from run import build_context, main, run_pipeline, select_next_race
from schemas import (
    Calendar, Meta, ModelPayload, PracticeData, Session, Standings, WeekendResponse, WeightSnapshot, WeightsFile,
)

UTC = timezone.utc


def read(out, name, model):
    return model.model_validate_json((out / name).read_text())


def test_writes_all_files_with_valid_schema(tmp_path):
    practice = PracticeData(best_runs={"d1": [("SOFT", 80.0)], "d2": [("SOFT", 80.1)],
                                       "d3": [("SOFT", 80.5)], "d4": [("SOFT", 80.6)]})
    run_pipeline(tmp_path, 2027, NOW, clients(openf1=FakeOpenF1(practice)))
    meta = read(tmp_path, "meta.json", Meta)
    assert meta.data_sources == {"jolpica": "ok", "open_meteo": "ok", "openf1": "ok"}
    assert len(read(tmp_path, "calendar.json", Calendar).races) == 3
    weekend = read(tmp_path, "weekend.json", WeekendResponse)
    assert weekend.status == "ok" and weekend.payload.race.round == 3
    race = weekend.payload.race_prediction
    assert len(race) == 4 and sum(p.win for p in race) == pytest.approx(1.0, abs=0.05)
    assert "car_pace" in weekend.payload.factors_used and "practice_pace" in weekend.payload.factors_used
    model = read(tmp_path, "model.json", ModelPayload)
    assert model.weights["car_pace"] == config.FACTOR_WEIGHTS["car_pace"]
    assert (tmp_path / "standings.json").exists()


def test_jolpica_failure_leaves_files_untouched_and_exits_1(tmp_path):
    names = ["meta.json", "calendar.json", "standings.json", "weekend.json", "model.json"]
    for n in names:
        (tmp_path / n).write_text("OLD")
    assert main(["--out", str(tmp_path)], clients=clients(fail=True)) == 1
    assert all((tmp_path / n).read_text() == "OLD" for n in names)


def test_openf1_missing_marks_source_missing_skips_its_factors_and_flags_low_data(tmp_path):
    run_pipeline(tmp_path, 2027, NOW, clients())
    assert read(tmp_path, "meta.json", Meta).data_sources["openf1"] == "missing"
    payload = read(tmp_path, "weekend.json", WeekendResponse).payload
    assert "practice_pace" in payload.factors_skipped and "weekend_shift" in payload.factors_skipped
    assert payload.low_data is True                  # spec: brak OpenF1 = "mało danych"


def test_no_history_gives_low_data(tmp_path):
    run_pipeline(tmp_path, 2027, NOW, clients(with_history=False))
    payload = read(tmp_path, "weekend.json", WeekendResponse).payload
    assert payload.low_data is True
    assert all(len(p.position_distribution) == 4 for p in payload.race_prediction)


def test_no_upcoming_race_writes_no_upcoming_race_status(tmp_path):
    run_pipeline(tmp_path, 2027, datetime(2027, 12, 1, tzinfo=UTC), clients())
    weekend = read(tmp_path, "weekend.json", WeekendResponse)
    assert weekend.status == "no_upcoming_race" and weekend.payload is None
    assert (tmp_path / "calendar.json").exists() and (tmp_path / "model.json").exists()


def test_cancelled_race_with_empty_results_does_not_crash(tmp_path):
    run_pipeline(tmp_path, 2027, NOW, clients(empty_round=2))
    assert read(tmp_path, "weekend.json", WeekendResponse).status == "ok"


def test_context_excludes_future_rounds():
    history = [hist_race(2027, r, ROWS) for r in range(1, 6)] + [hist_race(2026, 24, ROWS)]
    ctx = build_context(CALENDAR[2], ENTRIES, history, [], {}, None, None, None, None, None, {}, as_of_round=3)
    assert sorted((h.season, h.round) for h in ctx.history) == [(2026, 24), (2027, 1), (2027, 2)]


def test_actual_qualifying_used_only_after_the_session():
    from run import actual_qualifying
    race = CALENDAR[2]
    grid = {"d4": 1, "d3": 2, "d2": 3, "d1": 4}
    after = datetime(2027, 4, 10, 18, 0, tzinfo=UTC)
    got_grid, got_entries = actual_qualifying(race, after, FakeJolpica(grid=grid))
    assert got_grid == grid and sorted(e.driver_id for e in got_entries) == ["d1", "d2", "d3", "d4"]
    assert actual_qualifying(race, NOW, FakeJolpica(grid=grid)) is None          # kwalifikacje jeszcze się nie odbyły
    assert actual_qualifying(race, after, FakeJolpica(grid=None)) is None        # Jolpica jeszcze bez wyników


def test_actual_qualifying_shown_after_session(tmp_path):
    grid = {"d3": 1, "d1": 2, "d2": 3, "d4": 4}
    run_pipeline(tmp_path, 2027, datetime(2027, 4, 10, 18, 0, tzinfo=UTC), clients(grid=grid))
    quali = {p.driver_id: p for p in read(tmp_path, "weekend.json", WeekendResponse).payload.qualifying}
    assert quali["d3"].win == 1.0 and quali["d1"].win == 0.0


def test_reads_weights_json_when_present(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "USE_TUNED_WEIGHTS", True)
    weights = {**config.FACTOR_WEIGHTS, "car_pace": 0.9, "grid_base_weight": 0.2, "race_noise_base": 1.1}
    (tmp_path / "weights.json").write_text(WeightsFile(
        weights=weights, history=[WeightSnapshot(round=2, weights=weights)]).model_dump_json())
    run_pipeline(tmp_path, 2027, NOW, clients())
    model = read(tmp_path, "model.json", ModelPayload)
    assert model.weights["car_pace"] == 0.9 and len(model.weight_history) == 1


def test_select_next_race_skips_finished_and_handles_tbc():
    assert select_next_race(CALENDAR, NOW).round == 3
    assert select_next_race(CALENDAR, datetime(2027, 4, 11, 14, 0, tzinfo=UTC)).round == 3   # wyścig trwa
    tbc = CALENDAR[2].model_copy(update={"sessions": [Session(name="Race", start_utc=None)]})
    assert select_next_race([CALENDAR[0], tbc], NOW).round == 3                              # brak godzin = nadchodzący
    assert select_next_race(CALENDAR, datetime(2027, 4, 11, 17, 0, tzinfo=UTC)) is None


def test_drivers_missing_from_latest_race_are_excluded(tmp_path):
    run_pipeline(tmp_path, 2027, NOW, clients(extra_entry=True))
    payload = read(tmp_path, "weekend.json", WeekendResponse).payload
    assert sorted(p.driver_id for p in payload.race_prediction) == ["d1", "d2", "d3", "d4"]


def test_telemetry_for_upcoming_circuit_comes_from_its_last_race(tmp_path):
    openf1 = FakeOpenF1()
    run_pipeline(tmp_path, 2027, NOW, clients(openf1=openf1))
    for_circuit = [r for r in openf1.trace_requests if r.circuit_id == "c3"]
    assert for_circuit and all(r.season < 2027 for r in for_circuit)   # nadchodzący weekend nie ma jeszcze sesji


def test_model_json_includes_evaluation_of_completed_rounds(tmp_path):
    run_pipeline(tmp_path, 2027, NOW, clients())
    model = read(tmp_path, "model.json", ModelPayload)
    assert [e.round for e in model.evaluation] == [1, 2]


def test_wet_flags_are_cached_between_runs(tmp_path):
    seen = []

    def wet(races):
        seen.append(len(races))
        return {(h.season, h.round): False for h in races}

    c = clients()
    c.wet = wet
    run_pipeline(tmp_path, 2027, NOW, c)
    first = sum(seen)
    seen.clear()
    run_pipeline(tmp_path, 2027, NOW, c)
    assert first > 0 and sum(seen) == 0          # za drugim razem wszystko z pliku wet_cache.json


def test_weights_retuned_once_per_new_round(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "USE_TUNED_WEIGHTS", True)
    run_pipeline(tmp_path, 2027, NOW, clients(completed=3))
    stored = read(tmp_path, "weights.json", WeightsFile)
    assert [s.round for s in stored.history] == [3]
    assert all(lo <= stored.weights[k] <= hi for k, (lo, hi) in config.WEIGHT_BOUNDS.items())
    run_pipeline(tmp_path, 2027, NOW, clients(completed=3))             # ta sama runda: bez ponownego strojenia
    again = read(tmp_path, "weights.json", WeightsFile)
    assert [s.round for s in again.history] == [3] and again.weights == stored.weights
    model = read(tmp_path, "model.json", ModelPayload)
    assert model.weights == stored.weights and len(model.weight_history) == 1


def test_factors_without_backtest_data_are_not_tuned(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "USE_TUNED_WEIGHTS", True)
    run_pipeline(tmp_path, 2027, NOW, clients(completed=3))
    stored = read(tmp_path, "weights.json", WeightsFile)
    defaults = config.default_weights()
    for name in ("practice_pace", "weekend_shift", "wet_skill"):      # w teście wstecznym brak ich danych
        assert stored.weights[name] == defaults[name]


def test_locked_weight_from_config_is_not_tuned(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "USE_TUNED_WEIGHTS", True)
    monkeypatch.setattr(config, "LOCKED_WEIGHTS", {"car_pace", "grid_base_weight"})
    run_pipeline(tmp_path, 2027, NOW, clients(completed=3))
    stored = read(tmp_path, "weights.json", WeightsFile)
    assert stored.weights["car_pace"] == config.FACTOR_WEIGHTS["car_pace"]
    assert stored.weights["grid_base_weight"] == config.GRID_BASE_WEIGHT


def test_base_weights_are_used_when_tuning_is_switched_off(tmp_path, monkeypatch):
    # wynik etapu 1 modelu v3: dostrojone wagi poprawiają tylko poziom, pod który były strojone, a pogarszają prognozy sprzed kwalifikacji
    monkeypatch.setattr(config, "USE_TUNED_WEIGHTS", False)
    (tmp_path).mkdir(exist_ok=True)
    stale = WeightsFile(weights={**config.default_weights(), "car_pace": 0.49}, history=[])
    (tmp_path / "weights.json").write_text(stale.model_dump_json())           # stare dostrojone wagi z poprzednich przebiegów
    run_pipeline(tmp_path, 2027, NOW, clients(completed=3))
    model = read(tmp_path, "model.json", ModelPayload)
    assert model.weights == config.default_weights()                            # robot ich nie używa


def test_no_weights_file_before_three_rounds(tmp_path):
    run_pipeline(tmp_path, 2027, NOW, clients(completed=2))
    assert not (tmp_path / "weights.json").exists()


class CalendarsOnly:
    """Atrapa z kalendarzami wielu sezonów (do wyboru bieżącego sezonu)."""

    def __init__(self, calendars):
        self.calendars = calendars

    def calendar(self, season):
        return self.calendars.get(season, [])


def season_calendar(year):
    start = datetime(year, 11, 20, 13, 0, tzinfo=UTC)
    race = CALENDAR[0].model_copy(update={"season": year, "sessions": [
        Session(name="Race", start_utc=start)]})
    return [race]


def test_resolve_season_stays_on_current_year_while_races_remain():
    from run import resolve_season
    j = CalendarsOnly({2026: season_calendar(2026), 2027: season_calendar(2027)})
    assert resolve_season(datetime(2026, 11, 12, tzinfo=UTC), j) == 2026


def test_resolve_season_moves_to_next_year_when_season_over_and_calendar_published():
    from run import resolve_season
    j = CalendarsOnly({2026: season_calendar(2026), 2027: season_calendar(2027)})
    assert resolve_season(datetime(2026, 12, 20, tzinfo=UTC), j) == 2027


def test_resolve_season_stays_when_next_calendar_not_published():
    from run import resolve_season
    j = CalendarsOnly({2026: season_calendar(2026)})
    assert resolve_season(datetime(2026, 12, 20, tzinfo=UTC), j) == 2026


def test_resolve_season_waits_a_week_after_the_last_race_so_results_are_final():
    from run import resolve_season
    j = CalendarsOnly({2026: season_calendar(2026), 2027: season_calendar(2027)})   # ostatni wyścig 2026-11-20
    assert resolve_season(datetime(2026, 11, 25, tzinfo=UTC), j) == 2026            # 5 dni po: wyniki mogą się jeszcze zmienić
    assert resolve_season(datetime(2026, 11, 28, tzinfo=UTC), j) == 2027            # ponad 7 dni po


def test_weight_history_keeps_seasons_apart_and_does_not_retune_every_run(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "USE_TUNED_WEIGHTS", True)
    from tuning import append_snapshot
    old = append_snapshot(None, config.default_weights(), round=24, season=2026)
    (tmp_path / "weights.json").write_text(old.model_dump_json())
    for _ in range(2):
        run_pipeline(tmp_path, 2027, NOW, clients(completed=3))
    history = read(tmp_path, "weights.json", WeightsFile).history
    assert [(s.season, s.round) for s in history] == [(2026, 24), (2027, 3)]    # druga runda bez ponownego strojenia


def test_substitute_driver_seen_in_qualifying_replaces_the_driver_he_replaced(tmp_path):
    sub = make_entries(("d1", "t1"), ("d2", "t1"), ("d3", "t2"), ("sub", "t2"))
    grid = {"d3": 1, "d1": 2, "d2": 3, "sub": 4}
    run_pipeline(tmp_path, 2027, datetime(2027, 4, 10, 18, 0, tzinfo=UTC), clients(grid=grid, quali_entries=sub))
    payload = read(tmp_path, "weekend.json", WeekendResponse).payload
    assert sorted(p.driver_id for p in payload.race_prediction) == ["d1", "d2", "d3", "sub"]
    assert payload.lineup == "qualifying"


def test_lineup_is_flagged_when_it_comes_from_the_previous_season(tmp_path):
    run_pipeline(tmp_path, 2027, NOW, clients(entries_current=False))
    assert read(tmp_path, "weekend.json", WeekendResponse).payload.lineup == "previous_season"
    run_pipeline(tmp_path, 2027, NOW, clients())
    assert read(tmp_path, "weekend.json", WeekendResponse).payload.lineup == "latest_race"


def test_jolpica_failure_while_preparing_evaluation_leaves_files_untouched(tmp_path):
    names = ["meta.json", "calendar.json", "standings.json", "weekend.json", "model.json"]
    for n in names:
        (tmp_path / n).write_text("OLD")
    assert main(["--out", str(tmp_path), "--season", "2027"], clients=clients(fail_results=True)) == 1
    assert all((tmp_path / n).read_text() == "OLD" for n in names)


def test_broken_openf1_response_does_not_abort_the_update(tmp_path):
    run_pipeline(tmp_path, 2027, NOW, clients(openf1=FakeOpenF1(broken=True)))
    assert read(tmp_path, "meta.json", Meta).data_sources["openf1"] == "failed"
    payload = read(tmp_path, "weekend.json", WeekendResponse).payload
    assert payload.low_data is True and "practice_pace" in payload.factors_skipped
    assert (tmp_path / "standings.json").exists()


def test_weekend_tells_where_track_data_comes_from(tmp_path):
    run_pipeline(tmp_path, 2027, NOW, clients())
    payload = read(tmp_path, "weekend.json", WeekendResponse).payload
    assert payload.track_source in ("computed", "default", "manual") and payload.track_sample_size >= 0
    assert payload.profile_source in ("telemetry", "estimate", "manual", None)


def test_empty_new_season_standings_fall_back_to_previous_season_with_label(tmp_path):
    run_pipeline(tmp_path, 2027, NOW, clients(empty_standings=True))
    standings = read(tmp_path, "standings.json", Standings)
    assert standings.drivers and standings.season == 2026
    run_pipeline(tmp_path, 2027, NOW, clients())
    assert read(tmp_path, "standings.json", Standings).season == 2027


def test_predictions_are_frozen_before_the_race_and_scored_after_it(tmp_path):
    run_pipeline(tmp_path, 2027, NOW, clients(completed=2))                 # runda 3 jeszcze przed nami
    frozen = tmp_path / "predictions" / "2027-3.json"
    assert frozen.exists()
    assert len(read(tmp_path, "model.json", ModelPayload).live_evaluation) == 0
    after = datetime(2027, 4, 11, 14, 0, tzinfo=UTC)                        # wyścig trwa/zakończony, wyniki są
    before_text = frozen.read_text()
    run_pipeline(tmp_path, 2027, after, clients(completed=3))
    assert frozen.read_text() == before_text                                # po starcie nie nadpisujemy
    assert [e.round for e in read(tmp_path, "model.json", ModelPayload).live_evaluation] == [3]


# --- model v2: historia, kalibracja, ocena poza próbką ---
def test_pipeline_backfills_up_to_budget_each_run(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "BACKFILL_RACES_PER_RUN", 2)
    run_pipeline(tmp_path, 2027, NOW, clients())
    assert len(list((tmp_path / "history").glob("*.json"))) == 2
    run_pipeline(tmp_path, 2027, NOW, clients())
    assert len(list((tmp_path / "history").glob("*.json"))) == 4        # 2026: R23, R24; 2027: R1, R2


def test_aggregates_reach_the_context_without_future_rounds(tmp_path, monkeypatch):
    import run as run_module
    from helpers import make_agg
    from history_store import HistoryStore

    monkeypatch.setattr(config, "BACKFILL_RACES_PER_RUN", 0)           # tylko to, co wstawimy ręcznie
    store = HistoryStore(tmp_path / "history")
    for season, rnd in [(2026, 24), (2027, 1), (2027, 2), (2027, 3), (2027, 4)]:
        store.save(make_agg(season, rnd))
    seen = []
    original = run_module.combine_side
    monkeypatch.setattr(run_module, "combine_side",
                        lambda ctx, factors, weights, side: seen.append(ctx.aggregates) or original(ctx, factors, weights, side))
    run_pipeline(tmp_path, 2027, NOW, clients())                        # przewidujemy rundę 3
    assert [(a.season, a.round) for a in seen[0]] == [(2026, 24), (2027, 1), (2027, 2)]


def test_calibration_file_changes_win_but_keeps_sum_one(tmp_path):   # po kwalifikacjach: znana siatka
    from datetime import datetime, timezone
    from schemas import Calibration

    run_pipeline(tmp_path, 2027, AFTER_QUALI, clients(grid=QUALI_GRID))
    before = read(tmp_path, "weekend.json", WeekendResponse).payload.race_prediction
    (tmp_path / "calibration.json").write_text(
        Calibration(tau=0.6, n_races=90, fitted_at=datetime(2026, 11, 12, tzinfo=timezone.utc)).model_dump_json())
    run_pipeline(tmp_path, 2027, AFTER_QUALI, clients(grid=QUALI_GRID))
    after = read(tmp_path, "weekend.json", WeekendResponse).payload.race_prediction
    top = max(before, key=lambda p: p.win).driver_id
    win = lambda rows, d: next(p.win for p in rows if p.driver_id == d)
    assert win(after, top) < win(before, top)                           # tau < 1 spłaszcza faworyta
    assert sum(p.win for p in after) == pytest.approx(1.0)


def test_oos_file_is_copied_into_model_json(tmp_path):
    (tmp_path / "oos.json").write_text('[{"season": 2025, "brier": 0.0251}, {"season": 2026, "brier": 0.0243}]')
    run_pipeline(tmp_path, 2027, NOW, clients())
    model = read(tmp_path, "model.json", ModelPayload)
    assert [(s.season, s.brier) for s in model.out_of_sample] == [(2025, 0.0251), (2026, 0.0243)]


def test_openf1_exception_during_backfill_does_not_abort_and_leaves_no_partial_file(tmp_path):
    run_pipeline(tmp_path, 2027, NOW, clients(openf1=FakeOpenF1(broken=True)))
    assert read(tmp_path, "weekend.json", WeekendResponse).status == "ok"
    history = tmp_path / "history"
    assert not history.exists() or (not list(history.glob("*.json")) and not list(history.glob("*.tmp")))


def test_jolpica_failure_in_backfill_does_not_abort_the_run(tmp_path):
    # uzupełnianie historii to dodatek: jego awaria nie może zatrzymać prognozy weekendu
    assert main(["--out", str(tmp_path), "--season", "2027"], clients=clients(fail_quali_times=True)) == 0
    assert (tmp_path / "weekend.json").exists()


# --- oficjalna siatka z karami (model v2) ---
AFTER_QUALI = datetime(2027, 4, 10, 18, 0, tzinfo=UTC)
QUALI_GRID = {"d3": 1, "d1": 2, "d2": 3, "d4": 4}


def start_grid(official=None, **kw):
    from run import resolve_start_grid
    c = clients(grid=QUALI_GRID, openf1=FakeOpenF1(grid=official), **kw)
    return resolve_start_grid(CALENDAR[2], AFTER_QUALI, c)


def test_no_start_grid_before_qualifying():
    from run import resolve_start_grid
    assert resolve_start_grid(CALENDAR[2], NOW, clients(grid=QUALI_GRID, openf1=FakeOpenF1())) is None


def test_qualifying_only_when_openf1_has_no_grid():
    g = start_grid(None)
    assert g.source == "qualifying" and g.grid == QUALI_GRID and g.penalties == []


def test_official_grid_with_penalty_lists_the_change_and_is_used():
    from schemas import GridPenalty
    g = start_grid({"d1": 1, "d2": 2, "d4": 3, "d3": 4})        # pole sitter d3 ukarany z 1. na 4. miejsce
    assert g.source == "official" and g.grid == {"d1": 1, "d2": 2, "d4": 3, "d3": 4}
    assert g.penalties == [GridPenalty(driver_id="d3", from_pos=1, to_pos=4)]    # tylko ukarany, nie ci, którzy awansowali
    assert g.quali == QUALI_GRID                                                 # kwalifikacje bez kar zostają do pokazania


def test_pit_lane_starter_is_placed_after_the_last_driver():
    g = start_grid({"d3": 1, "d2": 2, "d4": 3})                 # d1 startuje z alei: brak w oficjalnej siatce
    assert g.grid["d1"] == 4 and sorted(g.grid.values()) == [1, 2, 3, 4]


def test_driver_unknown_to_the_lineup_is_ignored_without_crash():
    g = start_grid({"ghost": 1, "d3": 2, "d1": 3, "d2": 4, "d4": 5})
    assert set(g.grid) == {"d1", "d2", "d3", "d4"} and sorted(g.grid.values()) == [1, 2, 3, 4]


def test_openf1_failure_falls_back_to_qualifying():
    from run import resolve_start_grid
    g = resolve_start_grid(CALENDAR[2], AFTER_QUALI, clients(grid=QUALI_GRID, openf1=FakeOpenF1(broken=True)))
    assert g.source == "qualifying" and g.grid == QUALI_GRID


def test_penalized_pole_sitter_wins_less_often(tmp_path):
    sub_clients = lambda official: clients(grid=QUALI_GRID, openf1=FakeOpenF1(grid=official))
    a, b = tmp_path / "a", tmp_path / "b"
    run_pipeline(a, 2027, AFTER_QUALI, sub_clients(None))
    run_pipeline(b, 2027, AFTER_QUALI, sub_clients({"d1": 1, "d2": 2, "d4": 3, "d3": 4}))
    win = lambda out: {p.driver_id: p.win for p in read(out, "weekend.json", WeekendResponse).payload.race_prediction}
    assert win(b)["d3"] < win(a)["d3"]
    assert sum(win(b).values()) == pytest.approx(1.0, abs=0.05)


def test_weekend_payload_reports_grid_source_and_penalties(tmp_path):
    run_pipeline(tmp_path, 2027, AFTER_QUALI, clients(grid=QUALI_GRID, openf1=FakeOpenF1(grid={"d1": 1, "d2": 2, "d4": 3, "d3": 4})))
    payload = read(tmp_path, "weekend.json", WeekendResponse).payload
    assert payload.grid_source == "official" and [(p.driver_id, p.from_pos, p.to_pos) for p in payload.penalties] == [("d3", 1, 4)]
    run_pipeline(tmp_path, 2027, NOW, clients())
    assert read(tmp_path, "weekend.json", WeekendResponse).payload.grid_source == "predicted"


def test_calibration_is_not_applied_before_the_grid_is_known(tmp_path):
    from schemas import Calibration
    plain, calibrated = tmp_path / "plain", tmp_path / "cal"
    calibrated.mkdir()
    (calibrated / "calibration.json").write_text(Calibration(tau=0.6, n_races=90, fitted_at=datetime(2026, 11, 12, tzinfo=UTC)).model_dump_json())
    run_pipeline(plain, 2027, NOW, clients())
    run_pipeline(calibrated, 2027, NOW, clients())
    win = lambda out: [round(p.win, 9) for p in read(out, "weekend.json", WeekendResponse).payload.race_prediction]
    assert win(plain) == win(calibrated)                        # przed kwalifikacjami kalibracja nie działa


def test_forecast_is_asked_for_the_race_start_hour_and_temperature_reaches_the_payload(tmp_path):
    from fakes import forecast as fake_forecast
    calls = []

    def spy(lat, lon, day, start_utc=None):
        calls.append(start_utc)
        return fake_forecast(lat, lon, day, start_utc=start_utc)

    c = clients()
    c.forecast = spy
    run_pipeline(tmp_path, 2027, NOW, c)
    assert calls == [datetime(2027, 4, 11, 13, 0, tzinfo=UTC)]            # start wyścigu rundy 3
    assert read(tmp_path, "weekend.json", WeekendResponse).payload.weather.start_temperature_c == 15.0


def test_partial_official_grid_falls_back_to_qualifying_instead_of_inventing_penalties(monkeypatch):
    monkeypatch.setattr(config, "GRID_MAX_MISSING", 1)
    g = start_grid({"d3": 1, "d1": 2})        # OpenF1 jeszcze niepełne albo część kierowców się nie zmapowała
    assert g.source == "qualifying" and g.grid == QUALI_GRID and g.penalties == []


# --- osobne siły kwalifikacyjna i wyścigowa (model v3, etap 2) ---
def test_qualifying_and_race_use_their_own_strengths(tmp_path, monkeypatch):
    import run as run_module
    seen = {}
    real_quali, real_race = run_module.predict_qualifying, run_module.simulate_race

    def spy_quali(strength, *a, **kw):
        seen["quali"] = dict(strength)
        seen["quali_noise"] = kw.get("noise")
        return real_quali(strength, *a, **kw)

    def spy_race(strength, grid, *a, **kw):
        seen["race"] = dict(strength)
        seen["race_quali"] = kw.get("quali_strength")
        return real_race(strength, grid, *a, **kw)

    monkeypatch.setattr(run_module, "predict_qualifying", spy_quali)
    monkeypatch.setattr(run_module, "simulate_race", spy_race)
    monkeypatch.setattr(config, "QUALI_FACTOR_WEIGHTS", {"car_pace": 1.0})        # kwalifikacje: tylko car_pace
    monkeypatch.setattr(config, "QUALIFYING_NOISE", 0.55)
    run_pipeline(tmp_path, 2027, NOW, clients(completed=2))
    assert seen["quali"] and seen["race"] and seen["quali"] != seen["race"]
    assert seen["race_quali"] == seen["quali"]                   # siatka losowana z siły kwalifikacyjnej (przed kwalifikacjami)
    assert seen["quali_noise"] == 0.55                           # szum kwalifikacji z wag, nie stała na sztywno


def test_weekend_context_gets_a_long_history_for_the_ratings(tmp_path, monkeypatch):
    import run as run_module
    seen = {}
    real = run_module.build_context

    def spy(*a, **kw):
        seen["long"] = kw.get("long_history")
        return real(*a, **kw)

    monkeypatch.setattr(run_module, "build_context", spy)
    run_pipeline(tmp_path, 2027, NOW, clients(completed=2))
    assert seen["long"] and {h.season for h in seen["long"]} >= {2026, 2027}
    assert all((h.season, h.round) < (2027, 3) for h in seen["long"])               # przewidujemy rundę 3


def test_noise_options_reach_both_simulations(tmp_path, monkeypatch):
    import run as run_module
    seen = {}
    real_quali, real_race = run_module.predict_qualifying, run_module.simulate_race

    def spy_quali(strength, *a, **kw):
        seen["quali"] = kw
        return real_quali(strength, *a, **kw)

    def spy_race(strength, grid, *a, **kw):
        seen["race"] = kw
        return real_race(strength, grid, *a, **kw)

    monkeypatch.setattr(run_module, "predict_qualifying", spy_quali)
    monkeypatch.setattr(run_module, "simulate_race", spy_race)
    monkeypatch.setattr(config, "TEAM_NOISE_SHARE", 0.4)
    monkeypatch.setattr(config, "CHAOS_BASE", 0.1)
    monkeypatch.setattr(config, "CHAOS_SC", 0.2)
    run_pipeline(tmp_path, 2027, NOW, clients(completed=2))
    for side in ("quali", "race"):
        assert seen[side]["team_share"] == 0.4 and seen[side]["teams"]
    assert seen["quali"]["chaos_prob"] == 0.0                                        # kwalifikacje: chaos osobnym parametrem (domyślnie 0)
    assert seen["race"]["chaos_prob"] > 0.1                                          # wyścig: baza + składnik od ryzyka safety cara


# --- czynniki treningowe: dwie wersje prognozy i ocena na bieżąco (model v3, etap 5) ---
def strong_signals():
    from schemas import WeekendSignals
    # d4 (najsłabszy w historii atrap) jest w treningach najszybszy: sygnały wyraźnie zmieniają prognozę
    pace = {"d4": -2.0, "d3": -1.0, "d2": 1.0, "d1": 2.0}
    return WeekendSignals(long_run=pace, quali_sim=pace)


def test_frozen_file_has_both_versions_when_weekend_signals_exist(tmp_path):
    from schemas import FrozenPrediction
    run_pipeline(tmp_path, 2027, NOW, clients(completed=2, openf1=openf1_with(strong_signals())))
    frozen = read(tmp_path, "predictions/2027-3.json", FrozenPrediction)
    assert frozen.race_prediction_without_practice and frozen.qualifying and frozen.qualifying_without_practice
    wins = lambda rows: {p.driver_id: round(p.win, 4) for p in rows}
    assert wins(frozen.race_prediction) != wins(frozen.race_prediction_without_practice)
    assert wins(frozen.qualifying) != wins(frozen.qualifying_without_practice)


def test_frozen_file_has_no_second_version_without_signals(tmp_path):
    from schemas import FrozenPrediction
    run_pipeline(tmp_path, 2027, NOW, clients(completed=2))
    frozen = read(tmp_path, "predictions/2027-3.json", FrozenPrediction)
    assert frozen.race_prediction and frozen.race_prediction_without_practice is None and frozen.qualifying


def test_old_frozen_file_without_the_new_fields_still_loads(tmp_path):
    from schemas import FrozenPrediction
    run_pipeline(tmp_path, 2027, NOW, clients(completed=2))
    path = tmp_path / "predictions" / "2027-3.json"
    old = json.loads(path.read_text())
    for key in ("qualifying", "race_prediction_without_practice", "qualifying_without_practice"):
        old.pop(key, None)
    path.write_text(json.dumps(old))
    assert FrozenPrediction.model_validate_json(path.read_text()).qualifying is None


def test_live_comparison_scores_both_versions_after_the_race(tmp_path):
    run_pipeline(tmp_path, 2027, NOW, clients(completed=2, openf1=openf1_with(strong_signals())))
    after = datetime(2027, 4, 11, 14, 0, tzinfo=UTC)
    run_pipeline(tmp_path, 2027, after, clients(completed=3, grid=QUALI_GRID, openf1=openf1_with(strong_signals())))
    model = read(tmp_path, "model.json", ModelPayload)
    (row,) = model.live_comparison
    assert row.round == 3 and 0 <= row.race_rps <= 1 and 0 <= row.race_rps_without <= 1
    assert row.race_rps != row.race_rps_without
    assert row.quali_rps is not None and row.quali_rps_without is not None


def openf1_with(signals):
    f1 = FakeOpenF1()
    f1.signals = signals
    return f1


def test_robot_warns_about_a_season_without_an_engine_table_but_keeps_going(tmp_path, capsys):
    run_pipeline(tmp_path, 2027, NOW, clients(completed=2))
    assert "ENGINE_SUPPLIER" in capsys.readouterr().err                      # sezon 2027 nie ma tabeli silników
    assert (tmp_path / "weekend.json").exists()
