import math

from factors.weekend_signal_factors import Fp2LongRun, Fp3QualiSim, SprintPace, SqQuali
from helpers import make_ctx, make_entries
from schemas import WeekendSignals

ENTRIES = make_entries(("fast", "t1"), ("mid", "t2"), ("slow", "t3"), ("rookie", "t4"))
CASES = [
    (Fp2LongRun, "long_run", "fp2_long_run"),
    (Fp3QualiSim, "quali_sim", "fp3_quali_sim"),
    (SprintPace, "sprint_pace", "sprint_pace"),
    (SqQuali, "sq_gap", "sq_quali"),
]


def ctx(**signal_fields):
    return make_ctx(entries=ENTRIES, signals=WeekendSignals(**signal_fields))


def test_names_match_the_weight_keys():
    for factor, _, name in CASES:
        assert factor().name == name


def test_leader_of_the_session_scores_highest_and_values_are_finite():
    for factor, field, _ in CASES:
        scores = factor().score(ctx(**{field: {"fast": -1.0, "mid": 0.0, "slow": 1.5}}))
        assert scores["fast"] > scores["mid"] > scores["slow"], field
        assert all(math.isfinite(v) for v in scores.values())


def test_none_without_signals_or_without_the_given_session():
    for factor, field, _ in CASES:
        assert factor().score(make_ctx(entries=ENTRIES)) is None
        assert factor().score(ctx()) is None                                   # sygnały są, ale ta sesja jest pusta
    other = ctx(long_run={"fast": -1.0, "mid": 0.0})
    assert Fp3QualiSim().score(other) is None and Fp2LongRun().score(other) is not None


def test_driver_missing_from_the_session_is_left_out_and_unknown_ids_are_ignored():
    scores = Fp2LongRun().score(ctx(long_run={"fast": -1.0, "mid": 0.0, "slow": 1.0, "ghost": -9.0}))
    assert "rookie" not in scores and "ghost" not in scores
