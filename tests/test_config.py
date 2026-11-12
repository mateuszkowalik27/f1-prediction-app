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
        "weekend_shift", "car_track_fit", "wet_skill", "reliability", "quali_gap",
    }
