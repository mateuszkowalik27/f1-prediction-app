# F1 Prediction App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Darmowa PWA z kalendarzem w czasie polskim, pogodą toru, klasyfikacjami i w pełni automatycznymi predykcjami F1 (kwalifikacje, wyścig, strategia) jako szanse procentowe.

**Architecture:** Skrypt Pythona (GitHub Actions) pobiera dane z Jolpica, Open-Meteo i OpenF1, liczy predykcje (czynniki + symulacja Monte Carlo + auto-wagi) i zapisuje JSON do `public/data/`. Aplikacja React (Vite, PWA) na Vercel tylko czyta te pliki.

**Tech Stack:** Python 3.12, pydantic 2, numpy, httpx, pytest; Node 20, Vite, React 18, vite-plugin-pwa, vitest, @testing-library/react.

**Spec:** `docs/superpowers/specs/2026-11-12-f1-prediction-app-design.md`

## Global Constraints

- Koszt 0 zł: tylko darmowe API (Jolpica, Open-Meteo bez klucza, OpenF1) i darmowy hosting (GitHub, Vercel). Użytkownik nie wpisuje niczego ręcznie; nadpisania w `config.py` są opcjonalne i domyślnie puste.
- Godziny zawsze w strefie `Europe/Warsaw`, niezależnie od strefy urządzenia.
- Nazwa aplikacji: "F1 Prediction App". Sezony: 2026 (kalibracja) i 2027 (na żywo). Liczba kierowców = liczba wpisów w `entries` (22 w 2026).
- Symulacja: `N_SIMULATIONS=10_000`, stałe ziarno `RANDOM_SEED`. Ten sam zestaw danych daje ten sam wynik.
- Czynnik bez danych zwraca `None` i jest pomijany (waga 0, aplikacja pokazuje "mało danych"). Nigdy nie zgadujemy.
- Awaria Jolpica = żaden plik w `public/data/` nie jest nadpisany, proces kończy się kodem 1. Brak opcjonalnego źródła = pole `None` i wpis w `meta.data_sources`.
- Ręczne nadpisanie z `config.py` zawsze wygrywa z wyliczoną wartością.
- Testy Pythona: `pytest -q` z korzenia (`pytest.ini`: `pythonpath = data-pipeline`). Testy frontendu: `npm test -- --run`.
- Po każdym zadaniu asystent pisze użytkownikowi 3–4 zdania prostym językiem: co właśnie powstało i po co.
- Commity kończą się linią `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.

## Review Focus

1. Sesja bez ustalonej godziny (TBC) → aplikacja pokazuje "do ustalenia", nie wywala się. (Zadania 3, 20, 21)
2. Tor bez historii lub bez telemetrii (nowy tor) → wartości domyślne/szacunek, `source` to mówi, nadpisanie wygrywa. (Zadania 6, 7)
3. Kierowca bez danych (debiutant, zmiana w trakcie sezonu) → ocena neutralna, brak NaN, szanse sumują się do 100%. (Zadania 8, 10, 14)
4. Wyścig za więcej niż 16 dni (brak prognozy) → `None` i "Brak prognozy". (Zadania 4, 21)
5. Brak nadchodzącej rundy (koniec sezonu, kalendarz nowego sezonu nieopublikowany) → komunikat zamiast pustego ekranu. (Zadania 16, 21)

---

## Struktura plików

```
pytest.ini  package.json  vite.config.js
data-pipeline/
  schemas.py  config.py  run.py  evaluation.py  tuning.py  requirements.txt
  data/track_profile_estimates.json
  fetch/{jolpica,openmeteo,openf1}.py
  factors/{base,track_stats,track_profile,car_pace,driver_form,track_history,reliability,wet_skill,practice_pace,car_track_fit}.py
  simulate/{qualifying,race,strategy}.py
tests/ (fixtures w tests/fixtures/)
public/data/
src/{App.jsx, lib/{time,data}.js, screens/, components/}
.github/workflows/update-data.yml
```

---

### Task 1: Szkielet projektu

**Files:** Create `.gitignore`, `pytest.ini`, `data-pipeline/requirements.txt`, `tests/test_smoke.py`; scaffold Vite React (`package.json`, `vite.config.js`, `src/App.jsx`, `src/App.test.jsx`)

**Interfaces:** Produces: `pytest -q`, `npm test -- --run`, `npm run build` działają.

- [ ] **Step 1:** `git init`; `npm create vite@latest . -- --template react`; dodaj vitest, @testing-library/react, jsdom; w `vite.config.js` `test.environment='jsdom'` i `process.env.TZ='America/New_York'` (dowód, że strefa urządzenia nie ma wpływu). Venv; `requirements.txt`: pydantic, numpy, httpx, pytest. `pytest.ini`: `pythonpath = data-pipeline`, `testpaths = tests`.
- [ ] **Step 2:** Testy: `test_pytest_runs` (`assert True`) i `src/App.test.jsx` "renders app title" (`getByText('F1 Prediction App')`). Uruchom, oczekiwany FAIL dla Reacta.
- [ ] **Step 3:** Wyrenderuj nagłówek w `App.jsx`.
- [ ] **Step 4:** Oba zestawy testów i `npm run build` przechodzą. Commit: `chore: project scaffold`.

### Task 2: Schematy i konfiguracja

**Files:** Create `data-pipeline/schemas.py`, `data-pipeline/config.py`, `tests/test_schemas.py`, `tests/test_config.py`

**Interfaces:** Produces w `schemas.py` (pydantic v2):
- `Session(name:str, start_utc:datetime|None)`; nazwy: `FP1 FP2 FP3 Qualifying Sprint SprintQualifying Race`
- `Race(season:int, round:int, name:str, circuit_id:str, country:str, lat:float, lon:float, sessions:list[Session], is_sprint:bool)`
- `DriverEntry(driver_id:str, code:str, name:str, team_id:str)`
- `WeatherForecast(rain_probability:float, temperature_c:float, fetched_at:datetime)`
- `TrackProfile(circuit_id:str, slow:float, medium:float, fast:float, straight_share:float, source:Literal['telemetry','estimate','manual'])` (slow+medium+fast = 1)
- `DriverProbability(driver_id:str, win:float, podium:float, points:float, expected_points:float, position_distribution:list[float])`
- `Strategy(stops:int, compounds:list[str])`; `StrategyPrediction(primary:Strategy, alternative:Strategy, rain_risk:float, confidence:Literal['low','medium','high'])`; `SafetyCarOdds(sc:float, vsc:float)`
- `StandingRow(id:str, name:str, points:float, wins:int, position:int)`; `Standings(drivers:list[StandingRow], constructors:list[StandingRow])`; `Calendar(season:int, races:list[Race])`
- `RaceEvaluation(round:int, winner_prob:float, winner_in_top3:bool, mean_abs_position_error:float, brier_win:float)`
- `WeightSnapshot(round:int, weights:dict[str,float])`
- `WeekendPayload(race:Race, weather:WeatherForecast|None, strategy:StrategyPrediction, safety_car:SafetyCarOdds, qualifying:list[DriverProbability], race_prediction:list[DriverProbability], factors_used:list[str], factors_skipped:list[str], low_data:bool)`; `WeekendResponse(status:Literal['ok','no_upcoming_race'], payload:WeekendPayload|None)`
- `ModelPayload(weights:dict[str,float], weight_history:list[WeightSnapshot], factors_used:list[str], factors_skipped:list[str], evaluation:list[RaceEvaluation])`
- `Meta(generated_at:datetime, season:int, data_sources:dict[str, Literal['ok','missing','failed']])`

`config.py` (wartości liczbowe to punkty startowe, do dostrojenia w Zadaniu 17): `SEASON=2027`, `N_SIMULATIONS=10_000`, `N_SIMULATIONS_TUNING=2_000`, `RANDOM_SEED=2027`, `FACTOR_WEIGHTS` (klucze: `car_pace, driver_form, track_history, practice_pace, weekend_shift, car_track_fit, wet_skill, reliability`), `GRID_BASE_WEIGHT`, `RACE_NOISE_BASE`, `SC_NOISE_FACTOR`, `PIT_NOISE`, `WEIGHT_BOUNDS: dict[str,tuple[float,float]]` (dla każdego klucza wag oraz `grid_base_weight`, `race_noise_base`), `LOCKED_WEIGHTS: set[str]` (puste), `TUNING_K=8`, `RECENCY_HALF_LIFE_YEARS=3`, `DEFAULT_SC_PROBABILITY=0.55`, `DEFAULT_VSC_PROBABILITY=0.25`, `DEFAULT_STOPS=2`, `RAIN_START_INTERMEDIATE=0.6`, `SC_ALT_THRESHOLD=0.6`, `EARLY_SEASON_ROUNDS=3`, `EARLY_SEASON_RISK_MULTIPLIER=1.3`, `WET_RACE_MM=1.0`, `WET_SHRINK_K=4`, `WET_MIN_RAIN_PROBABILITY=0.2`, `FIT_MIN_RACES=6`, `FIT_RIDGE=3.0`, `CORNER_SLOW_KMH=120`, `CORNER_FAST_KMH=220`, `CORNER_PROMINENCE_KMH=15`, `STRAIGHT_KMH=280`, `POINTS_TABLE=[25,18,15,12,10,8,6,4,2,1]`; opcjonalne nadpisania (puste): `TRACK_OVERRIDES: dict[str,TrackOverride]`, `TRACK_PROFILE_OVERRIDES: dict[str,TrackProfile]`, `WET_SKILL_OVERRIDES: dict[str,float]`. `TrackOverride(overtaking_difficulty:float|None, sc_probability:float|None)`.

- [ ] **Step 1:** Testy: `test_session_allows_tbc_time`, `test_every_weight_has_bounds_and_base_inside_them`, `test_profile_shares_sum_to_one`, `test_weekend_response_requires_payload_when_ok`.
- [ ] **Step 2:** FAIL. **Step 3:** Implementacja. **Step 4:** PASS. Commit: `feat: data schemas and config`.

### Task 3: Klient Jolpica

**Files:** Create `data-pipeline/fetch/jolpica.py`, `tests/test_jolpica.py`, `tests/fixtures/jolpica_*.json`

**Interfaces:** Produces w `schemas.py`: `HistoricResult(driver_id:str, team_id:str, grid:int, finish:int|None, status:str)`, `HistoricRace(season:int, round:int, circuit_id:str, date:date, lat:float, lon:float, results:list[HistoricResult])`. Klient:
- `class JolpicaClient: __init__(self, http: httpx.Client | None = None)`
- `.calendar(season:int) -> list[Race]`, `.entries(season:int) -> list[DriverEntry]`, `.race_results(season:int, round:int) -> HistoricRace`, `.standings(season:int) -> Standings`, `.circuit_history(circuit_id:str, seasons:list[int]) -> list[HistoricRace]`, `.season_results(season:int, up_to_round:int) -> list[HistoricRace]`

- [ ] **Step 1:** Fixtures z prawdziwych odpowiedzi (`https://api.jolpi.ca/ergast/f1/`, jednorazowo skryptem pomocniczym w `tests/`). Testy z `httpx.MockTransport`: `test_calendar_converts_to_utc`, `test_sprint_weekend_flag`, `test_missing_session_time_is_none`, `test_circuit_history_spans_seasons`, `test_season_results_stops_at_round`, `test_retries_then_raises_on_http_500` (3 próby).
- [ ] **Step 2:** FAIL. **Step 3:** Implementacja (brak godziny → `Session(start_utc=None)`, DNF → `finish=None`). **Step 4:** PASS. Commit: `feat: jolpica client`.

### Task 4: Klient Open-Meteo (prognoza i archiwum)

**Files:** Create `data-pipeline/fetch/openmeteo.py`, `tests/test_openmeteo.py`

**Interfaces:** Produces:
- `fetch_forecast(lat:float, lon:float, race_date:date, http: httpx.Client | None = None, today: date | None = None) -> WeatherForecast | None`
- `fetch_historical_rain_mm(lat:float, lon:float, day:date, http: httpx.Client | None = None) -> float | None` (suma opadów dnia z `archive-api.open-meteo.com`)
- `wet_races(races: list[HistoricRace], http=None) -> dict[tuple[int,int], bool]` (klucz `(season, round)`, mokro gdy opady ≥ `WET_RACE_MM`; brak danych = brak klucza)

- [ ] **Step 1:** Testy z `MockTransport`: `test_forecast_returns_rain_probability_as_fraction`, `test_forecast_none_beyond_16_days` (bez żądania HTTP), `test_forecast_none_on_http_error`, `test_historical_rain_sum`, `test_wet_races_flags_by_threshold_and_skips_missing`.
- [ ] **Step 2:** FAIL. **Step 3:** Implementacja. **Step 4:** PASS. Commit: `feat: open-meteo forecast and archive`.

### Task 5: Klient OpenF1 (opcjonalny)

**Files:** Create `data-pipeline/fetch/openf1.py`, `tests/test_openf1.py`, fixtures

**Interfaces:** Produces w `schemas.py`: `PracticeData(best_runs: dict[str, list[tuple[str,float]]])` (driver_id → `(compound, mediana_3_najlepszych_long_runów_s)`), `SafetyEvent(season:int, kind:Literal['SC','VSC'], lap:int)`, `TyreHistory(median_stops:int, dominant_compounds:list[str])`. Klient:
- `class OpenF1Client: __init__(self, http=None)`
- `.practice_pace(race:Race, entries:list[DriverEntry]) -> PracticeData | None`
- `.safety_events(circuit_id:str, races:list[Race]) -> dict[int, list[SafetyEvent]] | None`
- `.tyre_history(circuit_id:str, races:list[Race]) -> TyreHistory | None`
- `.speed_trace(race:Race) -> list[float] | None` (prędkość km/h na najszybszym okrążeniu kwalifikacji lub wyścigu, próbki w kolejności)

Dopasowanie sesji OpenF1 do `Race`: ten sam rok i data sesji w ±3 dni od daty wyścigu. Kierowcy przez `DriverEntry.code` = `name_acronym`.

- [ ] **Step 1:** Testy: `test_practice_pace_maps_codes_to_driver_ids`, `test_returns_none_on_http_error`, `test_returns_none_when_no_matching_session`, `test_safety_events_grouped_by_season`, `test_speed_trace_returns_samples_in_order`.
- [ ] **Step 2:** FAIL. **Step 3:** Implementacja (`https://api.openf1.org/v1/`; każdy błąd lub pusta odpowiedź → `None`). **Step 4:** PASS. Commit: `feat: openf1 client`.

### Task 6: Statystyki toru

**Files:** Create `data-pipeline/factors/track_stats.py`, `tests/test_track_stats.py`

**Interfaces:** Produces w `schemas.py`: `TrackStats(circuit_id:str, overtaking_difficulty:float, sc_probability:float, vsc_probability:float, sample_size:int, source:Literal['computed','default','manual'])`; oraz
- `default_track_stats(all_history:list[HistoricRace], ref_season:int) -> TrackStats`
- `compute_track_stats(circuit_id:str, history:list[HistoricRace], safety:dict[int,list[SafetyEvent]]|None, ref_season:int, override:TrackOverride|None, fallback:TrackStats) -> TrackStats`

Wzór: waga wyścigu `w = 0.5 ** ((ref_season − season)/RECENCY_HALF_LIFE_YEARS)`. Trudność = `0.4*pole_win_rate + 0.3*(1 − winner_outside_top3_rate) + 0.3*(1 − min(mean_abs_grid_change/6, 1))`, ważone `w`, zmiany liczone tylko po sklasyfikowanych. `sc_probability` = ważony odsetek wyścigów z ≥1 SC (z `safety`, a gdy `None` — z `fallback`). Nadpisanie ustawia `source='manual'`.

- [ ] **Step 1:** Testy: `test_monaco_like_history_harder_than_monza_like` (różnica > 0,3), `test_recent_races_weigh_more`, `test_empty_history_returns_fallback_default_zero_sample`, `test_manual_override_wins`, `test_sc_probability_from_events`, `test_sc_falls_back_without_safety_data`.
- [ ] **Step 2:** FAIL. **Step 3:** Implementacja. **Step 4:** PASS. Commit: `feat: track stats`.

### Task 7: Profil toru

**Files:** Create `data-pipeline/factors/track_profile.py`, `data-pipeline/data/track_profile_estimates.json`, `tests/test_track_profile.py`

**Interfaces:** Consumes: `TrackProfile`, progi z configu. Produces:
- `profile_from_speed_trace(circuit_id:str, speed_kmh:list[float]) -> TrackProfile | None` (zakręt = lokalne minimum o głębokości ≥ `CORNER_PROMINENCE_KMH`; wolny < `CORNER_SLOW_KMH`, szybki ≥ `CORNER_FAST_KMH`, reszta średni; `straight_share` = odsetek próbek ≥ `STRAIGHT_KMH`; `None` gdy nie wykryto zakrętów; `source='telemetry'`)
- `load_estimates() -> dict[str, TrackProfile]` (z pliku, `source='estimate'`)
- `get_profile(circuit_id:str, trace:list[float]|None, estimates:dict[str,TrackProfile], override:TrackProfile|None) -> TrackProfile | None` (kolejność: nadpisanie, telemetria, szacunek, inaczej `None`)

Plik szacunków: wpisy dla torów kalendarza 2026/2027 z ogólnej wiedzy asystenta, każdy oznaczony jako szacunek; użytkownik jest o tym informowany przy oddaniu zadania.

- [ ] **Step 1:** Testy na syntetycznych przebiegach: `test_counts_slow_medium_fast_corners`, `test_flat_trace_returns_none`, `test_get_profile_priority_override_telemetry_estimate`, `test_unknown_circuit_without_data_returns_none`, `test_estimates_shares_sum_to_one`.
- [ ] **Step 2:** FAIL. **Step 3:** Implementacja. **Step 4:** PASS. Commit: `feat: track profiles`.

### Task 8: Szkielet czynników i łączenie

**Files:** Create `data-pipeline/factors/base.py`, `tests/test_factors_base.py`

**Interfaces:** Produces:
- `RaceContext` (frozen dataclass): `race:Race, entries:list[DriverEntry], history:list[HistoricRace]` (tylko rundy < bieżącej), `circuit_history:list[HistoricRace], wet:dict[tuple[int,int],bool], weather:WeatherForecast|None, practice:PracticeData|None, grid:dict[str,int]|None, track:TrackStats, profile:TrackProfile|None, profiles:dict[str,TrackProfile]` (profile torów już rozegranych rund sezonu), `season:int`
- `class Factor(Protocol): name:str; def score(self, ctx:RaceContext) -> dict[str,float] | None` (wyższa wartość = lepiej)
- `CombinedStrength(strength:dict[str,float], used:list[str], skipped:list[str], low_data:bool)`
- `combine(ctx:RaceContext, factors:list[Factor], weights:dict[str,float]) -> CombinedStrength`
- `zscore(values:dict[str,float]) -> dict[str,float]` (wartości stałe → same zera)

Reguły: wagi używanych czynników renormalizowane do sumy 1; kierowca nieobecny w wyniku czynnika dostaje 0; `low_data = len(used) < 3`.

- [ ] **Step 1:** Testy: `test_none_factor_skipped_and_weights_renormalized`, `test_driver_missing_from_factor_gets_neutral_and_values_finite`, `test_all_factors_none_gives_zero_strength_and_low_data`, `test_zscore_constant_input_is_zeros`.
- [ ] **Step 2:** FAIL. **Step 3:** Implementacja. **Step 4:** PASS. Commit: `feat: factor framework`.

### Task 9: Czynniki oparte na wynikach

**Files:** Create `factors/{car_pace,driver_form,track_history,reliability}.py`, `tests/test_result_factors.py`

**Interfaces:** Produces klasy `CarPace`, `DriverForm`, `TrackHistory`, `Reliability` (`name` = klucz z `FACTOR_WEIGHTS`) oraz `dnf_rates(ctx:RaceContext) -> dict[str,float]` (prawdopodobieństwo DNF 0–1, wygładzone ku średniej przy małej próbie; w `reliability.py`). Oraz `team_result_z(ctx:RaceContext, race:HistoricRace) -> dict[str,float]` w `car_pace.py` (z-score zespołu w jednym wyścigu, wyższy = lepszy; używa go Zadanie 12).

Podejście: `CarPace` = średnia punktów zespołu na wyścig w sezonie z wagą recency; `DriverForm` = ostatnie 5 rund; `TrackHistory` = ważona średnia pozycja końcowa kierowcy na torze, `None` gdy żaden kierowca nie ma historii; `Reliability` = minus wskaźnik awarii zespołu.

- [ ] **Step 1:** Testy: `test_car_pace_ranks_strongest_team_first`, `test_driver_form_uses_only_last_five_rounds`, `test_track_history_none_without_history`, `test_track_history_skips_driver_with_no_starts`, `test_reliability_penalizes_high_dnf_team`, `test_dnf_rates_in_0_1_for_rookie`.
- [ ] **Step 2:** FAIL. **Step 3:** Implementacja. **Step 4:** PASS. Commit: `feat: result-based factors`.

### Task 10: Umiejętność deszczowa

**Files:** Create `factors/wet_skill.py`, `tests/test_wet_skill.py`

**Interfaces:** Produces: `compute_wet_skill(races:list[HistoricRace], wet:dict[tuple[int,int],bool], entries:list[DriverEntry]) -> dict[str,float]` (różnica "wynik minus wynik partnera z zespołu" w wyścigach mokrych względem suchych, ściągnięta wzorem `n/(n+WET_SHRINK_K)`; kierowca bez mokrych wyścigów = 0) oraz klasa `WetSkill` (`name='wet_skill'`): `None`, gdy `ctx.weather is None`, `rain_probability < WET_MIN_RAIN_PROBABILITY` lub brak mokrych wyścigów w historii; w przeciwnym razie `rain_probability × skill`; wartość z `WET_SKILL_OVERRIDES` wygrywa.

- [ ] **Step 1:** Testy: `test_teammate_comparison_removes_car_effect` (obaj kierowcy zespołu mają ten sam bolid; lepszy w deszczu dostaje dodatnią ocenę), `test_rookie_gets_zero`, `test_shrinks_with_few_wet_races`, `test_none_when_dry_forecast`, `test_none_without_forecast`, `test_override_wins`.
- [ ] **Step 2:** FAIL. **Step 3:** Implementacja. **Step 4:** PASS. Commit: `feat: wet skill`.

### Task 11: Tempo treningowe i zmiana formy w weekendzie

**Files:** Create `factors/practice_pace.py`, `tests/test_practice_factors.py`

**Interfaces:** Produces: `adjusted_practice(practice:PracticeData) -> dict[str,float]` (driver_id → czas sprowadzony do wspólnej mieszanki; offset mieszanek = średnia różnica kierowców, którzy jechali na obu); klasa `PracticePace` (`name='practice_pace'`): `None` bez `ctx.practice`, inaczej z-score z odwróconym znakiem (szybciej = lepiej); klasa `WeekendShift` (`name='weekend_shift'`): `None` bez `ctx.practice` lub gdy `CarPace` nie ma danych; ocena zespołu = z-score tempa treningowego minus z-score `CarPace`, obcięta do ±2, przypisana jego kierowcom.

- [ ] **Step 1:** Testy: `test_practice_none_without_data`, `test_adjusts_for_compound` (kierowca na miękkich nie wygrywa tylko dzięki mieszance), `test_weekend_shift_positive_when_team_faster_than_usual`, `test_weekend_shift_clipped`, `test_weekend_shift_none_without_practice`.
- [ ] **Step 2:** FAIL. **Step 3:** Implementacja. **Step 4:** PASS. Commit: `feat: practice factors`.

### Task 12: Dopasowanie bolidu do toru

**Files:** Create `factors/car_track_fit.py`, `tests/test_car_track_fit.py`

**Interfaces:** Consumes: `team_result_z`, `ctx.profiles`, `ctx.profile`. Produces: klasa `CarTrackFit` (`name='car_track_fit'`): dla każdego zespołu regresja grzbietowa (`FIT_RIDGE`) `team_result_z ~ wycentrowany profil [slow, medium, fast]` na rozegranych rundach sezonu mających profil; ocena = przewidywanie dla wycentrowanego `ctx.profile`; `None`, gdy `ctx.profile is None` lub mniej niż `FIT_MIN_RACES` rund z profilem.

- [ ] **Step 1:** Testy na syntetycznych sezonach: `test_team_strong_on_fast_corners_scores_higher_on_fast_track`, `test_none_below_min_races`, `test_none_without_current_profile`, `test_ridge_shrinks_small_effects`.
- [ ] **Step 2:** FAIL. **Step 3:** Implementacja. **Step 4:** PASS. Commit: `feat: car-track fit`.

### Task 13: Model kwalifikacji

**Files:** Create `data-pipeline/simulate/qualifying.py`, `tests/test_qualifying.py`

**Interfaces:** Produces: `QualifyingPrediction(probabilities:list[DriverProbability], predicted_grid:dict[str,int])`; `predict_qualifying(strength:dict[str,float], n:int = config.N_SIMULATIONS, seed:int = config.RANDOM_SEED, noise:float = 0.8) -> QualifyingPrediction` (`win` = szansa na pole; `points`/`expected_points` = 0; `predicted_grid` z mediany pozycji).

- [ ] **Step 1:** Testy: `test_strongest_driver_highest_pole_probability`, `test_same_seed_same_result`, `test_pole_probabilities_sum_to_one`, `test_each_position_distribution_sums_to_one`, `test_predicted_grid_is_permutation`.
- [ ] **Step 2:** FAIL. **Step 3:** Implementacja (numpy). **Step 4:** PASS. Commit: `feat: qualifying model`.

### Task 14: Symulacja wyścigu

**Files:** Create `data-pipeline/simulate/race.py`, `tests/test_race.py`

**Interfaces:** Produces:
- `simulate_race(strength:dict[str,float], grid:dict[str,int], track:TrackStats, dnf:dict[str,float], stops:int, n:int = config.N_SIMULATIONS, seed:int = config.RANDOM_SEED, grid_weight:float = config.GRID_BASE_WEIGHT, noise_base:float = config.RACE_NOISE_BASE) -> list[DriverProbability]`
- `apply_early_season(dnf:dict[str,float], track:TrackStats, round:int) -> tuple[dict[str,float], TrackStats]` (dla `round <= EARLY_SEASON_ROUNDS` mnoży DNF i `sc_probability` przez `EARLY_SEASON_RISK_MULTIPLIER`, wynik ograniczony do 1)

Tempo w jednym rozegraniu: `strength − grid_weight × track.overtaking_difficulty × (grid_pos − 1) + N(0, σ)`, `σ = noise_base × (1 + SC_NOISE_FACTOR × track.sc_probability) × (1 + PIT_NOISE × stops)`; DNF losowany z `dnf[driver]` (kierowca bez wpisu dostaje średnią wartość `dnf`); punkty z `POINTS_TABLE`; `podium`/`points` = odsetek rozegrań w top 3 / top 10; długość `position_distribution` = liczba kierowców.

- [ ] **Step 1:** Testy: `test_pole_matters_more_on_monaco_than_monza` (identyczne `strength`, trudność 0.9 vs 0.1), `test_win_probabilities_sum_to_one`, `test_dnf_probability_one_scores_zero`, `test_driver_missing_from_dnf_gets_average_and_no_nan`, `test_works_with_22_drivers`, `test_same_seed_same_result`, `test_early_season_raises_risk_only_in_early_rounds`.
- [ ] **Step 2:** FAIL. **Step 3:** Implementacja. **Step 4:** PASS. Commit: `feat: race simulation`.

### Task 15: Strategia opon

**Files:** Create `data-pipeline/simulate/strategy.py`, `tests/test_strategy.py`

**Interfaces:** Produces: `predict_strategy(track:TrackStats, weather:WeatherForecast|None, tyre_history:TyreHistory|None) -> StrategyPrediction`.

Reguły: liczba stopów = `tyre_history.median_stops` lub `DEFAULT_STOPS` (wtedy `confidence='low'`); `rain_probability ≥ RAIN_START_INTERMEDIATE` → `primary` startuje na `INTERMEDIATE`, `rain_risk` = `rain_probability`; `track.sc_probability ≥ SC_ALT_THRESHOLD` → `alternative` ma `stops−1` (min. 1), inaczej `stops+1`.

- [ ] **Step 1:** Testy: `test_default_stops_low_confidence_without_history`, `test_uses_history_median_stops`, `test_heavy_rain_starts_on_intermediates`, `test_high_sc_odds_alternative_has_fewer_stops`, `test_works_without_weather`.
- [ ] **Step 2:** FAIL. **Step 3:** Implementacja. **Step 4:** PASS. Commit: `feat: tyre strategy`.

### Task 16: Pipeline i pliki JSON

**Files:** Create `data-pipeline/run.py`, `tests/test_pipeline.py`

**Interfaces:** Consumes: wszystko wyżej. Produces:
- `Clients` (dataclass): `jolpica:JolpicaClient`, `forecast:Callable[[float,float,date], WeatherForecast|None]` (domyślnie `fetch_forecast`), `wet:Callable[[list[HistoricRace]], dict[tuple[int,int],bool]]` (domyślnie `wet_races`), `openf1:OpenF1Client`; testy podstawiają atrapy
- `select_next_race(races:list[Race], now_utc:datetime) -> Race | None` (pierwsza runda, której sesja Race + 3 h jest w przyszłości; runda bez godzin traktowana jako nadchodząca)
- `build_context(race, entries, history, circuit_history, wet, weather, practice, grid, track, profile, profiles, as_of_round:int) -> RaceContext` (odfiltrowuje wyścigi `round >= as_of_round`)
- `run_pipeline(out_dir:Path, season:int, now_utc:datetime, clients:Clients) -> Meta` — zapisuje `meta.json`, `calendar.json`, `standings.json`, `weekend.json` (`WeekendResponse`), `model.json` (`ModelPayload`); wagi czyta z `weights.json`, a gdy go nie ma, z `config.FACTOR_WEIGHTS`. Zapis: walidacja schematem, plik tymczasowy, `os.replace`. CLI: `python data-pipeline/run.py --out public/data`.

Siatka: rzeczywiste wyniki kwalifikacji, jeśli już są, inaczej `predict_qualifying`. Przed symulacją wywołaj `apply_early_season`.

- [ ] **Step 1:** Testy (atrapy klientów): `test_writes_all_files_with_valid_schema`, `test_jolpica_failure_leaves_files_untouched_and_exits_1`, `test_openf1_missing_marks_source_missing_and_low_data`, `test_no_upcoming_race_writes_no_upcoming_race_status`, `test_cancelled_race_with_empty_results_does_not_crash`, `test_context_excludes_future_rounds`, `test_uses_real_grid_after_qualifying`, `test_reads_weights_json_when_present`.
- [ ] **Step 2:** FAIL. **Step 3:** Implementacja. **Step 4:** PASS; uruchom raz na żywych API z `--out /tmp/f1-out` i obejrzyj `weekend.json`. Commit: `feat: pipeline`.

### Task 17: Ocena modelu i test wsteczny na 2026

**Files:** Create `data-pipeline/evaluation.py`, `tests/test_evaluation.py`; Modify `run.py` (zapis `evaluation` do `model.json`)

**Interfaces:** Consumes: `RaceEvaluation`. Produces: `evaluate(round:int, prediction:list[DriverProbability], actual_finish:dict[str,int|None]) -> RaceEvaluation`; `backtest(season:int, clients:Clients, weights:dict[str,float], n:int = config.N_SIMULATIONS_TUNING) -> list[RaceEvaluation]` (dla każdej rundy kontekst z `as_of_round=round`). CLI `python data-pipeline/evaluation.py --season 2026`. Po przebiegu dostrój wartości bazowe w `config.py` i uzasadnij w komentarzu.

- [ ] **Step 1:** Testy: `test_perfect_prediction_zero_error_and_top3_true`, `test_winner_with_zero_probability_has_high_brier`, `test_dnf_excluded_from_position_error`, `test_backtest_never_uses_data_from_predicted_round`.
- [ ] **Step 2:** FAIL. **Step 3:** Implementacja. **Step 4:** PASS, uruchom backtest. Commit: `feat: evaluation and 2026 backtest`.

### Task 18: Auto-wagi

**Files:** Create `data-pipeline/tuning.py`, `tests/test_tuning.py`; Modify `run.py` (po wyścigu wywołuje strojenie i zapisuje `weights.json`)

**Interfaces:** Produces: `tune_weights(base:dict[str,float], bounds:dict[str,tuple[float,float]], locked:set[str], rounds_played:int, evaluate:Callable[[dict[str,float]], float]) -> dict[str,float]` — `evaluate` zwraca średni Brier na rozegranych rundach (mniejszy = lepiej). Wyszukiwanie współrzędnych (po jednej wadze, siatka w granicach), wynik `new = base + λ·(best − base)` z `λ = rounds_played/(rounds_played + TUNING_K)`; przy `rounds_played < 3` zwraca `base`. `weights.json` zawiera bieżące wagi i `history: list[WeightSnapshot]`. Strojone klucze: wszystkie z `FACTOR_WEIGHTS` oraz `grid_base_weight` i `race_noise_base`.

- [ ] **Step 1:** Testy: `test_returns_base_below_three_rounds`, `test_weights_stay_inside_bounds`, `test_locked_weights_untouched`, `test_moves_toward_predictive_factor` (syntetyczny `evaluate`, w którym jeden czynnik jest idealnym predyktorem → jego waga rośnie, ale o ułamek λ), `test_history_appended_each_round`.
- [ ] **Step 2:** FAIL. **Step 3:** Implementacja (symulacje w strojeniu z `N_SIMULATIONS_TUNING`). **Step 4:** PASS. Commit: `feat: auto weight tuning`.

### Task 19: GitHub Actions

**Files:** Create `.github/workflows/update-data.yml`

**Interfaces:** Consumes: `python data-pipeline/run.py --out public/data`.

Wyzwalacze: `workflow_dispatch`; `cron: '0 */6 * * *'`; `cron: '*/30 * * * 5,6,0'`. `concurrency` z anulowaniem poprzednich, `permissions: contents: write`. Kroki: checkout, `setup-python` 3.12 z cache pip, instalacja, uruchomienie, commit i push tylko przy zmianie `public/data/` (autor `github-actions[bot]`). Repozytorium publiczne.

- [ ] **Step 1:** Zwaliduj składnię (`python -c "import yaml; yaml.safe_load(open('.github/workflows/update-data.yml'))"`). Oczekiwane: brak błędów.
- [ ] **Step 2:** Użytkownik zakłada repozytorium (asystent prowadzi), push, ręczne "Run workflow". Oczekiwane: zielony przebieg i commit z nowymi JSON.
- [ ] **Step 3:** Commit: `ci: scheduled data update`.

### Task 20: Podstawy frontendu (czas, dane, nawigacja, PWA)

**Files:** Create `src/lib/time.js`, `src/lib/data.js`, `src/lib/time.test.js`; Modify `src/App.jsx`, `src/App.test.jsx`, `vite.config.js`, `public/icons/*`

**Interfaces:** Produces:
- `formatWarsaw(isoUtc:string|null, opts?:Intl.DateTimeFormatOptions) -> string` (`Europe/Warsaw`; `null` → `"do ustalenia"`)
- `useData(file:string) -> { data, error, loading }` (`fetch('/data/'+file)`)
- `App`: dolne zakładki Weekend / Klasyfikacje / Kalendarz / Model (`useState`, bez routera), pasek "Dane z: <generated_at>" z `meta.json`
- manifest PWA: `name "F1 Prediction App"`, `display: standalone`, ikony 192 i 512; `vite-plugin-pwa` z NetworkFirst dla `/data/*.json`

- [ ] **Step 1:** Testy: `formatWarsaw('2027-07-04T13:00:00Z')` → 15:00; `'2027-01-10T13:00:00Z'` → 14:00; `'2027-03-28T00:30:00Z'` i `'2027-03-28T01:30:00Z'` → 01:30 i 03:30 (zmiana czasu); `formatWarsaw(null)` → `"do ustalenia"`; klik w "Klasyfikacje" zmienia ekran.
- [ ] **Step 2:** FAIL. **Step 3:** Implementacja. **Step 4:** PASS + `npm run build` generuje service worker i manifest. Commit: `feat: frontend foundation and PWA`.

### Task 21: Ekran Weekend

**Files:** Create `src/screens/Weekend.jsx`, `src/components/{SessionList,WeatherCard,StrategyCard,ProbabilityTable}.jsx`, `src/screens/Weekend.test.jsx`, `src/test/weekend.sample.json`

**Interfaces:** Consumes: `useData('weekend.json')`, `formatWarsaw`. `ProbabilityTable` props: `rows:DriverProbability[]`, `nameById:Record<string,string>`, `mode:'qualifying'|'race'` (przełącznik Kwalifikacje/Wyścig, sortowanie malejąco po `win`, szansa jako `28%` z paskiem).

- [ ] **Step 1:** Testy na `weekend.sample.json`: `shows_sessions_in_warsaw_time`, `shows_tbc_for_missing_session_time`, `shows_no_forecast_message_when_weather_null`, `shows_low_data_banner`, `shows_season_over_message_when_no_upcoming_race`, `formats_probability_as_percent_sorted_desc`, `toggle_switches_between_qualifying_and_race`.
- [ ] **Step 2:** FAIL. **Step 3:** Implementacja (mobile-first, ~375 px). **Step 4:** PASS. Commit: `feat: weekend screen`.

### Task 22: Klasyfikacje i Kalendarz

**Files:** Create `src/screens/{Standings,Calendar}.jsx` i testy

**Interfaces:** `Standings`: przełącznik Kierowcy/Zespoły z `standings.json`. `Calendar`: lista rund z `calendar.json`; klik w rundę pokazuje `SessionList`, runda `is_sprint` ma znacznik "Sprint".

- [ ] **Step 1:** Testy: `standings_switches_drivers_and_constructors`, `calendar_marks_sprint_rounds`, `calendar_expands_sessions_on_click`, `calendar_shows_tbc_for_missing_times`.
- [ ] **Step 2:** FAIL. **Step 3:** Implementacja. **Step 4:** PASS. Commit: `feat: standings and calendar screens`.

### Task 23: Ekran Model

**Files:** Create `src/screens/ModelInfo.jsx` i test

**Interfaces:** Consumes: `model.json`. Pokazuje wagi czynników (paski) z historią zmian z `weight_history` (np. "forma kierowcy: 0,20 → 0,27 po rundzie 14"), czynniki użyte i pominięte (powód "brak danych") oraz tabelę trafności z `evaluation`.

- [ ] **Step 1:** Testy: `lists_used_and_skipped_factors`, `shows_weight_change_between_rounds`, `shows_evaluation_rows`, `shows_empty_state_without_evaluation`.
- [ ] **Step 2:** FAIL. **Step 3:** Implementacja. **Step 4:** PASS. Commit: `feat: model screen`.

### Task 24: Wdrożenie na Vercel, test na telefonie, README

**Files:** Create `README.md` (po polsku: jak działa aplikacja, jak ustawić opcjonalne nadpisania, jak zablokować wagę, jak dodać nowy czynnik)

- [ ] **Step 1:** Użytkownik zakłada konto Vercel (logowanie przez GitHub), importuje repozytorium (Vite, `npm run build`, katalog `dist`). Oczekiwane: publiczny adres pokazuje dane.
- [ ] **Step 2:** Test na Androidzie (Chrome → "Zainstaluj aplikację"): ikona na ekranie, uruchomienie pełnoekranowe, po włączeniu trybu samolotowego widać ostatnie dane.
- [ ] **Step 3:** Sprawdź, że commit robota z nowymi JSON uruchamia wdrożenie na Vercel. Commit README: `docs: readme`.

---

## Self-review

- **Pokrycie speca:** kalendarz i czas polski (3, 20–22); pogoda (4, 10, 21); czynniki: bolid, forma, historia toru, niezawodność (9), deszcz (10), trening i zmiana formy (11), dopasowanie do toru (12), pozycja startowa (14); statystyki i profile torów (6, 7); kwalifikacje (13); wyścig i początek sezonu (14); strategia (15); auto-wagi (18); ocena i backtest (17, 23); harmonogram (19); błędy i fallbacki (16); hosting i PWA (20, 24).
- **Spójność typów:** `RaceEvaluation`, `WeightSnapshot`, `TrackProfile` i `TrackStats` zdefiniowane w Zadaniach 2 i 6 przed użyciem; `RaceContext` (Zadanie 8) zawiera `profile`, `profiles` i `wet` używane w Zadaniach 10–12; `team_result_z` z Zadania 9 używane w 12.
- **Zmiana względem poprzedniej wersji:** ręczne poprawki bolidów i umiejętności deszczowe zastąpione czynnikami wyliczanymi z danych; dodane profile torów, dopasowanie bolidu do toru i auto-wagi.
