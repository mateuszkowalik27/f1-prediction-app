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
# Dostrojone testem wstecznym na sezonie 2026 (rundy 1-20, siatka znana, 10 000 symulacji; próbka uczona = oceniana,
# dlatego wybrano płaski fragment, a nie skrajny punkt). Błąd Briera zwycięzcy: 0,0361 -> 0,0246 (losowo: 0,0434);
# poprawa jest taka sama w obu połówkach sezonu (R1-10: 0,0356 -> 0,0229, R11-20: 0,0367 -> 0,0263).
GRID_BASE_WEIGHT = 0.9    # ile tempa kosztuje jedno miejsce na starcie (na torze o trudności 1)
RACE_NOISE_BASE = 0.5     # poziom losowości wyścigu
QUALIFYING_NOISE = 0.8    # losowość kwalifikacji (jeszcze niedostrojona: brak historycznych wyników kwalifikacji w teście)
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
    "grid_base_weight": (0.3, 1.6),
    "race_noise_base": (0.3, 1.5),
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


def default_weights() -> dict[str, float]:
    """Wagi czynników oraz siła startu i poziom losowości: punkt wyjścia dla auto-wag."""
    return {**FACTOR_WEIGHTS, "grid_base_weight": GRID_BASE_WEIGHT, "race_noise_base": RACE_NOISE_BASE}
PIT_OUTLIER_RATIO = 1.5   # postój dłuższy niż 1,5 x mediana wyścigu (czerwona flaga, kara) nie liczy się
FUEL_EFFECT_S_PER_LAP = 0.035   # o tyle szybsze jest auto z każdym okrążeniem (spalone paliwo); korekta przy liczeniu zużycia opon
MIN_STINT_LAPS = 8              # krótszych stintów nie używamy do zużycia opon
RACE_PACE_MIN_LAPS = 5          # tyle czystych okrążeń trzeba mieć, żeby liczyć tempo wyścigowe kierowcy
SLOW_LAP_RATIO = 1.07           # okrążenia wolniejsze niż 107% mediany (safety car, żółte flagi) odrzucamy

# Historia agregatów (model v2)
BACKFILL_RACES_PER_RUN = 6      # ile wyścigów najwyżej uzupełniamy na jedno uruchomienie robota (limity API)
FIRST_BACKFILL_SEASON = 2022    # od którego sezonu zbieramy historię
OPENF1_FIRST_SEASON = 2023      # OpenF1 ma dane dopiero od tego sezonu
TEST_SEASONS = [2024, 2025, 2026]   # sezony oceniane poza próbką (2022-2023 służą tylko do strojenia)
