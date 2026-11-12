from datetime import datetime, timezone

from history_store import HistoryStore
from schemas import RaceAggregates


def agg(season=2026, rnd=3, **kw):
    base = dict(
        season=season, round=rnd, circuit_id="c", computed_at=datetime(2026, 11, 12, tzinfo=timezone.utc),
        quali_gap={"d1": 0.0, "d2": 0.4}, pit_delta={"t1": -0.1}, race_pace={"d1": -0.2}, tyre_deg={"t1": 0.01},
        track_deg=0.08, air_temp_c=21.5, track_temp_c=34.0, official_grid={"d1": 1, "d2": 2},
        sources={"jolpica": "ok", "openf1": "ok"},
    )
    base.update(kw)
    return RaceAggregates(**base)


def test_roundtrip_save_and_load(tmp_path):
    store = HistoryStore(tmp_path)
    original = agg()
    assert store.save(original) is True
    assert store.load(2026, 3) == original


def test_save_never_overwrites_a_valid_file(tmp_path):
    store = HistoryStore(tmp_path)
    store.save(agg(quali_gap={"d1": 0.0}))
    assert store.save(agg(quali_gap={"d1": 9.9})) is False
    assert store.load(2026, 3).quali_gap == {"d1": 0.0}


def test_save_is_atomic_and_leaves_no_tmp_files(tmp_path):
    store = HistoryStore(tmp_path)
    store.save(agg())
    assert [p.name for p in tmp_path.iterdir()] == ["2026-3.json"]


def test_load_missing_returns_none(tmp_path):
    assert HistoryStore(tmp_path).load(2026, 3) is None


def test_corrupt_file_is_treated_as_missing_and_can_be_replaced(tmp_path):
    (tmp_path / "2026-3.json").write_text("{ nie json")
    store = HistoryStore(tmp_path)
    assert store.load(2026, 3) is None
    assert store.missing([(2026, 3)]) == [(2026, 3)]
    assert store.save(agg()) is True                      # uszkodzony plik wolno zastąpić
    assert store.load(2026, 3) is not None


def test_missing_lists_races_without_files(tmp_path):
    store = HistoryStore(tmp_path)
    store.save(agg(rnd=1))
    assert store.missing([(2026, 1), (2026, 2), (2025, 24)]) == [(2026, 2), (2025, 24)]


def test_all_returns_chronological_order(tmp_path):
    store = HistoryStore(tmp_path)
    for season, rnd in [(2026, 2), (2025, 24), (2026, 1)]:
        store.save(agg(season=season, rnd=rnd))
    assert [(a.season, a.round) for a in store.all()] == [(2025, 24), (2026, 1), (2026, 2)]


def test_all_skips_corrupt_files_and_works_on_missing_directory(tmp_path):
    (tmp_path / "2026-1.json").write_text("śmieci")
    assert HistoryStore(tmp_path).all() == []
    assert HistoryStore(tmp_path / "nie-ma").all() == []
