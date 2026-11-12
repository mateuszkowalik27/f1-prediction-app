"""Kształty danych używane w całym projekcie (pydantic). Te same kształty trafiają do plików JSON."""
from __future__ import annotations

from datetime import date, datetime
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
    start_temperature_c: float | None = None   # temperatura powietrza o godzinie startu wyścigu (prognoza godzinowa)


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


class TrackStats(BaseModel):
    circuit_id: str
    overtaking_difficulty: float  # 0 = łatwo wyprzedzać, 1 = prawie się nie da
    sc_probability: float
    vsc_probability: float
    sample_size: int
    source: Literal["computed", "default", "manual"]


class TrackOverride(BaseModel):
    overtaking_difficulty: float | None = None
    sc_probability: float | None = None


class HistoricResult(BaseModel):
    driver_id: str
    team_id: str
    grid: int
    finish: int | None  # None = nie sklasyfikowany (DNF, DSQ, DNS)
    status: str


class HistoricRace(BaseModel):
    season: int
    round: int
    circuit_id: str
    date: date
    lat: float
    lon: float
    results: list[HistoricResult]


class PracticeData(BaseModel):
    # driver_id -> lista (mieszanka, mediana 3 najszybszych okrążeń w sekundach)
    best_runs: dict[str, list[tuple[str, float]]]


class SafetyEvent(BaseModel):
    season: int
    kind: Literal["SC", "VSC"]
    lap: int


class TyreHistory(BaseModel):
    median_stops: int
    dominant_compounds: list[str]


class QualiTimes(BaseModel):
    driver_id: str
    q1: float | None = None   # sekundy; None = nie startował w tej sesji
    q2: float | None = None
    q3: float | None = None


class PitStop(BaseModel):
    driver_id: str
    lap: int
    duration_s: float         # czas przejazdu przez aleję serwisową (wjazd -> wyjazd)


class LapRecord(BaseModel):
    driver_id: str
    lap: int
    duration_s: float | None
    is_pit_out: bool
    compound: str | None = None
    tyre_age: int | None = None


class WeatherSample(BaseModel):
    air_c: float
    track_c: float | None = None


class RaceAggregates(BaseModel):
    """Raz policzone cechy zakończonego wyścigu (public/data/history/<sezon>-<runda>.json)."""
    season: int
    round: int
    circuit_id: str
    computed_at: datetime
    quali_gap: dict[str, float]      # driver_id -> strata do pole w % (0 = pole)
    pit_delta: dict[str, float]      # team_id -> sekundy względem mediany stawki
    race_pace: dict[str, float]      # driver_id -> % względem mediany stawki (ujemne = szybciej)
    tyre_deg: dict[str, float]       # team_id -> s/okrążenie względem mediany tej samej mieszanki
    track_deg: float | None          # poziom zużycia toru w tym wyścigu (mediana nachyleń)
    air_temp_c: float | None
    track_temp_c: float | None
    official_grid: dict[str, int] | None
    sources: dict[str, Literal["ok", "missing", "failed"]]   # klucze: jolpica, openf1
    attempts: int = 1                # ile razy budowaliśmy ten agregat (niekompletny próbujemy dopełnić)


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
    number: int | None = None    # numer startowy kierowcy (tylko w klasyfikacji kierowców)
    code: str | None = None      # trzyliterowy skrót kierowcy (ANT, HAM...), tylko w klasyfikacji kierowców


class Standings(BaseModel):
    drivers: list[StandingRow]
    constructors: list[StandingRow]
    season: int | None = None    # sezon, którego dotyczy tabela (poza sezonem pokazujemy ostatnią zakończoną)


class Calendar(BaseModel):
    season: int
    races: list[Race]


class RaceEvaluation(BaseModel):
    round: int
    winner_prob: float
    winner_in_top3: bool
    mean_abs_position_error: float
    brier_win: float


class Calibration(BaseModel):
    tau: float          # wykładnik: szansa' ~ szansa^tau (tau < 1 spłaszcza zbyt pewne szanse, > 1 wyostrza)
    n_races: int        # na ilu przewidywaniach poza próbką dopasowano
    fitted_at: datetime


class SeasonScore(BaseModel):
    season: int
    brier: float


class WeightSnapshot(BaseModel):
    season: int | None = None    # numer rundy powtarza się co sezon, więc sam nie wystarcza
    round: int
    weights: dict[str, float]


class WeightsFile(BaseModel):
    """Zawartość weights.json: bieżące wagi (czynniki + grid_base_weight + race_noise_base) i ich historia."""
    weights: dict[str, float]
    history: list[WeightSnapshot]


class ProfileCache(BaseModel):
    """track_profiles.json: profile policzone z telemetrii (nie zmieniają się, więc liczymy je raz)."""
    profiles: dict[str, TrackProfile]


class WetCache(BaseModel):
    """wet_cache.json: czy dany wyścig był mokry (klucz "sezon-runda"); pogoda z przeszłości się nie zmienia."""
    flags: dict[str, bool]


class GridPenalty(BaseModel):
    driver_id: str
    from_pos: int     # pozycja w kwalifikacjach
    to_pos: int       # pozycja na starcie wyścigu (po karze lub starcie z alei serwisowej)


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
    lineup: Literal["qualifying", "latest_race", "previous_season"] = "latest_race"   # skąd lista kierowców
    grid_source: Literal["official", "qualifying", "predicted"] = "predicted"            # skąd siatka startowa
    penalties: list[GridPenalty] = []                                                      # kto spadł na siatce względem kwalifikacji
    track_source: Literal["computed", "default", "manual"] = "default"                 # skąd statystyki toru
    track_sample_size: int = 0
    profile_source: Literal["telemetry", "estimate", "manual"] | None = None           # skąd profil zakrętów


class FrozenPrediction(BaseModel):
    """predictions/<sezon>-<runda>.json: przewidywanie wyścigu zapisane tuż przed jego startem."""
    season: int
    round: int
    saved_at: datetime
    race_prediction: list[DriverProbability]


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
    live_evaluation: list[RaceEvaluation] = []     # ocena przewidywań, które użytkownik faktycznie widział
    out_of_sample: list[SeasonScore] = []          # Brier poza próbką (public/data/oos.json, liczony ręcznie)


class Meta(BaseModel):
    generated_at: datetime
    season: int
    data_sources: dict[str, Literal["ok", "missing", "failed"]]


class SessionRow(BaseModel):
    """Jeden wiersz tabeli wyników sesji; które pola są wypełnione, zależy od rodzaju sesji (SessionTable.kind)."""
    driver_id: str
    position: int | None = None
    best_s: float | None = None     # trening, sprint-kwalifikacje: najlepsze okrążenie (sekundy)
    q1: float | None = None         # kwalifikacje: najlepsze czasy z części sesji
    q2: float | None = None
    q3: float | None = None
    time: str | None = None         # sprint/wyścig: czas zwycięzcy ("1:32:15.554") albo strata ("+7.152"), jak podaje Jolpica
    status: str | None = None       # sprint/wyścig: "Finished", "+1 Lap", "Retired" ...
    laps: int | None = None
    points: float | None = None     # sprint/wyścig: zdobyte punkty


class SessionTable(BaseModel):
    kind: Literal["practice", "qualifying", "race"]
    rows: list[SessionRow]
    fetched_at: datetime | None = None    # kiedy pobrano; świeże tabele odświeżamy jeszcze przez kilka godzin (źródła dopisują dane)


class RoundResults(BaseModel):
    """public/data/results/<sezon>-<runda>.json: wyniki zakończonych sesji rundy (klucze: nazwy sesji z kalendarza)."""
    season: int
    round: int
    generated_at: datetime
    sessions: dict[str, SessionTable]
    attempts: dict[str, int] = {}     # sesja -> ile razy próbowaliśmy ją pobrać bez skutku (po limicie rezygnujemy)
