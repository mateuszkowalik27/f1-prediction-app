# Model v3, etap 5: czynniki z treningów — plan wdrożenia

> **Dla wykonawcy:** zadania po kolei, TDD (test najpierw, obejrzyj porażkę, potem kod). Kroki mają składnię `- [ ]`.

**Cel:** cztery czynniki z sesji bieżącego weekendu (OpenF1), bez danych wstecz (decyzja użytkownika): `fp2_long_run` (tempo z długich przejazdów FP2 → siła
wyścigowa), `fp3_quali_sim` (symulacja kwalifikacji z FP3 → siła kwalifikacyjna), `sprint_pace` (czyste tempo ze sprintu → siła wyścigowa, weekendy sprinterskie),
`sq_quali` (kwalifikacje sprintu → siła kwalifikacyjna głównych kwalifikacji w weekendach sprinterskich; decyzja domyślna ze specyfikacji). Waga umiarkowana i stała.
Ocena na bieżąco: zamrożona prognoza zapisuje wersję z tymi czynnikami i bez nich, a po wyścigu liczymy RPS obu.

**Architektura:** nowy moduł `weekend_signals.py` (czyste funkcje: tempo z długich przejazdów, symulacja kwalifikacji, strata do najszybszego); `OpenF1Client.weekend_signals`
(sesje Practice 2/3, Sprint, Sprint Qualifying; błędy liczone jak dotąd); `RaceContext.signals`; cztery czynniki; w pipeline druga prognoza "bez czynników treningowych";
`FrozenPrediction` i `ModelPayload.live_comparison`.

**Stos:** Python 3.14 lokalnie (3.12 w CI), numpy, pydantic 2, pytest.

**Spec:** `docs/superpowers/specs/2026-11-13-model-v3-design.md` (sekcja 7).

## Ograniczenia globalne
- Brak danych (sesja się nie odbyła, brak okrążeń, błąd OpenF1): czynnik zwraca `None` i jest pomijany; weekend bez FP2/FP3 (sprinterski) nie ma `fp2_long_run`/`fp3_quali_sim`.
- Zgodność wstecz: istniejące testy zielone; UI bez zmian; stare pliki `predictions/*.json` (bez nowych pól) nadal się wczytują.
- Wagi stałe i nie strojone (`LOCKED_WEIGHTS`); werdykt po ok. 10 weekendach z `live_comparison`.

## Przegląd fokusu
- Kierowca bez długiego przejazdu (za mało okrążeń w stincie): pomijany; kierowca z jedną mieszanką bez wspólnych kierowców z drugą: pomijany.
- `signals` obecne, ale dany słownik pusty: czynnik `None`, nie błąd.
- Nieznany kierowca z sygnałów (spoza składu): pomijany przy z-score.

---

### Zadanie 1: obliczenia `weekend_signals.py`
**Pliki:** utwórz `data-pipeline/weekend_signals.py`, test `tests/test_weekend_signals.py`; `schemas.py` (`WeekendSignals`).
**Interfejsy:** `WeekendSignals(long_run, quali_sim, sprint_pace, sq_gap: dict[str, float])` (procenty względem stawki, ujemne = szybciej);
`long_run_pace(laps: list[LapRecord]) -> dict[str, float]` (stinty min. `PRACTICE_LONGRUN_MIN_LAPS` = 5 czystych okrążeń na jednej mieszance, korekta na paliwo
`+FUEL_EFFECT_S_PER_LAP * numer okrążenia w stincie`, odrzucenie okrążeń wolniejszych niż `SLOW_LAP_RATIO` x mediana stintu, przesunięcie między mieszankami
jak w `adjusted_practice`, mediana stintów kierowcy, % względem mediany stawki); `quali_sim_pace(laps) -> dict[str, float]` (najlepsze czyste okrążenie kierowcy
po przesunięciu między mieszankami, % względem mediany stawki); `gap_percent(best_times: dict[str, float]) -> dict[str, float]` (% straty do najszybszego).
- [ ] Testy: szybszy kierowca ma ujemny %; stint krótszy niż 5 okrążeń pomijany; korekta na paliwo zmniejsza sztuczną przewagę późniejszych okrążeń; przesunięcie między mieszankami;
  okrążenia wolniejsze o ponad 7% odrzucane; `gap_percent` najszybszy = 0.
- [ ] RED → implementacja → GREEN → commit.

### Zadanie 2: OpenF1 `weekend_signals`
**Pliki:** `data-pipeline/fetch/openf1.py`, `tests/test_openf1.py`.
**Interfejsy:** `OpenF1Client.weekend_signals(race, entries) -> WeekendSignals | None`: dla sesji "Practice 2" (`long_run`), "Practice 3" (`quali_sim`), "Sprint"
(`sprint_pace` przez `compute_race_pace`), "Sprint Qualifying" (`sq_gap` z `/session_result`, najlepszy czas kierowcy); okrążenia z mieszanką jak w `race_laps`
(wspólna `_session_laps(key, entries)`). Błąd lub brak => `errors += 1` / pominięta sesja; wszystkie słowniki puste => `None`.
- [ ] Testy z atrapami HTTP: FP2 daje `long_run`, FP3 `quali_sim`, Sprint `sprint_pace`, SQ `sq_gap`; brak sesji => `None`; błąd HTTP zwiększa `errors`.
- [ ] RED → implementacja → GREEN → commit.

### Zadanie 3: czynniki i wagi
**Pliki:** `factors/base.py` (`RaceContext.signals`), `factors/context.py`, `factors/weekend_signal_factors.py` (cztery klasy), `registry.py`, `config.py`, testy.
**Interfejsy:** `Fp2LongRun`, `Fp3QualiSim`, `SprintPace`, `SqQuali` (`name` odpowiednio `fp2_long_run`, `fp3_quali_sim`, `sprint_pace`, `sq_quali`): z-score `-%` po wpisach,
`None` bez danych. Wagi: wyścig `fp2_long_run` 0,10 i `sprint_pace` 0,10; kwalifikacje `q_fp3_quali_sim` 0,12 i `q_sq_quali` 0,15; pozostałe 0 i `LOCKED_WEIGHTS`.
- [ ] Testy: lider tempa ma najwyższy wynik; `None` bez sygnałów i bez danego słownika; kierowca spoza sygnałów dostaje wynik neutralny; wagi w `default_weights()` i bounds zgodne z `test_config`.
- [ ] RED → implementacja → GREEN → commit.

### Zadanie 4: pipeline i ocena na bieżąco
**Pliki:** `run.py`, `schemas.py` (`FrozenPrediction`, `LiveComparison`, `ModelPayload.live_comparison`), testy.
- [ ] `_predict_weekend`: sygnały (opcjonalnie), druga prognoza z wagami czynników treningowych równymi 0 (`race_prediction_without_practice`, `qualifying_without_practice`).
- [ ] `FrozenPrediction`: nowe pola opcjonalne (`qualifying`, `race_prediction_without_practice`, `qualifying_without_practice`); `live_comparison` po wyścigu: RPS z / bez dla wyścigu
  i dla kwalifikacji (wyniki z `RoundCase`).
- [ ] Testy: zamrożony plik zawiera obie wersje; `live_comparison` liczy RPS dla rundy z zapisaną prognozą; stary plik bez nowych pól się wczytuje.
- [ ] RED → implementacja → GREEN → komplet testów → commit.

### Zadanie 5: dane i dokumentacja
- [ ] README ("Etap 5": co robi każdy czynnik, wagi, jak czytać `live_comparison`, kiedy decyzja), komentarze w `config.py`; przebieg robota; testy (`pytest`, `vitest`); commit.

## Weryfikacja końcowa etapu
Testy zielone; robot w weekendzie z treningami zapisuje dwie wersje prognozy; `model.json` ma `live_comparison`; README opisuje kryterium decyzji po ok. 10 weekendach.
