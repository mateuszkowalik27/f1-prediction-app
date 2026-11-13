"""Ustawienia modelu. Wartości liczbowe to punkty startowe, dostrajane w teście wstecznym (Zadanie 17)."""
from schemas import TrackOverride, TrackProfile

SEASON = 2027
N_SIMULATIONS = 10_000
N_SIMULATIONS_TUNING = 2_000
RANDOM_SEED = 2027

# Wagi czynników (auto-wagi mogą je ostrożnie zmieniać w granicach WEIGHT_BOUNDS).
FACTOR_WEIGHTS: dict[str, float] = {
    "car_pace": 0.12,       # etap 3 v3: część punktów zastąpiona ocenami i czystym tempem (wariant v3_core, bramka niżej)
    "driver_form": 0.06,
    "track_history": 0.10,
    "practice_pace": 0.15,
    "weekend_shift": 0.10,
    "car_track_fit": 0.05,
    "wet_skill": 0.05,
    "reliability": 0.10,
    "quali_gap": 0.0,       # od etapu 2 modelu v3 służy tylko sile kwalifikacyjnej (QUALI_FACTOR_WEIGHTS); w wyścigu dublował siatkę
    "pit_stop": 0.0,        # WYPADŁ z bramki v3 (patrz komentarz na dole); kod zostaje, waga 0 i LOCKED_WEIGHTS
    "race_vs_quali": 0.0,   # WYPADŁ z bramki (patrz komentarz na dole); kod zostaje, waga 0 i LOCKED_WEIGHTS
    "tyre_deg_fit": 0.0,    # WYPADŁ z bramki (patrz komentarz na dole); kod zostaje, waga 0 i LOCKED_WEIGHTS
    "temp_fit": 0.0,        # WYPADŁ z bramki (patrz komentarz na dole); kod zostaje, waga 0 i LOCKED_WEIGHTS
    "pace_race": 0.10,      # model v3, etap 3: czyste tempo okrążeń (od 2023; brak = czynnik pominięty)
    "rating_race": 0.17,    # model v3, etap 3: ocena Plackett-Luce auto + kierowca
    "rating_quali": 0.0,    # model v3, etap 3: ocena kwalifikacyjna auto + kierowca; tylko siła kwalifikacyjna (q_rating_quali)
}
# Wagi siły KWALIFIKACYJNEJ (jedno okrążenie); zasila przewidywanie kwalifikacji i losowanie siatki przed kwalifikacjami.
# Ustawione ręcznie, nie strojone automatycznie. `quali_gap` jest tu głównym składnikiem (po kwalifikacjach nie wchodzi do wyścigu).
QUALI_FACTOR_WEIGHTS: dict[str, float] = {
    "car_pace": 0.25,
    "quali_gap": 0.40,
    "car_track_fit": 0.10,
    "practice_pace": 0.10,
    "track_history": 0.05,
    "wet_skill": 0.05,
    "driver_form": 0.05,
}
# Dostrojone testem wstecznym na sezonie 2026 (rundy 1-20, siatka znana, 10 000 symulacji; próbka uczona = oceniana,
# dlatego wybrano płaski fragment, a nie skrajny punkt). Błąd Briera zwycięzcy: 0,0361 -> 0,0246 (losowo: 0,0434);
# poprawa jest taka sama w obu połówkach sezonu (R1-10: 0,0356 -> 0,0229, R11-20: 0,0367 -> 0,0263).
GRID_BASE_WEIGHT = 0.9    # ile tempa kosztuje jedno miejsce na starcie (na torze o trudności 1)
RACE_NOISE_BASE = 0.5     # poziom losowości wyścigu
QUALIFYING_NOISE = 0.7    # losowość kwalifikacji; wybrana na sezonach 2022-2023 (min RPS kwalifikacji), na testowych 2024-2026 też blisko optimum (0,6-0,7)
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
    "quali_gap": (0.0, 0.30),
    "pit_stop": (0.0, 0.10),
    "race_vs_quali": (0.0, 0.20),
    "tyre_deg_fit": (0.0, 0.15),
    "temp_fit": (0.0, 0.08),
    "rating_race": (0.0, 0.5),
    "pace_race": (0.0, 0.3),
    "rating_quali": (0.0, 0.3),
    "quali_noise": (0.3, 1.5),
    "grid_base_weight": (0.3, 1.6),
    "race_noise_base": (0.3, 1.5),
}
LOCKED_WEIGHTS: set[str] = {"race_vs_quali", "tyre_deg_fit", "temp_fit", "pit_stop", "quali_gap", "quali_noise", "rating_quali",
                            "team_noise_share", "chaos_base", "chaos_sc", "chaos_rain", "chaos_mult"}   # wagi, których robot nie rusza
TUNING_K = 8                       # im większe, tym ostrożniejsze strojenie
USE_TUNED_WEIGHTS = False          # robot używa wag bazowych; strojenie (walk-forward, oos.py) zostaje jako narzędzie do porównań

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
    quali = {f"q_{name}": QUALI_FACTOR_WEIGHTS.get(name, 0.0) for name in FACTOR_WEIGHTS}
    return {**FACTOR_WEIGHTS, **quali, "grid_base_weight": GRID_BASE_WEIGHT, "race_noise_base": RACE_NOISE_BASE,
            "quali_noise": QUALIFYING_NOISE, "team_noise_share": TEAM_NOISE_SHARE, "chaos_base": CHAOS_BASE,
            "chaos_sc": CHAOS_SC, "chaos_rain": CHAOS_RAIN, "chaos_mult": CHAOS_MULT}
PIT_OUTLIER_RATIO = 1.5   # postój dłuższy niż 1,5 x mediana wyścigu (czerwona flaga, kara) nie liczy się
FUEL_EFFECT_S_PER_LAP = 0.035   # o tyle szybsze jest auto z każdym okrążeniem (spalone paliwo); korekta przy liczeniu zużycia opon
MIN_STINT_LAPS = 8              # krótszych stintów nie używamy do zużycia opon
RACE_PACE_MIN_LAPS = 5          # tyle czystych okrążeń trzeba mieć, żeby liczyć tempo wyścigowe kierowcy
SLOW_LAP_RATIO = 1.07           # okrążenia wolniejsze niż 107% mediany (safety car, żółte flagi) odrzucamy

# Historia agregatów (model v2)
BACKFILL_RACES_PER_RUN = 6      # ile wyścigów najwyżej uzupełniamy na jedno uruchomienie robota (limity API)
MAX_AGGREGATE_ATTEMPTS = 3      # tyle razy próbujemy dopełnić niekompletny agregat, potem zostaje jak jest
BACKFILL_MIN_AGE_DAYS = 2       # świeżo zakończonego wyścigu nie zamrażamy: źródła dopisują dane z opóźnieniem
GRID_MAX_MISSING = 3            # ilu zakwalifikowanych może brakować w oficjalnej siatce (start z alei), zanim jej nie ufamy
RESULTS_ROUNDS_PER_RUN = 8      # ile rund najwyżej uzupełniamy wynikami sesji na jedno uruchomienie robota
RESULTS_MAX_ATTEMPTS = 6        # tyle nieudanych prób pobrania wyników jednej sesji, potem rezygnujemy
RESULTS_DELAY_MINUTES = 10      # tyle minut po końcu sesji próbujemy pobrać jej wyniki po raz pierwszy
RESULTS_SETTLE_HOURS = 3        # przez tyle godzin po końcu sesji wyniki odświeżamy (źródła uzupełniają dane z opóźnieniem)
FIRST_BACKFILL_SEASON = 2022    # od którego sezonu zbieramy historię
OPENF1_FIRST_SEASON = 2023      # OpenF1 ma dane dopiero od tego sezonu
TEST_SEASONS = [2024, 2025, 2026]   # sezony oceniane poza próbką (2022-2023 służą tylko do strojenia)

# Kalibracja szans (model v2)
CAL_MIN_RACES = 60                                            # poniżej tylu przewidywań poza próbką nie korygujemy (tau = 1)
CAL_TAU_GRID = [round(0.6 + 0.05 * i, 2) for i in range(21)]  # 0,60 ... 1,60

# Punkt odniesienia modelu v2 (test poza próbką, domyślna liczba symulacji, bez nowych czynników), 2026-11-12:
#   Brier szans na wygraną: 2024 = 0,0368, 2025 = 0,0328, 2026 = 0,0270 (losowanie ~0,043).
#   Kalibracja: tau = 0,75 na 68 przewidywaniach poza próbką (0,03248 -> 0,03214): model lekko zbyt pewny siebie.
#   Bramka każdego nowego czynnika porównuje się z tymi liczbami (python data-pipeline/oos.py --factor NAZWA).

# Czynniki z agregatów (model v2)
AGGREGATE_MIN_RACES = 3   # tyle agregatów z danymi trzeba mieć, żeby czynnik się włączył
QUALI_GAP_CLIP = 7.0      # strata w kwalifikacjach powyżej tylu % jest przycinana (nieudane okrążenie, awaria)

# Bramka quali_gap (2026-11-12, poza próbką, Brier z czynnikiem / bez): 2024 0,03628/0,03677, 2025 0,03355/0,03277,
#   2026 0,02649/0,02699; średnio 0,03210/0,03218 -> ZOSTAJE (lepszy w 2 z 3 sezonów), ale zysk jest bardzo mały (~0,25%).
PIT_DELTA_CLIP = 2.0         # różnica czasu postoju zespołu względem stawki jest przycinana do +-2 s na wyścig
AGG_SHRINK_K = 3             # ściąganie quali_gap/pit_stop ku zeru dla kierowców i zespołów z małą liczbą wyścigów: n/(n+K)
RACEQ_SHRINK_K = 4           # ściąganie przewagi niedzielnej ku zeru: n/(n+K)
RACE_PACE_CLIP = 5.0         # tempo wyścigowe względem stawki przycinane do +-5% (uszkodzone auto)
# Bramka pit_stop (2026-11-12, poza próbką, Brier z czynnikiem / bez): 2024 0,03623/0,03628, 2025 0,03215/0,03355,
#   2026 0,02549/0,02649; średnio 0,03129/0,03210 -> ZOSTAJE (lepszy we wszystkich 3 sezonach). Uwaga: szybkie postoje
#   korelują z siłą zespołu, więc część efektu może być zastępnikiem siły bolidu, a nie samej szybkości załogi.
TYRE_FIT_MIN_RACES = 6        # tyle agregatów ze zużyciem trzeba mieć, żeby tyre_deg_fit się włączył
DEG_HIGH_RATIO = 1.25        # tor uznajemy za "wysokie zużycie", gdy jego poziom zużycia > 1,25 x średnia wszystkich torów
# Bramka race_vs_quali (2026-11-12, poza próbką, Brier z czynnikiem / bez): 2024 0,03587/0,03609, 2025 0,03346/0,03222,
#   2026 0,02624/0,02553; średnio 0,03186/0,03128 -> WYPADA (gorszy średnio i w 2 z 3 sezonów). Waga 0, LOCKED_WEIGHTS.
# Bramka tyre_deg_fit (2026-11-12, poza próbką, Brier z czynnikiem / bez): 2024 0,03609/0,03623, 2025 0,03222/0,03215,
#   2026 0,02553/0,02549; średnio 0,03128/0,03129 -> WYPADA (praktycznie remis, ale gorszy w 2 z 3 sezonów). Waga 0, LOCKED_WEIGHTS.
#   Wpływ zużycia na strategię opon (predict_strategy deg_ratio) zostaje: to osobna funkcja, nie czynnik siły.
# Bramka temp_fit (2026-11-12, poza próbką, Brier z czynnikiem / bez): 2024 0,03621/0,03623, 2025 0,03360/0,03215,
#   2026 0,02540/0,02549; średnio 0,03173/0,03129 -> WYPADA (gorszy średnio, wyraźnie w 2025). Waga 0, LOCKED_WEIGHTS.
#   Uwaga: w teście wstecznym prognozę zastępowała faktyczna temperatura powietrza z wyścigu (lekko optymistycznie).
# Punkt odniesienia po modelu v2 (poza próbką, 2026-11-12): Brier 2024 = 0,03623, 2025 = 0,03215, 2026 = 0,02549
#   (średnio 0,03129 wobec 0,03218 przed v2); kalibracja tau = 0,8 (0,03163 -> 0,03145).

# Punkt odniesienia v3 (2026-11-13, model v3 etap 1, średni RPS na wyścig, 68 wyścigów testowych 2024-2026, mniej = lepiej):
#   zestaw         przed kwal.  po kwal.  kwalifikacje
#   bazowe           0,1224      0,1147    0,1122     (używa robot; liczby po usunięciu pit_stop)
#   dostrojone       0,1250      0,1115    0,1162     (poprawa tylko tam, gdzie strojone; pogorszenie przed kwal. i w kwal.)
#   sama siatka      0,1645      0,1178    0,1740
#   Dostrojone vs bazowe: przed +0,0026 [+0,0019; +0,0034] WORSE, po -0,0032 [-0,0047; -0,0018] BETTER, kwal. +0,0040 WORSE
#   => USE_TUNED_WEIGHTS = False (robot na wagach bazowych). Bazowe vs sama siatka: wyraźnie lepsze na wszystkich poziomach.
# Bramka v3 (RPS, przedział 90%, z - bez; ujemna = czynnik pomaga), 2026-11-13:
#   quali_gap: przed -0,0005 [-0,0009; -0,00004] BETTER, po +0,0010 [+0,0004; +0,0016] WORSE, kwal. -0,0009 BETTER.
#     Pomaga tam, gdzie siatka jest nieznana (przed kwal., w kwal.), a po kwalifikacjach dubluje informację zawartą już w siatce.
#     Automat zwróciłby "drop"; DECYZJA: bez zmian wagi, w etapie 2 trafia tylko do siły kwalifikacyjnej, nie wyścigowej.
#   pit_stop:  przed +0,0004 [-0,0002; +0,0009] nieoznaczone, po +0,0006 [+0,0002; +0,0009] WORSE, kwal. +0,0009 WORSE
#     -> WYPADA (waga 0, LOCKED_WEIGHTS). Dawna miara (zwycięzca) uznała go za pomocny; pełna kolejność tego nie potwierdza
#     (podejrzenie z v2: zastępnik siły zespołu, nie szybkości załogi).
# Etap 2 v3 (2026-11-13), osobne siły kwalifikacyjna i wyścigowa vs dawna wspólna (RPS, z - bez, przedział 90%):
#   przed kwal. -0,0020 [-0,0030; -0,0010] BETTER, po kwal. +0,0001 [-0,0000; +0,0002] bez różnicy, kwal. -0,0051 [-0,0066; -0,0036] BETTER.
#   Średni RPS (osobne): przed 0,1206, po 0,1148, kwalifikacje 0,1066. Szum kwalifikacji 0,7 wybrany na 2022-2023.

# Oceny siły (ratings.py, model v3 etap 3); wstępne wartości, dobierane na sezonach 2022-2023 (oos.py --scan-ratings)
RATING_ETA_CAR = 0.1        # tempo uczenia oceny auta po wyścigu (wybrane na 2022-2023; krajobraz płaski: różnice ~0,0001 RPS)
RATING_ETA_DRIVER = 0.03    # tempo uczenia poprawki kierowcy (wolniej niż auto: kierowca zmienia się wolniej)
RATING_CAR_KEEP = 0.8       # ile oceny auta zostaje na początku nowego sezonu (auta się zmieniają)
RATING_DRIVER_KEEP = 0.9    # ile poprawki kierowcy zostaje na początku nowego sezonu
# Bramka etapu 3 v3 (RPS wariant - baza, przedział 90%; ujemna = wariant lepszy), 2026-11-13, 68 wyścigów testowych:
#   rating_race (oceny zamiast punktów): przed -0,0002 [-0,0006; +0,0001], po +0,0000 -> nieoznaczone (równe punktom).
#   rating_race_plus (oceny + połowa starych): przed -0,0002 [-0,0004; -0,00003] BETTER, po -0,0001 [-0,0003; +0,0001].
#   pace_race (czyste tempo kosztem części punktów): przed -0,0002 [-0,0002; -0,0001] BETTER, po -0,0001 [-0,0002; +0,0001].
#   v3_core (oceny 0,17 + tempo 0,10 + po połowie starych punktów): przed -0,0003 [-0,0005; -0,0001] BETTER, po -0,0001 -> WCHODZI.
#   Efekt jest mały (ok. 0,3% RPS przed kwalifikacjami), ale jednoznaczny kierunkowo i bez pogorszenia po kwalifikacjach.
RATING_QUALI_DRIVER_K = 6    # ściąganie poprawki kierowcy (względem kolegi) ku zeru: n/(n+K); porównanie z kolegą jest zaszumione
#   rating_quali (zastępuje quali_gap w sile kwalifikacyjnej): przed +0,0010 [+0,0003; +0,0018] WORSE, kwal. +0,0016 [+0,0008; +0,0024] WORSE -> WYPADA.
#   rating_quali_plus (pół na pół z quali_gap): przed +0,0003, kwal. +0,0003, oba nieoznaczone -> stan dotychczasowy (rating_quali waga 0, LOCKED).
#   Wniosek: prosta średnia straty kierowcy (quali_gap) jest w kwalifikacjach lepsza niż rozkład na auto i kierowcę.
# Punkt odniesienia po etapie 3 v3 (2026-11-13, wagi bazowe, średni RPS): przed kwal. 0,1203, po kwal. 0,1147, kwalifikacje 0,1066.

# Losowość symulacji (model v3, etap 4): wspólny wstrząs zespołu i chaos (mieszanka). Zerowe = zachowanie sprzed etapu 4.
TEAM_NOISE_SHARE = 0.0   # jaka część losowości kierowcy jest wspólna dla zespołu (0-1)
CHAOS_BASE = 0.0         # bazowe prawdopodobieństwo "chaosu" w wyścigu / kwalifikacjach
CHAOS_SC = 0.0           # dodatek do tego prawdopodobieństwa za ryzyko safety cara toru (tylko wyścig)
CHAOS_RAIN = 0.0         # dodatek za szansę deszczu
CHAOS_MULT = 2.0         # ile razy większa jest losowość w symulacji z chaosem
