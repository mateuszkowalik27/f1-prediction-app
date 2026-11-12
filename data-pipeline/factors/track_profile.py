"""Profil toru: udział zakrętów wolnych / średnich / szybkich i prostych.

Źródła, od najważniejszego: ręczne nadpisanie -> telemetria (prędkość na okrążeniu) -> szacunek z pliku.
"""
from __future__ import annotations

import json
from pathlib import Path

import config
from schemas import TrackProfile

ESTIMATES_FILE = Path(__file__).resolve().parent.parent / "data" / "track_profile_estimates.json"


def _corner_minima(speeds: list[float]) -> list[float]:
    """Minimalne prędkości zakrętów: lokalne minima o głębokości (prominence) >= CORNER_PROMINENCE_KMH."""
    pts: list[float] = []
    for v in speeds:  # zwijamy plateau, żeby minimum nie było rozdzielone
        if not pts or v != pts[-1]:
            pts.append(v)
    minima = []
    for i in range(1, len(pts) - 1):
        if not (pts[i] < pts[i - 1] and pts[i] < pts[i + 1]):
            continue
        left = right = pts[i]
        for j in range(i - 1, -1, -1):
            if pts[j] < pts[i]:
                break
            left = max(left, pts[j])
        for j in range(i + 1, len(pts)):
            if pts[j] < pts[i]:
                break
            right = max(right, pts[j])
        if min(left, right) - pts[i] >= config.CORNER_PROMINENCE_KMH:
            minima.append(pts[i])
    return minima


def profile_from_speed_trace(circuit_id: str, speed_kmh: list[float]) -> TrackProfile | None:
    minima = _corner_minima(speed_kmh)
    if not minima:
        return None
    slow = sum(m < config.CORNER_SLOW_KMH for m in minima)
    fast = sum(m >= config.CORNER_FAST_KMH for m in minima)
    medium = len(minima) - slow - fast
    return TrackProfile(
        circuit_id=circuit_id, slow=slow / len(minima), medium=medium / len(minima), fast=fast / len(minima),
        straight_share=sum(v >= config.STRAIGHT_KMH for v in speed_kmh) / len(speed_kmh),
        source="telemetry",
    )


def load_estimates() -> dict[str, TrackProfile]:
    raw = json.loads(ESTIMATES_FILE.read_text())["circuits"]
    return {cid: TrackProfile(circuit_id=cid, source="estimate", **vals) for cid, vals in raw.items()}


def get_profile(
    circuit_id: str,
    trace: list[float] | None,
    estimates: dict[str, TrackProfile],
    override: TrackProfile | None,
) -> TrackProfile | None:
    if override is not None:
        return override
    if trace:
        measured = profile_from_speed_trace(circuit_id, trace)
        if measured is not None:
            return measured
    return estimates.get(circuit_id)
