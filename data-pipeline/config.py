"""Ustawienia modelu. Wartości liczbowe to punkty startowe, dostrajane w teście wstecznym (Zadanie 17)."""
from schemas import TrackOverride, TrackProfile

SEASON = 2027
N_SIMULATIONS = 10_000
N_SIMULATIONS_TUNING = 2_000
RANDOM_SEED = 2027

# Wagi czynników (auto-wagi mogą je ostrożnie zmieniać w granicach WEIGHT_BOUNDS).
FACTOR_WEIGHTS: dict[str, float] = {
    "car_pace": 0.30,
    "driver_form": 0.15,
    "track_history": 0.10,
    "practice_pace": 0.15,
    "weekend_shift": 0.10,
    "car_track_fit": 0.05,
    "wet_skill": 0.05,
    "reliability": 0.10,
}
GRID_BASE_WEIGHT = 0.15   # ile tempa kosztuje jedno miejsce na starcie (na torze o trudności 1)
RACE_NOISE_BASE = 1.0     # poziom losowości wyścigu
SC_NOISE_FACTOR = 0.5     # ile chaosu dodaje wysokie ryzyko safety cara
PIT_NOISE = 0.1           # ile chaosu dodaje każdy pit-stop

WEIGHT_BOUNDS: dict[str, tuple[float, float]] = {
    "car_pace": (0.10, 0.50),
    "driver_form": (0.05, 0.30),
    "track_history": (0.02, 0.25),
    "practice_pace": (0.05, 0.30),
    "weekend_shift": (0.02, 0.25),
    "car_track_fit": (0.01, 0.15),
    "wet_skill": (0.01, 0.15),
    "reliability": (0.02, 0.25),
    "grid_base_weight": (0.05, 0.40),
    "race_noise_base": (0.5, 2.0),
}
LOCKED_WEIGHTS: set[str] = set()   # wagi, których robot nie rusza
TUNING_K = 8                       # im większe, tym ostrożniejsze strojenie

RECENCY_HALF_LIFE_YEARS = 3
DEFAULT_SC_PROBABILITY = 0.55
DEFAULT_VSC_PROBABILITY = 0.25
SAFETY_PRIOR_STRENGTH = 2.0   # ile "wirtualnych wyścigów" o domyślnym ryzyku dodajemy do historii toru
DEFAULT_STOPS = 2
RAIN_START_INTERMEDIATE = 0.6
SC_ALT_THRESHOLD = 0.6
EARLY_SEASON_ROUNDS = 3
EARLY_SEASON_RISK_MULTIPLIER = 1.3
WET_RACE_MM = 1.0
WET_SHRINK_K = 4
WET_MIN_RAIN_PROBABILITY = 0.2
FIT_MIN_RACES = 6
FIT_RIDGE = 3.0
CORNER_SLOW_KMH = 120
CORNER_FAST_KMH = 220
CORNER_PROMINENCE_KMH = 15
STRAIGHT_KMH = 280
POINTS_TABLE = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]

# Opcjonalne nadpisania (domyślnie puste, wygrywają z wyliczonymi wartościami).
TRACK_OVERRIDES: dict[str, TrackOverride] = {}
TRACK_PROFILE_OVERRIDES: dict[str, TrackProfile] = {}
WET_SKILL_OVERRIDES: dict[str, float] = {}

# Czynniki oparte na wynikach
FORM_HALF_LIFE_ROUNDS = 8   # co ile rund wynik traci połowę wagi (siła bolidu)
FORM_RACES = 5              # ile ostatnich rund liczy się do formy kierowcy
DNF_PRIOR_STRENGTH = 5      # jak mocno ściągamy wskaźnik awarii ku średniej przy małej próbie
DEFAULT_DNF_RATE = 0.08     # gdy nie ma jeszcze żadnych wyników
