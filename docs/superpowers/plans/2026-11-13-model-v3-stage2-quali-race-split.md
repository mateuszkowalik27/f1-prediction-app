# Model v3, etap 2: osobne kwalifikacje i wyścig — plan wdrożenia

> **Dla wykonawcy:** zadania po kolei, TDD (test najpierw, obejrzyj porażkę, potem kod). Kroki mają składnię `- [ ]`.

**Cel:** kwalifikacje i wyścig mają własne siły i własne zestawy wag. Kwalifikacje wpływają na wyścig tylko przez pozycję
startową. `quali_gap` służy kwalifikacjom, a wyścigu już nie.

**Architektura:** nowy słownik `QUALI_FACTOR_WEIGHTS` w `config.py` (nazwy czynników bez prefiksu); `default_weights()` dokłada je
jako klucze `q_<czynnik>` oraz `quali_noise`. Dzięki temu `weights.json`, strojenie i raporty działają bez zmian (klucze `q_*`
nie mają granic, więc strojenie ich nie rusza). `factors/base.py` dostaje `combine_side(...)` (siła wyścigowa albo kwalifikacyjna).
`simulate_race` dostaje opcjonalne `quali_strength` do losowania siatki, gdy kwalifikacji jeszcze nie było. Pipeline i ocena używają
dwóch sił. Tryb porównawczy `separate=False` odtwarza stare, wspólne zachowanie do testów A/B.

**Stos:** Python 3.14 lokalnie (3.12 w CI), numpy, pydantic 2, pytest.

**Spec:** `docs/superpowers/specs/2026-11-13-model-v3-design.md` (sekcja 4).

## Ograniczenia globalne
- Zgodność wstecz: istniejące testy zielone; UI bez zmian.
- Kwalifikacje wpływają na wyścig wyłącznie przez siatkę (oficjalną, z karami, gdy znana; losowaną z siły kwalifikacyjnej, gdy nie).
- Wagi `q_*` są ustawione ręcznie i nie są strojone automatycznie; szum kwalifikacji jest dobierany na sezonach treningowych
  2022-2023, a oceniany na testowych 2024-2026 (bez przecieku).

## Przegląd fokusu
- Czynnik bez danych w kwalifikacjach (np. treningi w teście wstecznym): pomijany jak dotąd (`None`).
- Wszystkie wagi kwalifikacyjne równe 0 dla dostępnych czynników: siła zerowa, nie błąd (wynik jak "sama siatka").
- Stary `weights.json` bez kluczy `q_*`: uzupełniany wartościami domyślnymi (`_load_weights`).

---

### Zadanie 1: wagi i `combine_side`

**Pliki:** `data-pipeline/config.py`, `data-pipeline/factors/base.py`, testy `tests/test_config.py`, `tests/test_factors_base.py`.

**Interfejsy:**
- `config.QUALI_FACTOR_WEIGHTS: dict[str, float]` — wagi siły kwalifikacyjnej (klucze = nazwy czynników): początkowo
  `car_pace 0.25, quali_gap 0.40, car_track_fit 0.10, practice_pace 0.10, track_history 0.05, wet_skill 0.05, driver_form 0.05`,
  pozostałe 0.
- `config.RACE_FACTOR_WEIGHTS`: bez zmian (`FACTOR_WEIGHTS`), ale `quali_gap` = 0.0 i dodany do `LOCKED_WEIGHTS`.
- `config.default_weights()` zwraca także `q_<czynnik>` oraz `quali_noise` (domyślnie `QUALIFYING_NOISE`); `quali_noise` ma
  granice w `WEIGHT_BOUNDS` (0,3 – 1,5) i jest w `LOCKED_WEIGHTS` (strojone ręcznie, nie przez robota).
- `combine_side(ctx, factors, weights, side: Literal["race", "quali"]) -> CombinedStrength`: dla `quali` bierze wagi
  `weights["q_" + name]` (brak klucza = 0), dla `race` zwykłe `weights[name]`.

- [ ] Testy: `default_weights()` zawiera `q_quali_gap` i `quali_noise`; w wadze wyścigowej `quali_gap == 0`; `combine_side` dla
  `quali` używa tylko wag `q_*` (czynnik z `q_x = 0` jest pomijany jak przy wadze 0); brak klucza `q_*` = czynnik pomijany.
- [ ] RED → implementacja → GREEN → komplet testów → commit.

### Zadanie 2: losowanie siatki z siły kwalifikacyjnej

**Pliki:** `data-pipeline/simulate/race.py`, test `tests/test_race.py`.

**Interfejsy:** `simulate_race(..., quali_strength: dict[str, float] | None = None)`: gdy `grid is None`, siatka jest losowana z
`quali_strength` (jeśli podane) zamiast z siły wyścigowej; szum kwalifikacji z `qualifying_noise` jak dotąd.

- [ ] Test: dwóch kierowców, siła wyścigowa wskazuje A, siła kwalifikacyjna wskazuje B, `grid=None`: przy dużym szumie wyścigu małym
  i silnej różnicy w kwalifikacji B startuje częściej z przodu, więc jego szansa na wygraną jest większa niż przy
  `quali_strength=None`; bez `quali_strength` wynik identyczny jak dotąd (zgodność wstecz).
- [ ] RED → implementacja → GREEN → commit.

### Zadanie 3: ocena z dwiema siłami

**Pliki:** `data-pipeline/evaluation.py`, `tests/test_evaluation.py`.

**Interfejsy:**
- `_predict_case(case, weights, n, grid_known=True, separate=True)`: siła wyścigowa z `combine_side(..., "race")`; przy
  `grid_known=False` i `separate=True` siatka losowana z `combine_side(..., "quali")` (przekazane jako `quali_strength`).
- `evaluate_levels(cases, weights, n, separate=True)`: poziom `quali` używa siły kwalifikacyjnej i `weights["quali_noise"]`
  (`separate=True`) albo siły wyścigowej i `QUALIFYING_NOISE` (`separate=False`, stare zachowanie).

- [ ] Testy: `separate=True` vs `False` dają różne `rps_quali`, gdy wagi `q_*` różnią się od wyścigowych; `quali_noise` z wag jest
  używany (inna wartość zmienia wynik); `separate=False` odtwarza dotychczasowe liczby (test regresji na tych samych atrapach).
- [ ] RED → implementacja → GREEN → komplet testów → commit.

### Zadanie 4: pipeline

**Pliki:** `data-pipeline/run.py` (`_predict_weekend`), testy `tests/test_pipeline.py`.

- [ ] `_predict_weekend`: `race_strength = combine_side(..., "race")`, `quali_strength = combine_side(..., "quali")`;
  `predict_qualifying(quali_strength.strength, noise=weights["quali_noise"])`; `simulate_race(race_strength.strength, actual_grid, ...,
  quali_strength=quali_strength.strength)`; `factors_used/skipped` i `low_data` z siły wyścigowej (jak dotąd).
- [ ] Test: czynnik tylko w wadze kwalifikacyjnej (np. `quali_gap`) nie pojawia się w `factors_used` wyścigu; ranking
  kwalifikacji w `weekend.json` zależy od wag `q_*` (zmiana `q_quali_gap` zmienia kolejność w atrapach).
- [ ] RED → implementacja → GREEN → komplet testów → commit.

### Zadanie 5: szum kwalifikacji i pomiar A/B

**Pliki:** `data-pipeline/oos.py` (nowy raport), `data-pipeline/config.py`, `README.md`.

- [ ] `quali_noise_scan(cases, weights, noises) -> dict[float, float]`: średni `rps_quali` dla listy wartości szumu.
  Wartość wybieramy na sezonach 2022-2023 (min RPS kwalifikacji), potem wpisujemy do `QUALIFYING_NOISE`.
- [ ] `oos.py` (raport bez argumentów) dodaje porównanie `separate=True` vs `False` (różnice z przedziałami na trzech poziomach).
- [ ] Uruchom (ręcznie): `python data-pipeline/oos.py`. Zapisz wyniki w komentarzu `config.py` i w README ("Etap 2").
  Kryterium sukcesu: poziom `quali` wyraźnie lepszy (przedział poniżej zera) przy braku wyraźnego pogorszenia `pre` i `post`;
  inaczej wynik "niejednoznaczny" i zostaje opis w README bez zmiany zachowania (rozstrzygamy po etapie 3).
- [ ] Commit.

### Zadanie 6: dane i domknięcie

- [ ] Przebieg robota lokalnie (`python data-pipeline/run.py --out public/data`), kalibracja (`python data-pipeline/calibrate.py`).
- [ ] Pełny zestaw testów (`pytest`, `vitest`) zielony; README: sekcja o osobnych siłach; commit.

## Weryfikacja końcowa etapu
Testy zielone; `weekend.json` ma kwalifikacje z siły kwalifikacyjnej; README i `config.py` zawierają wynik A/B i wybrany szum.
