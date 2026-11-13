# Model v3, etap 1: miara oceny — plan wdrożenia

> **Dla wykonawcy:** wykonaj zadania po kolei, TDD (test najpierw, obejrzyj porażkę, potem kod). Kroki mają składnię `- [ ]`.

**Cel:** zastąpić ocenę "tylko zwycięzca" oceną całej kolejności (RPS), dodać ocenę prognoz sprzed kwalifikacji i samych
kwalifikacji oraz przedziały ufności (bootstrap) i nową regułę bramki.

**Architektura:** nowy moduł `scoring.py` (czyste funkcje: RPS, bootstrap, werdykt); `evaluation.py` dostaje poziomy oceny
(`grid_known`, kwalifikacje) i `RoundCase.actual_quali`; `oos.py` raportuje wagi bazowe obok dostrojonych i bramkę z przedziałami;
`oos.json` dostaje nowe pola. Robot (`run.py`) bez zmian poza ewentualną decyzją w zadaniu 6.

**Stos:** Python 3.14 lokalnie (3.12 w CI), numpy, pydantic 2, pytest.

**Spec:** `docs/superpowers/specs/2026-11-13-model-v3-design.md` (sekcja 3).

## Ograniczenia globalne
- Komentarze i teksty dla użytkownika po polsku; kod angielski jak dotąd.
- Zgodność wstecz: istniejące testy (318) zostają zielone; `Brier` zwycięzcy zostaje jako wskaźnik pomocniczy.
- Ziarno losowości zawsze jawne (powtarzalność bootstrapu i symulacji).

## Przegląd fokusu (czego plan nie pokrywa testami, a trzeba sprawdzić)
- Kierowca bez miejsca w kolejności mety (nieklasyfikowany): rozkład "jednakowo prawdopodobny na ostatnich miejscach".
- Wyścig bez danych kwalifikacji z Jolpica (`actual_quali=None`): poziom "kwalifikacje" pomija wyścig, nie psuje reszty.
- Sezon bez żadnego wyścigu testowego: pomijany jak dotąd.

---

### Zadanie 1: `scoring.py` — RPS

**Pliki:** utwórz `data-pipeline/scoring.py`, test `tests/test_scoring.py`.

**Interfejsy:**
- Produkuje: `rps(predicted: Sequence[float], actual: Sequence[float]) -> float`, gdzie oba to rozkłady na miejsca 1..N
  (suma 1); wynik w [0, 1], 0 = idealnie. Definicja: `sum_{k=1}^{N-1} (F_pred(k) - F_act(k))^2 / (N-1)`.
- Produkuje: `actual_distribution(position: int | None, n: int, classified: int) -> list[float]` — jedynka na `position`
  albo, dla `None` (nieklasyfikowany), rozkład jednostajny na miejscach `classified+1..n`.
- Produkuje: `ranking_rps(prediction: list[DriverProbability], actual: dict[str, int | None]) -> float` — średnie RPS po
  kierowcach obecnych w obu (pozycja `None` = nieklasyfikowany). N = długość `position_distribution`.

- [ ] Test: `rps([1,0,0],[1,0,0]) == 0`; `rps([1,0,0],[0,0,1]) == 1`; `rps([0,1,0],[1,0,0]) == 0.5` (blisko = mała kara,
  daleko = duża); `actual_distribution(None, 5, 3) == [0,0,0,.5,.5]`; kierowca spoza prognozy jest pomijany.
- [ ] Uruchom, zobacz porażkę (brak modułu). Zaimplementuj. Uruchom, zobacz zielone.
- [ ] Commit.

### Zadanie 2: `scoring.py` — bootstrap i werdykt

**Interfejsy:**
- Produkuje: `@dataclass(frozen=True) class Diff: mean: float; lo: float; hi: float; n: int`.
- Produkuje: `paired_bootstrap(a: Sequence[float], b: Sequence[float], n_boot: int = 4000, seed: int = 0, level: float = 0.9) -> Diff`
  (różnica `a - b` na wyścig; ujemna = `a` lepsze; przedział percentylowy).
- Produkuje: `verdict(diff: Diff) -> Literal["better", "worse", "inconclusive"]` — `better` gdy `hi < 0`, `worse` gdy `lo > 0`.

- [ ] Test: identyczne listy → `mean == 0`, werdykt `inconclusive`; `a` stale o 0,1 mniejsze → `better` i `hi < 0`; powtarzalność przy tym
  samym ziarnie; różne długości → `ValueError`.
- [ ] RED → implementacja → GREEN → commit.

### Zadanie 3: poziomy oceny w `evaluation.py`

**Pliki:** `data-pipeline/evaluation.py`, `data-pipeline/schemas.py` (bez zmian modelu API), testy `tests/test_evaluation.py`.

**Interfejsy:**
- `RoundCase.actual_quali: dict[str, int] | None = None` (domyślnie `None`, zgodność wstecz).
- `prepare_rounds`: wypełnia `actual_quali` z `jolpica.qualifying_grid(season, round)`; `JolpicaError` albo brak → `None`.
- `_predict_case(case, weights, n, grid_known=True)`: przy `grid_known=False` przekazuje `grid=None` do `simulate_race`.
- Produkuje: `@dataclass(frozen=True) class RaceLevels: round: int; rps_pre: float; rps_post: float; rps_quali: float | None; brier_win_post: float`.
- Produkuje: `evaluate_levels(cases: list[RoundCase], weights: dict[str, float], n: int) -> list[RaceLevels]` — dla każdego wyścigu:
  `rps_pre` (siatka losowana), `rps_post` (znana siatka), `rps_quali` (`predict_qualifying` z siły po `combine`, `QUALIFYING_NOISE`,
  oceniane względem `actual_quali`; `None` bez danych).

- [ ] Test (atrapy): przy `grid_known=False` w symulacji nie ma deterministycznej siatki (wynik różni się od `grid_known=True`, gdy
  siatka jest mocno inna niż siła); `evaluate_levels` zwraca 3 pola dla przypadku z `actual_quali` i `None` bez niego; idealna
  siła (lider siły = pole) daje niższe `rps_quali` niż siła odwrócona.
- [ ] RED → implementacja → GREEN → komplet testów zielony → commit.

### Zadanie 4: raport poza próbką z przedziałami

**Pliki:** `data-pipeline/oos.py`, `data-pipeline/schemas.py` (`SeasonScore`), `tests/test_oos.py`.

**Interfejsy:**
- `SeasonScore` dostaje opcjonalne pola: `rps_pre`, `rps_post`, `rps_quali` (średnie sezonu, `None` gdy brak), zgodność wstecz.
- Produkuje: `level_report(by_season, test_seasons, base, bounds, locked, n) -> dict` z trzema zestawami wag: `base`
  (bazowe), `tuned` (walk-forward jak dziś) i `grid_only` (siła zerowa), oraz `Diff` dla par: `tuned - base`, `base - grid_only`
  na każdym z trzech poziomów (po wszystkich wyścigach testowych).
- `keep_rule` zastąpiona `gate_verdict(with_levels, without_levels) -> Literal["keep", "drop", "inconclusive"]`:
  `keep` gdy `verdict(Diff) == "better"` na `rps_pre` lub `rps_post` i nie `worse` na drugim; `drop` gdy `worse` na którymś;
  inaczej `inconclusive` (istniejące zostaje, nowe nie wchodzi). Stara reguła zostaje w kodzie do porównania (nie jest używana).
- `factor_gate` zwraca werdykt z przedziałami; CLI `oos.py --factor` drukuje tabelę RPS (z / bez) i przedział.
- `write_oos` zapisuje nowe pola; `oos.py` bez argumentów drukuje raport trzech zestawów wag.

- [ ] Test: `gate_verdict` — wyraźna poprawa → `keep`; wyraźne pogorszenie → `drop`; szeroki przedział → `inconclusive`;
  `write_oos` zapisuje stare i nowe pola; `level_report` na małych atrapach zwraca wszystkie klucze.
- [ ] RED → implementacja → GREEN → commit.

### Zadanie 5: pomiar bazowy na prawdziwych danych

**Pliki:** `data-pipeline/config.py` (komentarz z wynikami), `README.md`, `public/data/oos.json`.

- [ ] Uruchom `python data-pipeline/oos.py` (kilka minut, ręcznie). Zapisz RPS na trzech poziomach dla `base`, `tuned`, `grid_only`
  oraz przedziały. Wpisz tabelę do komentarza w `config.py` ("Punkt odniesienia v3, 2026-11-13").
- [ ] Przelicz dziś-odrzucone i zachowane czynniki nową bramką tylko tam, gdzie to tanie: `--factor quali_gap`, `--factor pit_stop`
  (raport, bez zmiany wag w tym etapie, chyba że werdykt to `drop` z wyraźnym przedziałem).
- [ ] README: sekcja "Jak oceniamy model" (RPS, trzy poziomy, przedziały, werdykt "niejednoznaczny") po polsku.
- [ ] Commit.

### Zadanie 6: decyzja o strojeniu w robocie

**Pliki:** `data-pipeline/run.py` (`_tuned_weights`), `data-pipeline/config.py`, testy `tests/test_pipeline.py`.

- [ ] Jeśli raport z zadania 5 pokazuje, że `tuned` nie jest wyraźnie lepsze od `base` (przedział nie `better`): ustaw
  `config.USE_TUNED_WEIGHTS = False`; robot używa wag bazowych i nadal zapisuje historię strojenia do porównania. Jeśli jest
  wyraźnie lepsze: zostaw strojenie, ale zmień jego cel na średni RPS po kwalifikacjach (`evaluation.mean_rps_post`).
- [ ] Test: przy `USE_TUNED_WEIGHTS = False` wagi z `weekend` pipeline równają się bazowym mimo dostępnych rund do strojenia.
- [ ] Pełny zestaw testów (`pytest`, `vitest`) zielony; commit.

## Weryfikacja końcowa etapu
Wszystkie testy zielone; `oos.json` zawiera RPS na trzech poziomach; README i komentarz w `config.py` opisują nową miarę i punkt
odniesienia; decyzja z zadania 6 jest zapisana jako ruling w README.
