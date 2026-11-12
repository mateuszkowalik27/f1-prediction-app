"""Wspólne konstruktory do testów czynników i symulacji."""
from datetime import datetime, timezone

from factors.base import RaceContext
from schemas import DriverEntry, Race, Session, TrackStats


def make_entries(*specs):
    """specs: (driver_id, team_id) -> DriverEntry z kodem z 3 liter."""
    return [DriverEntry(driver_id=d, code=d[:3].upper(), name=d, team_id=t) for d, t in specs]


def make_race(round=5, circuit_id="c", day=datetime(2027, 5, 9, 13, 0, tzinfo=timezone.utc)):
    return Race(season=2027, round=round, name="Test GP", circuit_id=circuit_id, country="X",
                lat=0.0, lon=0.0, is_sprint=False, sessions=[Session(name="Race", start_utc=day)])


def make_track(difficulty=0.5, sc=0.5, circuit_id="c"):
    return TrackStats(circuit_id=circuit_id, overtaking_difficulty=difficulty, sc_probability=sc,
                      vsc_probability=0.2, sample_size=5, source="computed")


def make_ctx(entries=None, **overrides):
    entries = entries or make_entries(("d1", "t1"), ("d2", "t1"), ("d3", "t2"), ("d4", "t2"))
    base = dict(race=make_race(), entries=entries, track=make_track(), season=2027)
    base.update(overrides)
    return RaceContext(**base)
