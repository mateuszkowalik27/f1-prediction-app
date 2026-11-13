# Model v3, etap 4: wspólna losowość zespołu i grube ogony — plan wdrożenia

> **Dla wykonawcy:** zadania po kolei, TDD (test najpierw, obejrzyj porażkę, potem kod). Kroki mają składnię `- [ ]`.

**Cel:** symulacje wyścigu i kwalifikacji mają (1) **wspólny wstrząs zespołu** (obaj kierowcy jednego auta mają ten sam dobry lub zły
weekend) i (2) rzadki **chaos** (mieszanka: z pewnym prawdopodobieństwem cała stawka dostaje wielokrotnie większą losowość). Cel kalibracji:
udział wyścigów wygranych przez kierowcę z prognozą poniżej 2% zbliżony do prognozowanego (dziś ok. 6 z 68 przy 0,1%), faworyci (powyżej 35%) nie przeszacowani.

**Architektura:** parametry jako klucze w słowniku wag (`team_noise_share`, `chaos_base`, `chaos_sc`, `chaos_rain`, `chaos_mult`), jak `quali_noise`,
z wartościami domyślnymi w `config.py` i w `LOCKED_WEIGHTS` (nie strojone przez robota). `simulate_race` i `predict_qualifying` dostają `teams` i
parametry chaosu; przy wartościach zerowych wynik jest **identyczny** jak dziś (te same losowania, brak zmiany zachowania). Raport
`oos.py --scan-noise` wybiera wartości na sezonach 2022-2023 (RPS + diagnostyka ogonów), bramka wariantem sprawdza je na 2024-2026.

**Stos:** Python 3.14 lokalnie (3.12 w CI), numpy, pydantic 2, pytest.

**Spec:** `docs/superpowers/specs/2026-11-13-model-v3-design.md` (sekcja 6).

## Ograniczenia globalne
- Zgodność wstecz: domyślnie zerowe parametry nie zmieniają żadnego wyniku; istniejące testy zielone; UI bez zmian.
- Całkowita wariancja losowości zachowana: udział zespołu `rho` dzieli ją na część wspólną (`sqrt(rho)`) i indywidualną (`sqrt(1-rho)`).
- Wartości parametrów wybierane na sezonach 2022-2023, oceniane na 2024-2026.

## Przegląd fokusu
- Kierowca bez zespołu w `teams`: dostaje własny, jednoosobowy wstrząs (bez błędu).
- `chaos_base + chaos_sc * sc + chaos_rain * deszcz` ograniczone do `[0, 0,6]`.
- Siatka znana (po kwalifikacjach): wspólny wstrząs i chaos dotyczą tylko wyścigu; kwalifikacje mają własne losowanie.

---

### Zadanie 1: `simulate_race` — wstrząs zespołu i chaos
**Pliki:** `data-pipeline/simulate/race.py`, `tests/test_race.py`.
**Interfejsy:** `simulate_race(..., teams: dict[str, str] | None = None, team_share: float = 0.0, chaos_prob: float = 0.0, chaos_mult: float = 1.0)`.
Losowość każdego kierowcy = `sigma * (sqrt(1-share) * z_ind + sqrt(share) * z_team[zespół])`, mnożona w każdej symulacji przez `chaos_mult` z
prawdopodobieństwem `chaos_prob`. Przy `team_share = 0` i `chaos_prob = 0` brak dodatkowych losowań (wynik identyczny jak dziś).
- [ ] Testy: zerowe parametry dają identyczny wynik jak wywołanie bez nich; przy `team_share=1` koledzy z zespołu wygrywają/kończą razem częściej (wspólny los),
  przy 0 niezależnie; `chaos_mult>1` z dużym `chaos_prob` podnosi szansę słabszego kierowcy i obniża faworyta; prawdopodobieństwa sumują się do 1.
- [ ] RED → implementacja → GREEN → commit.

### Zadanie 2: `predict_qualifying` — to samo dla kwalifikacji
**Pliki:** `data-pipeline/simulate/qualifying.py`, `tests/test_qualifying.py`. Te same parametry (`teams`, `team_share`, `chaos_prob`, `chaos_mult`).
- [ ] Testy: zerowe parametry = wynik jak dziś; wspólny wstrząs zwiększa korelację miejsc kolegów; chaos spłaszcza rozkład (niższa szansa pole faworyta).
- [ ] RED → implementacja → GREEN → commit.

### Zadanie 3: parametry w wagach i okablowanie
**Pliki:** `config.py`, `evaluation.py`, `run.py`, testy.
- [ ] `config`: `TEAM_NOISE_SHARE = 0.0`, `CHAOS_BASE = 0.0`, `CHAOS_SC = 0.0`, `CHAOS_RAIN = 0.0`, `CHAOS_MULT = 2.0`; `default_weights()` zawiera
  `team_noise_share`, `chaos_base`, `chaos_sc`, `chaos_rain`, `chaos_mult`; wszystkie w `LOCKED_WEIGHTS`.
- [ ] `_predict_case`, `evaluate_quali`, `_predict_weekend`: `teams` z `entries`, `chaos_prob = clip(chaos_base + chaos_sc*sc + chaos_rain*deszcz, 0, 0,6)`.
- [ ] Testy: wagi zawierają klucze; zmiana `team_noise_share`/`chaos_base` w wagach zmienia wynik oceny; domyślnie wynik niezmieniony (regresja).
- [ ] RED → implementacja → GREEN → komplet testów → commit.

### Zadanie 4: diagnostyka ogonów i skan
**Pliki:** `evaluation.py` (log-strata zwycięzcy w `RaceLevels`), `oos.py` (`tail_report`, `noise_scan`, `--scan-noise`), testy.
- [ ] `RaceLevels.logloss_win_pre`, `logloss_win_post` (log-strata zwycięzcy, dolne ograniczenie 0,001).
- [ ] `tail_report(cases, weights, n) -> dict`: liczba wyścigów wygranych przez kierowcę z prognozą `< 0,02` (faktycznie vs oczekiwana suma prognoz) i średnia
  prognoza vs faktyczna częstość dla faworytów `> 0,35`.
- [ ] `noise_scan(cases, weights, grid, n)`: dla kombinacji parametrów średni RPS (pre, post, kwalifikacje), log-strata i `tail_report`; CLI `--scan-noise`.
- [ ] Testy na atrapach; commit.

### Zadanie 5: wybór parametrów i bramka
- [ ] `oos.py --scan-noise` (ręcznie): kombinacje `team_noise_share` x `chaos_base` x `chaos_mult`; wybór na 2022-2023 (min suma RPS trzech poziomów przy poprawie
  ogonów), kontrola na 2024-2026. Wartości do `config.py`.
- [ ] Wariant `noise_model` w `VARIANTS`; bramka `--variant noise_model`: przyjmujemy, gdy werdykt nie jest `drop` i diagnostyka ogonów jest bliżej celu;
  inaczej zostaje stan dotychczasowy (zerowe parametry).
- [ ] Zapis wyniku w `config.py` i README; commit.

### Zadanie 6: dane i domknięcie
- [ ] Kalibracja (`calibrate.py`), przebieg robota (`run.py`), raport (`oos.py`); pełne testy (`pytest`, `vitest`); README (sekcja "Etap 4"); commit.

## Weryfikacja końcowa etapu
Testy zielone; parametry w `config.py` z komentarzem wyboru; README zawiera tabelę ogonów (przed i po) i werdykt bramki.
