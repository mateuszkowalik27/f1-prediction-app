import numpy as np
import pytest

from simulate.noise import draw_noise

DRIVERS = ["a", "b", "c", "d"]
TEAMS = {"a": "t1", "b": "t1", "c": "t2", "d": "t2"}


def rng():
    return np.random.default_rng(11)


def test_zero_parameters_are_identical_to_plain_normal_noise():
    plain = np.random.default_rng(3).normal(0.0, 0.7, size=(500, 4))
    assert np.array_equal(draw_noise(np.random.default_rng(3), 500, DRIVERS, 0.7, TEAMS, 0.0, 0.0, 5.0), plain)


def test_shared_noise_correlates_teammates_by_the_share_and_keeps_each_drivers_spread():
    x = draw_noise(rng(), 40000, DRIVERS, 0.7, TEAMS, team_share=0.6)
    assert np.std(x[:, 0]) == pytest.approx(0.7, rel=0.03)                    # całkowita losowość kierowcy bez zmian
    assert np.corrcoef(x[:, 0], x[:, 1])[0, 1] == pytest.approx(0.6, abs=0.03)   # koledzy: korelacja = udział wspólny
    assert abs(np.corrcoef(x[:, 0], x[:, 2])[0, 1]) < 0.03                    # inne zespoły: niezależnie


def test_chaos_inflates_the_spread_in_the_right_share_of_simulations():
    many = [f"d{i}" for i in range(60)]                                       # wiele kolumn, żeby rozmiar losowości w wierszu był dokładny
    x = draw_noise(rng(), 6000, many, 0.5, None, chaos_prob=0.25, chaos_mult=3.0)
    scale = np.std(x, axis=1)
    assert (scale > 1.0).mean() == pytest.approx(0.25, abs=0.03)              # ok. 25% symulacji ma 3 razy większą losowość (1,5 zamiast 0,5)
    assert np.median(scale) == pytest.approx(0.5, abs=0.05)                   # a większość jest spokojna


def test_driver_missing_from_teams_gets_his_own_shock_and_prob_is_clamped():
    x = draw_noise(rng(), 2000, DRIVERS, 0.5, {"a": "t1"}, team_share=0.5)
    assert abs(np.corrcoef(x[:, 1], x[:, 2])[0, 1]) < 0.1                      # b i c bez zespołu: niezależni
    y = draw_noise(rng(), 100, DRIVERS, 0.5, TEAMS, team_share=5.0, chaos_prob=2.0, chaos_mult=2.0)
    assert np.isfinite(y).all()                                                # wartości spoza zakresu nie psują losowania
