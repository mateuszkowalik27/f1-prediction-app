import math

import pytest

import config
from helpers import make_track
from simulate.race import apply_early_season, simulate_race

DRIVERS = ["a", "b", "c", "d", "e", "f"]
EQUAL = {d: 0.0 for d in DRIVERS}
GRID = {d: i + 1 for i, d in enumerate(DRIVERS)}
NO_DNF = {d: 0.0 for d in DRIVERS}


def run(strength=EQUAL, grid=GRID, difficulty=0.5, dnf=NO_DNF, stops=2, n=4000, seed=1):
    return {p.driver_id: p for p in simulate_race(strength, grid, make_track(difficulty), dnf, stops, n=n, seed=seed)}


def test_pole_matters_more_on_monaco_than_monza():
    monaco = run(difficulty=0.9)["a"].win
    monza = run(difficulty=0.1)["a"].win
    assert monaco > monza + 0.05
    assert monaco > 1 / len(DRIVERS)


def test_win_probabilities_sum_to_one():
    result = run()
    assert sum(p.win for p in result.values()) == pytest.approx(1.0)
    for p in result.values():
        assert sum(p.position_distribution) == pytest.approx(1.0)


def test_dnf_probability_one_scores_zero():
    p = run(dnf={**NO_DNF, "a": 1.0})["a"]
    assert (p.win, p.podium, p.points, p.expected_points) == (0.0, 0.0, 0.0, 0.0)
    assert p.position_distribution[-1] == 1.0   # zawsze na końcu stawki


def test_driver_missing_from_dnf_gets_average_and_no_nan():
    dnf = {d: 0.1 for d in DRIVERS if d != "f"}
    for p in run(dnf=dnf).values():
        assert all(math.isfinite(v) for v in [p.win, p.podium, p.points, p.expected_points])
        assert sum(p.position_distribution) == pytest.approx(1.0)


def test_driver_missing_from_grid_starts_at_back():
    strong = {**EQUAL, "f": 1.0}
    with_grid = run(strength=strong, grid={**GRID, "f": 1}, difficulty=0.9)["f"].win
    without = run(strength=strong, grid={d: g for d, g in GRID.items() if d != "f"}, difficulty=0.9)["f"].win
    assert without < with_grid


def test_works_with_22_drivers():
    drivers = [f"d{i}" for i in range(22)]
    result = simulate_race({d: 0.0 for d in drivers}, {d: i + 1 for i, d in enumerate(drivers)},
                           make_track(0.5), {d: 0.0 for d in drivers}, 2, n=500, seed=3)
    assert all(len(p.position_distribution) == 22 for p in result)
    assert sum(p.win for p in result) == pytest.approx(1.0)


def test_same_seed_same_result():
    assert run(seed=5) == run(seed=5)
    assert run(seed=5) != run(seed=6)


def test_early_season_raises_risk_only_in_early_rounds():
    track = make_track(0.5, sc=0.5)
    dnf, early_track = apply_early_season({"a": 0.1, "b": 0.9}, track, round=2)
    assert dnf["a"] == pytest.approx(0.1 * config.EARLY_SEASON_RISK_MULTIPLIER)
    assert dnf["b"] == 1.0                       # obcięte do 1
    assert early_track.sc_probability == pytest.approx(0.5 * config.EARLY_SEASON_RISK_MULTIPLIER)
    assert track.sc_probability == 0.5           # oryginał bez zmian
    late_dnf, late_track = apply_early_season({"a": 0.1}, track, round=config.EARLY_SEASON_ROUNDS + 1)
    assert late_dnf == {"a": 0.1} and late_track.sc_probability == 0.5


def test_unknown_grid_is_sampled_so_favourite_is_less_certain():
    strength = {"a": 1.0, "b": 0.5, "c": 0.0, "d": -0.5, "e": -1.0, "f": -1.5}
    track = make_track(0.9)
    fixed = simulate_race(strength, {d: i + 1 for i, d in enumerate(strength)}, track, NO_DNF, 2, n=4000, seed=1)
    sampled = simulate_race(strength, None, track, NO_DNF, 2, n=4000, seed=1)
    win = lambda rows: {p.driver_id: p.win for p in rows}
    assert win(sampled)["a"] < win(fixed)["a"]                       # niepewna siatka = mniej pewny faworyt
    assert sum(win(sampled).values()) == pytest.approx(1.0)
    assert all(sum(p.position_distribution) == pytest.approx(1.0) for p in sampled)


def test_unknown_grid_same_seed_same_result():
    strength = {"a": 1.0, "b": 0.0, "c": -1.0}
    one = simulate_race(strength, None, make_track(0.5), {}, 2, n=500, seed=3)
    assert one == simulate_race(strength, None, make_track(0.5), {}, 2, n=500, seed=3)


# --- siatka losowana z siły kwalifikacyjnej (model v3, etap 2) ---
def test_unknown_grid_is_sampled_from_the_qualifying_strength_when_given():
    race_strength = {d: (1.0 if d == "a" else 0.0) for d in DRIVERS}       # w wyścigu najszybszy: a
    quali_strength = {d: (3.0 if d == "f" else 0.0) for d in DRIVERS}      # w kwalifikacjach najszybszy: f
    track = make_track(0.9)                                                # tor, na którym start ma duże znaczenie
    shared = {p.driver_id: p for p in simulate_race(race_strength, None, track, NO_DNF, 2, n=6000, seed=2)}
    split = {p.driver_id: p for p in simulate_race(race_strength, None, track, NO_DNF, 2, n=6000, seed=2,
                                                   quali_strength=quali_strength)}
    assert split["f"].win > shared["f"].win + 0.03            # f startuje z przodu częściej, więc wygrywa częściej
    assert split["a"].win < shared["a"].win                   # kosztem a, który w kwalifikacjach nie błyszczy


def test_quali_strength_is_ignored_when_the_grid_is_known():
    race_strength = {d: (1.0 if d == "a" else 0.0) for d in DRIVERS}
    quali_strength = {d: (3.0 if d == "f" else 0.0) for d in DRIVERS}
    with_q = simulate_race(race_strength, GRID, make_track(0.5), NO_DNF, 2, n=800, seed=4, quali_strength=quali_strength)
    without = simulate_race(race_strength, GRID, make_track(0.5), NO_DNF, 2, n=800, seed=4)
    assert with_q == without


# --- wspólny wstrząs zespołu i chaos (model v3, etap 4) ---
TEAMS = {"a": "t1", "b": "t1", "c": "t2", "d": "t2", "e": "t3", "f": "t3"}


def sim(**kw):
    return {p.driver_id: p for p in simulate_race(
        {d: 0.0 for d in DRIVERS}, GRID, make_track(0.3), NO_DNF, 2, n=kw.pop("n", 6000), seed=kw.pop("seed", 5), **kw)}


def test_zero_noise_parameters_reproduce_the_old_result_exactly():
    plain = simulate_race(EQUAL, GRID, make_track(0.5), NO_DNF, 2, n=800, seed=9)
    zero = simulate_race(EQUAL, GRID, make_track(0.5), NO_DNF, 2, n=800, seed=9, teams=TEAMS, team_share=0.0,
                         chaos_prob=0.0, chaos_mult=3.0)
    assert plain == zero


def test_shared_team_noise_changes_the_result_but_not_the_total_spread_of_one_driver():
    solo = sim(teams=TEAMS, team_share=0.0)
    shared = sim(teams=TEAMS, team_share=0.8)
    assert [p.win for p in solo.values()] != [p.win for p in shared.values()]
    assert sum(p.win for p in shared.values()) == pytest.approx(1.0)


def test_chaos_helps_the_outsider_and_hurts_the_favourite():
    strength = {d: (2.0 if d == "a" else 0.0) for d in DRIVERS}
    calm = {p.driver_id: p for p in simulate_race(strength, GRID, make_track(0.3), NO_DNF, 2, n=8000, seed=3)}
    wild = {p.driver_id: p for p in simulate_race(strength, GRID, make_track(0.3), NO_DNF, 2, n=8000, seed=3,
                                                  chaos_prob=0.5, chaos_mult=4.0)}
    assert wild["a"].win < calm["a"].win and wild["f"].win > calm["f"].win


def test_noise_options_keep_probabilities_normalised():
    res = sim(teams=TEAMS, team_share=0.5, chaos_prob=0.3, chaos_mult=3.0)
    assert sum(p.win for p in res.values()) == pytest.approx(1.0)
    assert all(sum(p.position_distribution) == pytest.approx(1.0) for p in res.values())


def test_driver_missing_from_teams_still_works():
    res = sim(teams={"a": "t1"}, team_share=0.5)
    assert sum(p.win for p in res.values()) == pytest.approx(1.0)


def test_chaos_does_not_blur_the_sampled_grid_only_the_race():
    strength = {d: (3.0 if d == "a" else 0.0) for d in DRIVERS}
    quali_strength = {d: (3.0 if d == "a" else 0.0) for d in DRIVERS}
    a = simulate_race(strength, None, make_track(0.9), NO_DNF, 2, n=4000, seed=6, quali_strength=quali_strength,
                      chaos_prob=1.0, chaos_mult=1.0)                                  # chaos x1: bez zmiany
    b = simulate_race(strength, None, make_track(0.9), NO_DNF, 2, n=4000, seed=6, quali_strength=quali_strength)
    assert [p.win for p in a] == [p.win for p in b]                                    # mnożnik 1 nie zmienia nic, także w siatce
