import config


def test_every_weight_has_bounds_and_base_inside_them():
    bases = dict(config.FACTOR_WEIGHTS)
    bases["grid_base_weight"] = config.GRID_BASE_WEIGHT
    bases["race_noise_base"] = config.RACE_NOISE_BASE
    for name, base in bases.items():
        assert name in config.WEIGHT_BOUNDS, name
        lo, hi = config.WEIGHT_BOUNDS[name]
        assert 0 <= lo <= base <= hi, name


def test_factor_weight_keys_complete():
    assert set(config.FACTOR_WEIGHTS) == {
        "car_pace", "driver_form", "track_history", "practice_pace",
        "weekend_shift", "car_track_fit", "wet_skill", "reliability", "quali_gap", "pit_stop", "race_vs_quali", "tyre_deg_fit", "temp_fit", "rating_race", "pace_race", "rating_quali",
        "fp2_long_run", "fp3_quali_sim", "sprint_pace", "sq_quali",
    }


def test_default_weights_carry_the_qualifying_weights_and_noise():
    w = config.default_weights()
    assert w["q_quali_gap"] == config.QUALI_FACTOR_WEIGHTS["quali_gap"] > 0
    assert w["quali_noise"] == config.QUALIFYING_NOISE
    assert set(config.QUALI_FACTOR_WEIGHTS) <= set(config.FACTOR_WEIGHTS)       # tylko istniejące czynniki


def test_quali_gap_serves_qualifying_not_the_race():
    assert config.FACTOR_WEIGHTS["quali_gap"] == 0.0 and "quali_gap" in config.LOCKED_WEIGHTS
    assert config.QUALI_FACTOR_WEIGHTS["quali_gap"] >= max(config.QUALI_FACTOR_WEIGHTS.values()) - 1e-9   # główny składnik


def test_qualifying_weights_and_noise_are_not_touched_by_the_tuner():
    assert "quali_noise" in config.LOCKED_WEIGHTS
    assert not any(k.startswith("q_") for k in config.WEIGHT_BOUNDS)


def test_noise_parameters_are_weights_and_locked_from_the_tuner():
    w = config.default_weights()
    for key in ("team_noise_share", "chaos_base", "chaos_sc", "chaos_rain", "chaos_mult", "chaos_quali"):
        assert key in w and key in config.LOCKED_WEIGHTS and key not in config.WEIGHT_BOUNDS
