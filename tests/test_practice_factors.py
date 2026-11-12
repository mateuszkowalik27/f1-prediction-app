from factors.practice_pace import PracticePace, WeekendShift, adjusted_practice
from helpers import hist_race, make_ctx, make_entries
from schemas import PracticeData


def practice(**runs):
    return PracticeData(best_runs={d: list(r) for d, r in runs.items()})


def test_practice_none_without_data():
    assert PracticePace().score(make_ctx(practice=None)) is None


def test_adjusts_for_compound():
    # A i B jechali na obu mieszankach: miękka jest o 0,6 s szybsza. C tylko na miękkich, D tylko na średnich.
    data = practice(
        A=[("MEDIUM", 81.0), ("SOFT", 80.4)], B=[("MEDIUM", 81.2), ("SOFT", 80.6)],
        C=[("SOFT", 80.5)], D=[("MEDIUM", 81.0)],
    )
    adj = adjusted_practice(data)
    assert adj["C"] > adj["D"]          # surowo C jest szybszy (80,5 < 81,0), ale tylko dzięki miękkim oponom
    assert abs(adj["A"] - 81.0) < 1e-9


def test_practice_pace_faster_driver_scores_higher():
    ctx = make_ctx(practice=practice(d1=[("SOFT", 80.0)], d2=[("SOFT", 81.0)], d3=[("SOFT", 80.5)], d4=[("SOFT", 80.7)]))
    scores = PracticePace().score(ctx)
    assert scores["d1"] > scores["d3"] > scores["d4"] > scores["d2"]


def two_team_history():
    rows = [("d1", "t1", 1), ("d2", "t1", 2), ("d3", "t2", 3), ("d4", "t2", 4)]
    return [hist_race(2027, r, rows) for r in (1, 2, 3)]


def test_weekend_shift_positive_when_team_faster_than_usual():
    fast_t2 = practice(d1=[("SOFT", 81.0)], d2=[("SOFT", 81.1)], d3=[("SOFT", 80.0)], d4=[("SOFT", 80.1)])
    scores = WeekendShift().score(make_ctx(history=two_team_history(), practice=fast_t2))
    assert scores["d3"] > 0 > scores["d1"]   # t2 zwykle słabszy, ale w treningach szybszy


def test_weekend_shift_clipped():
    entries = make_entries(("d1", "t1"), ("d2", "t1"), ("d3", "t2"), ("d4", "t2"), ("d5", "t3"), ("d6", "t3"))
    rows = [("d1", "t1", 1), ("d2", "t1", 2), ("d3", "t2", 3), ("d4", "t2", 4), ("d5", "t3", 5), ("d6", "t3", 6)]
    history = [hist_race(2027, r, rows) for r in (1, 2, 3)]
    data = practice(d1=[("SOFT", 81.0)], d2=[("SOFT", 81.0)], d3=[("SOFT", 80.5)], d4=[("SOFT", 80.5)],
                    d5=[("SOFT", 80.0)], d6=[("SOFT", 80.0)])
    scores = WeekendShift().score(make_ctx(entries=entries, history=history, practice=data))
    assert scores["d5"] == 2.0 and scores["d1"] == -2.0


def test_weekend_shift_none_without_practice():
    assert WeekendShift().score(make_ctx(history=two_team_history(), practice=None)) is None


def test_weekend_shift_none_without_season_pace():
    data = practice(d1=[("SOFT", 80.0)], d3=[("SOFT", 81.0)])
    assert WeekendShift().score(make_ctx(history=[], practice=data)) is None
