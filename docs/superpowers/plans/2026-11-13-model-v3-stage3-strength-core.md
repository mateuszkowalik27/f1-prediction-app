# Model v3, etap 3: rdzeń siły — plan wdrożenia

> **Dla wykonawcy:** zadania po kolei, TDD (test najpierw, obejrzyj porażkę, potem kod). Kroki mają składnię `- [ ]`.

**Cel:** zastąpić "średnią punktów" (`car_pace`, `driver_form`) dynamicznymi ocenami opartymi na całej kolejności mety: auto i
kierowca osobno, awarie bez wpływu na ocenę umiejętności, plus czyste tempo okrążeń i ocena kwalifikacyjna z różnic czasów.
Każdy nowy czynnik przechodzi bramkę nową miarą (RPS, przedziały) z etapu 1; stare czynniki zostają w kodzie do porównań.

**Architektura:** nowy moduł `ratings.py` (czysta logika: aktualizacja Plackett-Luce po każdym wyścigu, `car` + `driver`,
przejście między sezonami, filtr statusów). `RaceContext` dostaje `long_history` (wyniki z ośmiu sezonów wstecz do "rozgrzewki"
ocen; w teście wstecznym i w robocie ta sama reguła, bez przecieku z przyszłości). Nowe czynniki `rating_race`, `pace_race`,
`rating_quali`. `oos.py` dostaje bramkę wariantów (`--variant`), która porównuje wagi bazowe z wagami z podmienionymi czynnikami.

**Stos:** Python 3.14 lokalnie (3.12 w CI), numpy, pydantic 2, pytest.

**Spec:** `docs/superpowers/specs/2026-11-13-model-v3-design.md` (sekcja 5).

## Ograniczenia globalne
- Zgodność wstecz: istniejące testy zielone; stare czynniki nie są usuwane; interfejs aplikacji bez zmian.
- Bez przecieku: ocena wyścigu `R` powstaje wyłącznie z wyników wcześniejszych niż `R` (jak cała historia w kontekście).
- Hiperparametry ocen (tempo uczenia, przechodzenie między sezonami) wybierane na sezonach 2022-2023, sprawdzane na 2024-2026.
- Kierowcy bez dojechania do mety (awaria, wypadek) są wyłączani z rankingu danego wyścigu (neutralnie); skłonność do awarii
  zostaje w `reliability`.

## Przegląd fokusu
- Nowy kierowca lub zespół bez historii: ocena domyślna 0 (średnia), bez błędu.
- Za mało danych (mniej niż 3 wyścigi w `long_history`): czynnik zwraca `None`.
- Wyścig z jednym sklasyfikowanym kierowcą albo bez sklasyfikowanych: pomijany przy aktualizacji.

---

### Zadanie 1: silnik ocen `ratings.py`

**Pliki:** utwórz `data-pipeline/ratings.py`, test `tests/test_ratings.py`.

**Interfejsy:**
- `finished(status: str) -> bool`: `True` dla "Finished" i okrążonych ("+1 Lap", "+2 Laps"); reszta (awarie, wypadki, DSQ) `False`.
- `@dataclass class Ratings: car: dict[str, float]; driver: dict[str, float]`; `strength(driver_id, team_id) -> float` (`car + driver`, brak = 0).
- `update_race(ratings, order: list[tuple[str, str]], eta_car: float, eta_driver: float) -> None`: `order` to
  `(driver_id, team_id)` od najlepszego do najgorszego; jeden krok gradientu logarytmu wiarygodności modelu Plackett-Luce (siła =
  `car + driver`): dla każdego miejsca k suma po pozostałych `(1[wybrany] - p)`; zmiana auta = `eta_car * suma po kierowcach zespołu`,
  zmiana kierowcy = `eta_driver * jego składnik`. Mniej niż 2 kierowców: bez zmian.
- `new_season(ratings, car_keep: float, driver_keep: float) -> None`: mnoży oceny aut i kierowców (ściąganie ku 0).
- `build_ratings(history, eta_car, eta_driver, car_keep, driver_keep) -> Ratings`: odtwarza wyniki chronologicznie, na granicy sezonu
  woła `new_season`, w każdym wyścigu rankinguje tylko dojeżdżających (`finished`) w kolejności `finish`.

- [ ] Testy: `finished`; zespół, który wygrywa z kolejnymi, rośnie (`car` zwycięzcy > przegranego po kilku wyścigach);
  kierowca lepszy od kolegi z tego samego auta dostaje dodatni `driver`, a `car` zespołu pozostaje blisko środka; kierowca, który
  odpadł z awarią, nie zmienia swojej oceny; `new_season` ściąga oceny; nieznany kierowca ma siłę 0; mniej niż 2 sklasyfikowanych: bez zmian.
- [ ] RED → implementacja → GREEN → commit.

### Zadanie 2: `long_history` w kontekście

**Pliki:** `data-pipeline/factors/base.py`, `data-pipeline/factors/context.py`, `data-pipeline/evaluation.py`, `data-pipeline/run.py`, testy.

**Interfejsy:** `RaceContext.long_history: list[HistoricRace]` (domyślnie pusta); `build_context(..., long_history=())` filtruje do wyścigów
wcześniejszych niż bieżący (jak `history`). W teście wstecznym `long_history = past + results` (osiem sezonów wstecz plus bieżący); w robocie
(`_predict_weekend`) analogicznie `season_results` dla `HISTORY_SEASONS` poprzednich sezonów i bieżącego do rundy `race.round - 1`.

- [ ] Test: `long_history` w kontekście nigdy nie zawiera rundy bieżącej ani późniejszych; w teście wstecznym zawiera sezony starsze niż
  `history`; w robocie z atrapą przekazywane są poprzednie sezony.
- [ ] RED → implementacja → GREEN → komplet testów → commit.

### Zadanie 3: czynnik `rating_race`

**Pliki:** utwórz `data-pipeline/factors/rating_race.py`, `data-pipeline/factors/registry.py`, `data-pipeline/config.py`, test `tests/test_rating_race.py`.

**Interfejsy:** `RatingRace.score(ctx) -> dict[str, float] | None`: `build_ratings(ctx.long_history or ctx.history, ...)` z
`config.RATING_*`, siła = `Ratings.strength` dla wpisów, z-score po wpisach; `None`, gdy `< 3` wyścigi. Stałe `RATING_ETA_CAR`,
`RATING_ETA_DRIVER`, `RATING_CAR_KEEP`, `RATING_DRIVER_KEEP` (wstępne wartości z zadania 4). Waga `rating_race = 0.0` na starcie
(bramka w zadaniu 5), `WEIGHT_BOUNDS` (0, 0,5).

- [ ] Testy: lider ocen dostaje najwyższy wynik; kierowca spoza historii dostaje wynik neutralny i skończony; `None` przy krótkiej
  historii; wynik nie zależy od wyścigów z przyszłości (test na `long_history` z późniejszą rundą).
- [ ] RED → implementacja → GREEN → commit.

### Zadanie 4: dobór hiperparametrów ocen

**Pliki:** `data-pipeline/oos.py`, `data-pipeline/config.py`, `README.md`.

- [ ] `rating_scan(cases, weights, grid) -> dict`: średni RPS "po kwalifikacjach" i "przed kwalifikacjami" dla siatki wartości
  (`RATING_ETA_CAR` x `RATING_ETA_DRIVER` x `RATING_CAR_KEEP`), z wagą `rating_race` zastępującą `car_pace` + `driver_form`.
  CLI `oos.py --scan-ratings`. Wybór na sezonach 2022-2023 (minimum RPS), kontrola na 2024-2026. Wartości do `config.py`.
- [ ] Test `rating_scan` na atrapach (zwraca wynik dla każdej kombinacji, mniejszy błąd dla sensownych parametrów).
- [ ] Commit.

### Zadanie 5: bramka `rating_race`

**Pliki:** `data-pipeline/oos.py`, `data-pipeline/config.py`, testy `tests/test_oos.py`.

**Interfejsy:** `VARIANTS: dict[str, dict[str, float]]` (nazwa → nadpisania wag); `variant_gate(by_season, test_seasons, base, overrides, n)`
zwraca `(werdykt, diffs)` z `gate_verdict`; CLI `oos.py --variant NAZWA`. Wariant `rating_race`: `{car_pace: 0, driver_form: 0,
rating_race: 0.45}` (suma wag wyścigu zachowana); wariant `rating_race_plus`: oceny obok starych (np. `rating_race 0.30`, stare po połowie).

- [ ] Test `variant_gate` na atrapach (wariant lepszy = `keep`, gorszy = `drop`).
- [ ] Uruchom ręcznie oba warianty; zapisz wyniki; jeśli `keep`: ustaw wagi w `config.py` (stare `car_pace`/`driver_form` do wartości
  wariantu, zablokowane w `LOCKED_WEIGHTS` tylko gdy 0); jeśli `inconclusive` lub `drop`: zostaje stan dotychczasowy (waga 0).
- [ ] Commit.

### Zadanie 6: czynnik `pace_race` (czyste tempo okrążeń)

**Pliki:** utwórz `data-pipeline/factors/pace_race.py`, rejestr, `config.py`, test `tests/test_pace_race.py`; bramka wariantem w `oos.py`.

**Interfejsy:** `PaceRace.score(ctx)`: z agregatów `race_pace` (kierowca -> % względem mediany stawki, ujemne = szybciej) bierze średnią ważoną
nowością (`FORM_HALF_LIFE_ROUNDS`) z przycięciem `RACE_PACE_CLIP`, ściąganą `n/(n+K)` (`AGG_SHRINK_K`); z-score po wpisach (znak odwrócony:
szybszy = wyższa ocena); `None`, gdy mniej niż `AGGREGATE_MIN_RACES` agregatów z tempem. Waga startowa 0,0; wariant `pace_race` w `VARIANTS`.

- [ ] Testy: szybszy kierowca dostaje wyższy wynik; kierowca z jednym wyścigiem jest ściągnięty ku zeru; `None` bez agregatów; wartości skończone.
- [ ] RED → implementacja → GREEN → bramka (`--variant pace_race`) → decyzja o wadze → commit.

### Zadanie 7: czynnik `rating_quali`

**Pliki:** utwórz `data-pipeline/factors/rating_quali.py`, rejestr, `config.py`, test `tests/test_rating_quali.py`; bramka wariantem.

**Interfejsy:** `RatingQuali.score(ctx)`: z agregatów `quali_gap` (kierowca -> strata do pole w %) i zespołów z `ctx.long_history` rozkłada stratę na
**auto** (średnia strata zespołu) i **kierowcę** (odchylenie od kolegi z zespołu), obie ważone nowością i ściągane; siła = `-(auto + kierowca)`,
z-score po wpisach; `None`, gdy mniej niż `AGGREGATE_MIN_RACES` agregatów. Wariant `rating_quali` zastępuje `q_quali_gap` ważonym `q_rating_quali`.
Zasilanie: tylko siła kwalifikacyjna (`QUALI_FACTOR_WEIGHTS`).

- [ ] Testy: lepszy zespół i lepszy kierowca w zespole mają wyższą ocenę; kierowca bez kolegi używa tylko wyniku zespołu; `None` bez agregatów.
- [ ] RED → implementacja → GREEN → bramka na poziomie `quali` (poprawa przedziałem, bez wyraźnego pogorszenia `pre`/`post`) → commit.

### Zadanie 8: dane i domknięcie

- [ ] Przebieg robota (`run.py`), kalibracja (`calibrate.py`), pełny raport (`oos.py`); README ("Etap 3": tabela wyników bramek, wybrane wagi);
  komentarze w `config.py`; pełny zestaw testów (`pytest`, `vitest`); commit.

## Weryfikacja końcowa etapu
Testy zielone; każdy nowy czynnik ma w `config.py` i README werdykt bramki z przedziałem; `ratings.py` pokryty testami bez przecieku z
przyszłości; robot używa `long_history` i nowych czynników zgodnie z werdyktami.
