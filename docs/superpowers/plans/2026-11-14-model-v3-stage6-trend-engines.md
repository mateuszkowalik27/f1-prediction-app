# Model v3, etap 6: trend sezonu i grupowanie po silniku — plan wdrożenia

> **Dla wykonawcy:** zadania po kolei, TDD (test najpierw, obejrzyj porażkę, potem kod). Kroki mają składnię `- [ ]`.

**Cel:** (1) oceny aut dostają **trend** (zespół z poprawkami przyspiesza, inny zwalnia); (2) **ciągłość przy zmianie nazwy zespołu** (Alfa Romeo, Sauber, Audi; AlphaTauri, RB) i
(3) **punkt startowy z dostawcy silnika** dla zespołu bez własnych wyników (np. Cadillac 2026): średnia ocen innych zespołów z tym samym silnikiem.

**Architektura:** nowy moduł `engines.py` z tabelami `ENGINE_SUPPLIER` (sezon -> zespół -> dostawca; ręcznie, co sezon) i `TEAM_LINEAGE` (zespół -> poprzednia nazwa); `ratings.py`
dostaje trend (wygładzona zmiana oceny auta po wyścigu), dziedziczenie oceny po poprzedniku i punkt startowy z dostawcy; `RatingRace` używa ich z `config`. Trend i dziedziczenie
przechodzą bramkę nową miarą (RPS, przedziały): trend wchodzi tylko przy wyraźnej poprawie, dziedziczenie i punkt startowy z dostawcy tylko przy braku pogorszenia (to poprawność danych).

**Stos:** Python 3.14 lokalnie (3.12 w CI), numpy, pydantic 2, pytest.

**Spec:** `docs/superpowers/specs/2026-11-13-model-v3-design.md` (sekcja 8).

## Ograniczenia globalne
- Zgodność wstecz: wartości zerowe (`RATING_TREND_GAIN = 0`, brak tabel) dają dokładnie dotychczasowe oceny; istniejące testy zielone; UI bez zmian.
- Tabela silników jest ręczna: test sprawdza pokrycie wszystkich zespołów sezonu 2026, a robot ostrzega na stderr o zespole bez dostawcy (bez przerywania).
- Bez przecieku: oceny nadal powstają tylko z wyścigów wcześniejszych niż przewidywany.

## Przegląd fokusu
- Zespół bez poprzednika, bez dostawcy lub bez ocenionych kolegów po silniku: ocena startowa 0 (jak dotąd), bez błędu.
- Poprzednik też bez oceny: brak dziedziczenia.
- Pierwszy wyścig w historii: trend 0.

---

### Zadanie 1: tabele i pomocnicze `engines.py`
**Pliki:** utwórz `data-pipeline/engines.py`, test `tests/test_engines.py`; `config.py` (`ENGINE_SUPPLIER`, `TEAM_LINEAGE`).
**Interfejsy:** `supplier_of(season: int, team_id: str) -> str | None`; `predecessor_of(team_id: str) -> str | None`; `uncovered_teams(season: int, team_ids: Iterable[str]) -> list[str]`.
Tabele dla sezonów 2022-2026 (Mercedes, Ferrari, Red Bull/RBPT, Renault; 2026: Mercedes, Ferrari, Honda, Red Bull-Ford, Audi), `TEAM_LINEAGE`: `alfa -> sauber -> audi`, `alphatauri -> rb`.
- [ ] Testy: wszystkie 11 zespołów 2026 mają dostawcę; klient Mercedesa 2026 (McLaren, Williams, Alpine) ma tego samego dostawcę co fabryka; `predecessor_of("audi") == "sauber"`;
  nieznany zespół/sezon -> `None`; `uncovered_teams` wskazuje brakujące.
- [ ] RED → implementacja → GREEN → commit.

### Zadanie 2: trend, dziedziczenie i punkt startowy w `ratings.py`
**Pliki:** `data-pipeline/ratings.py`, `tests/test_ratings.py`.
**Interfejsy:** `Ratings.trend: dict[str, float]`; `Ratings.strength(driver_id, team_id, trend_gain=0.0)` (dodaje `trend_gain * trend[zespół]`);
`build_ratings(history, eta_car, eta_driver, car_keep, driver_keep, *, trend_alpha=0.0, lineage=None, supplier_of=None, supplier_weight=0.0)`:
po każdym wyścigu `trend[zespół] = (1 - alpha) * trend + alpha * (ocena po - ocena przed)`; na granicy sezonu trend ściągany x0,5; przy pierwszym pojawieniu zespołu
bez oceny: dziedziczy ocenę poprzednika (`lineage`), a gdy go nie ma, dostaje `supplier_weight * średnia ocen zespołów z tym samym dostawcą` (`supplier_of(sezon, zespół)`).
- [ ] Testy: zespół, który wygrywa kolejne wyścigi, ma dodatni trend, a przegrywający ujemny; `strength` z `trend_gain` większym niż 0 wyprzedza zespół o tej samej ocenie bez trendu;
  zmiana nazwy (`audi` po `sauber`) dziedziczy ocenę; nowy zespół dostaje średnią ocen kolegów po silniku; wartości domyślne dają wynik identyczny jak dotąd.
- [ ] RED → implementacja → GREEN → commit.

### Zadanie 3: `RatingRace` i bramka parametrów
**Pliki:** `data-pipeline/factors/rating_race.py`, `data-pipeline/oos.py`, `config.py`, testy.
**Interfejsy:** stałe `RATING_TREND_GAIN` (0), `RATING_TREND_ALPHA` (0,3), `RATING_SUPPLIER_WEIGHT` (0), `RATING_USE_LINEAGE` (False); `RatingRace` czyta je (z możliwością podania wprost);
`oos.py`: `rating_param_gate(cases_by_season, test_seasons, base, new_params, old_params, n)` (bramka dwóch zestawów parametrów ocen: przelicza `rating_race` i porównuje RPS),
`--scan-trend` (zysk trendu 0 / 0,5 / 1 / 2 na sezonach 2022-2023, kontrola na testowych), `--gate-ratings` (dziedziczenie, punkt startowy z dostawcy, trend).
- [ ] Testy: `RatingRace` z włączonymi parametrami zmienia wynik względem domyślnych; `rating_param_gate` zwraca werdykt i przedziały na atrapach.
- [ ] RED → implementacja → GREEN → commit.

### Zadanie 4: pomiar i decyzje
- [ ] `oos.py --scan-trend` (wybór zysku trendu na 2022-2023), `--gate-ratings` (test 2024-2026). Decyzje: dziedziczenie i punkt startowy z dostawcy włączamy, gdy nie pogarszają (werdykt inny niż `drop`);
  trend tylko przy `keep`. Wartości do `config.py`, wyniki do komentarza i README. Commit.

### Zadanie 5: ostrzeżenie o zespole bez dostawcy
**Pliki:** `data-pipeline/run.py`, test `tests/test_pipeline.py`.
- [ ] `_predict_weekend` ostrzega na stderr (`UWAGA: zespół X nie ma dostawcy silnika w ENGINE_SUPPLIER[sezon]`), bez przerywania; test na zespole spoza tabeli.
- [ ] RED → implementacja → GREEN → commit.

### Zadanie 6: dane i domknięcie
- [ ] Kalibracja, przebieg robota, raport (`oos.py`); README ("Etap 6"); pełne testy; commit.

## Weryfikacja końcowa etapu
Testy zielone; tabela silników pokrywa wszystkie zespoły 2026 (test); werdykty bramek (trend, dziedziczenie, dostawca) są w `config.py` i README.
