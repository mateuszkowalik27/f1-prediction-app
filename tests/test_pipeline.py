import json
from datetime import datetime, timezone

import pytest

import config
from fakes import CALENDAR, ENTRIES, NOW, ROWS, FakeJolpica, FakeOpenF1, clients
from fetch.jolpica import JolpicaError
from helpers import hist_race
from run import build_context, main, resolve_grid, run_pipeline, select_next_race
from schemas import (
    Calendar, Meta, ModelPayload, PracticeData, Session, WeekendResponse, WeightSnapshot, WeightsFile,
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


def test_openf1_missing_marks_source_missing_and_skips_its_factors(tmp_path):
    run_pipeline(tmp_path, 2027, NOW, clients())
    assert read(tmp_path, "meta.json", Meta).data_sources["openf1"] == "missing"
    payload = read(tmp_path, "weekend.json", WeekendResponse).payload
    assert "practice_pace" in payload.factors_skipped and "weekend_shift" in payload.factors_skipped


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


def test_resolve_grid_uses_actual_after_qualifying():
    race, predicted = CALENDAR[2], {"d1": 1, "d2": 2, "d3": 3, "d4": 4}
    actual = {"d4": 1, "d3": 2, "d2": 3, "d1": 4}
    after = datetime(2027, 4, 10, 18, 0, tzinfo=UTC)
    assert resolve_grid(race, after, FakeJolpica(grid=actual), predicted) == (actual, "actual")
    assert resolve_grid(race, NOW, FakeJolpica(grid=actual), predicted) == (predicted, "predicted")
    assert resolve_grid(race, after, FakeJolpica(grid=None), predicted) == (predicted, "predicted")


def test_actual_qualifying_shown_after_session(tmp_path):
    grid = {"d3": 1, "d1": 2, "d2": 3, "d4": 4}
    run_pipeline(tmp_path, 2027, datetime(2027, 4, 10, 18, 0, tzinfo=UTC), clients(grid=grid))
    quali = {p.driver_id: p for p in read(tmp_path, "weekend.json", WeekendResponse).payload.qualifying}
    assert quali["d3"].win == 1.0 and quali["d1"].win == 0.0


def test_reads_weights_json_when_present(tmp_path):
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


def test_weights_retuned_once_per_new_round(tmp_path):
    run_pipeline(tmp_path, 2027, NOW, clients(completed=3))
    stored = read(tmp_path, "weights.json", WeightsFile)
    assert [s.round for s in stored.history] == [3]
    assert all(lo <= stored.weights[k] <= hi for k, (lo, hi) in config.WEIGHT_BOUNDS.items())
    run_pipeline(tmp_path, 2027, NOW, clients(completed=3))             # ta sama runda: bez ponownego strojenia
    again = read(tmp_path, "weights.json", WeightsFile)
    assert [s.round for s in again.history] == [3] and again.weights == stored.weights
    model = read(tmp_path, "model.json", ModelPayload)
    assert model.weights == stored.weights and len(model.weight_history) == 1


def test_factors_without_backtest_data_are_not_tuned(tmp_path):
    run_pipeline(tmp_path, 2027, NOW, clients(completed=3))
    stored = read(tmp_path, "weights.json", WeightsFile)
    defaults = config.default_weights()
    for name in ("practice_pace", "weekend_shift", "wet_skill"):      # w teście wstecznym brak ich danych
        assert stored.weights[name] == defaults[name]


def test_locked_weight_from_config_is_not_tuned(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LOCKED_WEIGHTS", {"car_pace", "grid_base_weight"})
    run_pipeline(tmp_path, 2027, NOW, clients(completed=3))
    stored = read(tmp_path, "weights.json", WeightsFile)
    assert stored.weights["car_pace"] == config.FACTOR_WEIGHTS["car_pace"]
    assert stored.weights["grid_base_weight"] == config.GRID_BASE_WEIGHT


def test_no_weights_file_before_three_rounds(tmp_path):
    run_pipeline(tmp_path, 2027, NOW, clients(completed=2))
    assert not (tmp_path / "weights.json").exists()
