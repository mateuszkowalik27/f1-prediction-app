import pytest
from pydantic import ValidationError

from schemas import Session, TrackProfile, WeekendResponse


def test_session_allows_tbc_time():
    s = Session(name="Race", start_utc=None)
    assert s.start_utc is None


def test_profile_shares_sum_to_one():
    ok = TrackProfile(circuit_id="monaco", slow=0.6, medium=0.3, fast=0.1,
                      straight_share=0.1, source="estimate")
    assert ok.slow == 0.6
    with pytest.raises(ValidationError):
        TrackProfile(circuit_id="x", slow=0.5, medium=0.3, fast=0.3,
                     straight_share=0.1, source="estimate")


def test_weekend_response_requires_payload_when_ok():
    with pytest.raises(ValidationError):
        WeekendResponse(status="ok", payload=None)
    assert WeekendResponse(status="no_upcoming_race", payload=None).payload is None
