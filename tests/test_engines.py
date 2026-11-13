from engines import predecessor_of, supplier_of, uncovered_teams

TEAMS_2026 = ["alpine", "aston_martin", "audi", "cadillac", "ferrari", "haas", "mclaren", "mercedes", "rb", "red_bull", "williams"]


def test_every_2026_team_has_a_supplier():
    assert uncovered_teams(2026, TEAMS_2026) == []


def test_customer_teams_share_the_works_teams_supplier():
    works = supplier_of(2026, "mercedes")
    assert works and all(supplier_of(2026, t) == works for t in ("mclaren", "williams", "alpine"))
    assert supplier_of(2026, "ferrari") == supplier_of(2026, "haas") == supplier_of(2026, "cadillac")
    assert supplier_of(2026, "aston_martin") != works


def test_suppliers_for_the_ground_effect_seasons_are_known_too():
    for season in (2022, 2023, 2024, 2025):
        assert supplier_of(season, "mercedes") == supplier_of(season, "williams")
        assert supplier_of(season, "red_bull") is not None


def test_a_team_that_switched_supplier_changes_it_between_seasons():
    assert supplier_of(2025, "alpine") != supplier_of(2026, "alpine")


def test_rebrands_point_to_the_predecessor():
    assert predecessor_of("audi") == "sauber" and predecessor_of("rb") == "alphatauri"
    assert predecessor_of("alphatauri") == "toro_rosso" and predecessor_of("aston_martin") == "racing_point"
    assert predecessor_of("mercedes") is None


def test_unknown_team_or_season_gives_none_and_uncovered_lists_the_gaps():
    assert supplier_of(2026, "nowy_zespol") is None and supplier_of(1999, "mercedes") is None
    assert uncovered_teams(2026, ["mercedes", "nowy_zespol"]) == ["nowy_zespol"]
