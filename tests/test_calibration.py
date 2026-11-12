from datetime import datetime, timezone

import pytest

from calibration import apply_tau, fit_tau, load_calibration
from schemas import Calibration, DriverProbability

DRIVERS = ["d1", "d2", "d3", "d4"]


def rows(wins):
    """Przewidywanie z podanymi szansami na wygraną (rozkład pozycji: reszta po równo)."""
    out = []
    for d, w in zip(DRIVERS, wins):
        rest = (1 - w) / 3
        out.append(DriverProbability(driver_id=d, win=w, podium=min(1.0, w + 0.3), points=min(1.0, w + 0.5),
                                     expected_points=10 * w, position_distribution=[w, rest, rest, rest]))
    return out


def races(predicted, favourite_wins, n=80):
    """n wyścigów: faworyt (d1) wygrywa dokładnie `favourite_wins` razy na 100, reszta po kolei."""
    preds = []
    for i in range(n):
        winner = "d1" if (i % 100) < favourite_wins else DRIVERS[1 + i % 3]
        actual = {d: (1 if d == winner else 2) for d in DRIVERS}
        preds.append((rows(predicted), actual))
    return preds


def brier(preds, tau):
    total = 0.0
    for r, actual in preds:
        cal = {x.driver_id: x.win for x in apply_tau(r, tau)}
        total += sum((cal[d] - (actual[d] == 1)) ** 2 for d in DRIVERS) / len(DRIVERS)
    return total / len(preds)


def test_tau_is_one_below_min_races():
    assert fit_tau(races([0.7, 0.1, 0.1, 0.1], 40, n=10), min_races=60) == 1.0


def test_overconfident_predictions_get_tau_below_one_and_lower_brier():
    preds = races([0.7, 0.1, 0.1, 0.1], 40)       # model daje 70%, a faworyt wygrywa 40%
    tau = fit_tau(preds, min_races=60)
    assert tau < 1.0
    assert brier(preds, tau) < brier(preds, 1.0)


def test_underconfident_predictions_get_tau_above_one():
    preds = races([0.4, 0.2, 0.2, 0.2], 75)       # model daje 40%, a faworyt wygrywa 75%
    assert fit_tau(preds, min_races=60) > 1.0


def test_apply_tau_keeps_win_sum_one_and_distribution_sum_one():
    out = apply_tau(rows([0.7, 0.1, 0.1, 0.1]), 0.8)
    assert sum(r.win for r in out) == pytest.approx(1.0)
    assert all(sum(r.position_distribution) == pytest.approx(1.0) for r in out)
    assert out[0].win < 0.7 and out[1].win > 0.1          # tau < 1 spłaszcza


def test_apply_tau_one_is_identity():
    original = rows([0.7, 0.1, 0.1, 0.1])
    assert apply_tau(original, 1.0) == original


def test_zero_win_stays_zero_and_podium_not_below_win():
    out = apply_tau(rows([0.9, 0.1, 0.0, 0.0]), 0.6)
    assert out[2].win == 0.0 and out[3].win == 0.0
    assert all(r.podium >= r.win and r.points >= r.win for r in out)


def test_load_calibration_missing_file_is_none_and_roundtrip(tmp_path):
    assert load_calibration(tmp_path / "calibration.json") is None
    path = tmp_path / "calibration.json"
    path.write_text(Calibration(tau=0.85, n_races=90, fitted_at=datetime(2026, 11, 12, tzinfo=timezone.utc)).model_dump_json())
    assert load_calibration(path).tau == 0.85
    (tmp_path / "bad.json").write_text("nie json")
    assert load_calibration(tmp_path / "bad.json") is None
