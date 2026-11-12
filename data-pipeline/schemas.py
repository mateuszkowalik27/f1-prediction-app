"""Kształty danych używane w całym projekcie (pydantic). Te same kształty trafiają do plików JSON."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, model_validator


class Session(BaseModel):
    name: Literal["FP1", "FP2", "FP3", "Qualifying", "Sprint", "SprintQualifying", "Race"]
    start_utc: datetime | None  # None = godzina jeszcze nieustalona (TBC)


class Race(BaseModel):
    season: int
    round: int
    name: str
    circuit_id: str
    country: str
    lat: float
    lon: float
    sessions: list[Session]
    is_sprint: bool


class DriverEntry(BaseModel):
    driver_id: str
    code: str
    name: str
    team_id: str


class WeatherForecast(BaseModel):
    rain_probability: float  # 0-1
    temperature_c: float
    fetched_at: datetime


class TrackProfile(BaseModel):
    circuit_id: str
    slow: float
    medium: float
    fast: float
    straight_share: float
    source: Literal["telemetry", "estimate", "manual"]

    @model_validator(mode="after")
    def _shares_sum_to_one(self) -> "TrackProfile":
        if abs(self.slow + self.medium + self.fast - 1.0) > 0.01:
            raise ValueError("slow + medium + fast musi dawać 1")
        return self


class TrackOverride(BaseModel):
    overtaking_difficulty: float | None = None
    sc_probability: float | None = None


class DriverProbability(BaseModel):
    driver_id: str
    win: float
    podium: float
    points: float
    expected_points: float
    position_distribution: list[float]


class Strategy(BaseModel):
    stops: int
    compounds: list[str]


class StrategyPrediction(BaseModel):
    primary: Strategy
    alternative: Strategy
    rain_risk: float
    confidence: Literal["low", "medium", "high"]


class SafetyCarOdds(BaseModel):
    sc: float
    vsc: float


class StandingRow(BaseModel):
    id: str
    name: str
    points: float
    wins: int
    position: int


class Standings(BaseModel):
    drivers: list[StandingRow]
    constructors: list[StandingRow]


class Calendar(BaseModel):
    season: int
    races: list[Race]


class RaceEvaluation(BaseModel):
    round: int
    winner_prob: float
    winner_in_top3: bool
    mean_abs_position_error: float
    brier_win: float


class WeightSnapshot(BaseModel):
    round: int
    weights: dict[str, float]


class WeekendPayload(BaseModel):
    race: Race
    weather: WeatherForecast | None
    strategy: StrategyPrediction
    safety_car: SafetyCarOdds
    qualifying: list[DriverProbability]
    race_prediction: list[DriverProbability]
    factors_used: list[str]
    factors_skipped: list[str]
    low_data: bool


class WeekendResponse(BaseModel):
    status: Literal["ok", "no_upcoming_race"]
    payload: WeekendPayload | None

    @model_validator(mode="after")
    def _payload_matches_status(self) -> "WeekendResponse":
        if self.status == "ok" and self.payload is None:
            raise ValueError("status 'ok' wymaga payload")
        return self


class ModelPayload(BaseModel):
    weights: dict[str, float]
    weight_history: list[WeightSnapshot]
    factors_used: list[str]
    factors_skipped: list[str]
    evaluation: list[RaceEvaluation]


class Meta(BaseModel):
    generated_at: datetime
    season: int
    data_sources: dict[str, Literal["ok", "missing", "failed"]]
