# Model v2: nowe zmienne, dłuższy test wsteczny i kalibracja

Data: 2026-11-12. Status: do akceptacji. Rozszerza `2026-11-12-f1-prediction-app-design.md` (nie zastępuje go).

## 1. Cel

Poprawić dokładność i wiarygodność szans na wygraną o sześć nowych źródeł informacji wskazanych przez użytkownika:
**kary na starcie, różnica czasów w kwalifikacjach, tempo wyścigowe vs kwalifikacyjne, zużycie opon, czas pit stopu
zespołu, temperatura**. Każda zmienna jest dodawana **osobno** i zostaje w modelu tylko wtedy, gdy poprawia wynik na
sezonach, których model nie widział przy strojeniu (sekcja 3).

Poza zakresem (decyzja użytkownika: nie wybrano): kierowca osobno od bolidu (porównanie z partnerem), start
(miejsca zyskane na 1. okrążeniu), prędkość maksymalna zespołu, wyniki sprintów w modelu, szanse na żywo w trakcie
wyścigu (osobny temat, po tym zakresie).

## 2. Fundament (robimy pierwszy)

### 2.1 Dłuższy test wsteczny (2022–2026)
Dziś ocena opiera się na 20 wyścigach jednego sezonu, więc szum zasłania efekt nowych zmiennych. Rozszerzamy test na
sezony 2022–2026 (około 100 wyścigów). Zmienne zależne od OpenF1 mają dane dopiero od 2023, więc dla 2022 są
wyłączone (`None`), a reszta modelu działa jak dotąd.

### 2.2 Protokół oceny poza próbką
Rosnące okno: wagi i stałe dla sezonu S są strojone wyłącznie na sezonach wcześniejszych niż S, a ocenianie dotyczy
sezonu S. Wynik to średni Brier z sezonów testowych 2024, 2025, 2026 (2022–2023 służą tylko do strojenia).
**Reguła zostawienia zmiennej:** poprawia średni Brier z sezonów testowych **i** nie pogarsza go w więcej niż jednym
z trzech sezonów. W przeciwnym razie zmienna jest wyłączona (waga 0 w konfiguracji), ale kod zostaje.

### 2.3 Kalibracja szans
Sprawdzamy, czy "30%" wygrywa w około 30% wyścigów. Dopasowujemy jeden parametr skalujący τ
(`p' ∝ p^τ`, potem normalizacja do 100%) na przewidywaniach poza próbką z testu wstecznego. Jeden parametr wybrany,
bo danych jest mało. Wynik w `public/data/calibration.json`, stosowany w pipeline przed zapisem szans. Przy zbyt małej
próbce (< 60 wyścigów) τ = 1 (brak korekty).

### 2.4 Magazyn agregatów
Surowe okrążenia nie są pobierane przy każdym uruchomieniu robota (limity API: Jolpica ~200/h, OpenF1 3/s).
Dla każdego **zakończonego** wyścigu liczymy raz zestaw agregatów i zapisujemy go w
`public/data/history/<sezon>-<runda>.json` (kilka KB na wyścig, łącznie < 1 MB):

- `quali_gap`: kierowca → procentowa strata do najszybszego w sesji (Q1 dla wszystkich, Q2/Q3 dla awansujących),
- `pit_delta`: zespół → mediana różnicy czasu przejazdu przez aleję względem mediany stawki w tym wyścigu,
- `race_pace`: kierowca → mediana czystych okrążeń wyścigowych względem mediany stawki,
- `tyre_deg`: zespół → nachylenie (s/okrążenie) czasu okrążenia od wieku opon, po korekcie na paliwo, osobno dla
  mieszanek; oraz poziom zużycia toru w tym wyścigu,
- `temps`: temperatura powietrza i toru podczas wyścigu,
- `official_grid`: oficjalna siatka startowa (z karami),
- `sources`: które źródła dostarczyły dane (ok / brak).

Uzupełnianie historii (backfill) idzie stopniowo: pipeline dolicza maksymalnie N brakujących wyścigów na uruchomienie
(analogicznie do dzisiejszych profili torów), więc pierwsze dni po wdrożeniu historia się dopełnia. Agregaty są
idempotentne i niezmienne po zapisaniu.

## 3. Zmienne

Każda to czynnik (`Factor`) z własną wagą w `FACTOR_WEIGHTS`, granicami w `WEIGHT_BOUNDS`, polską nazwą w
`labels.js`, wyłączany (`None`), gdy brak danych. Auto-wagi stroją je jak dotychczasowe.

### 3.1 Kary na starcie (zmiana siatki, nie czynnik)
Po kwalifikacjach używamy **oficjalnej siatki startowej** (kary, starty z alei serwisowej) zamiast kolejności
kwalifikacji. Start z alei serwisowej = pozycja za ostatnim zakwalifikowanym. Przed kwalifikacjami kar nie zgadujemy.
Weekend pokazuje, kiedy siatka różni się od kwalifikacji ("Kary: X z 3. na 13."). Źródło oficjalnej siatki do
potwierdzenia w pierwszym kroku implementacji (spike: OpenF1 `starting_grid`, a w razie braku wynik wyścigu z Jolpica
po fakcie). Test wsteczny już dziś używa prawdziwej siatki, więc ta zmiana wyrównuje działanie na żywo z testem.

### 3.2 `quali_gap` (różnica czasów w kwalifikacjach)
Dla każdego kierowcy: średnia procentowej straty do najszybszego, z wagą recency (jak forma). Jeden numer na kierowcę
łączący Q1 (wszyscy) i Q2/Q3 (awansujący); sposób łączenia sesji ustalamy w planie. Wejście także dla modelu
kwalifikacji (ta sama siła). Źródło: Jolpica (czasy Q1/Q2/Q3, 2022+).

### 3.3 `race_vs_quali` (tempo wyścigowe vs kwalifikacyjne)
Dla zespołu: średnia z (tempo wyścigowe względem stawki minus tempo kwalifikacyjne względem stawki), z wagą recency
i ściąganiem ku zeru. Zespół szybszy w niedzielę, niż wynika z soboty, dostaje plus. Czyste okrążenia: bez 1.
okrążenia, okrążeń z pit stopem, za safety carem/VSC i z flagami. Źródło: OpenF1 (okrążenia), 2023+.

### 3.4 `tyre_deg_fit` (zużycie opon)
Interakcja zespołu z torem: (zużycie zespołu względem stawki) × (poziom zużycia toru z jego historii). Zespół o małym
zużyciu dostaje plus na torze o dużym zużyciu. Wchodzi także do strategii: wysoki poziom zużycia podnosi
prawdopodobieństwo wariantu z większą liczbą postojów (alternatywa) i obniża pewność strategii głównej. Czynnik jest
wyłączony, gdy tor nie ma historii zużycia (OpenF1, 2023+).

### 3.5 `pit_stop` (czas pit stopu zespołu)
Mediana `pit_delta` zespołu ze **wszystkich postojów sezonu** (z wagą recency, na początku sezonu uzupełniana
poprzednim rokiem). Porównujemy z medianą stawki **w tym samym wyścigu** (różna długość alei na torach), odrzucamy
wartości odstające (czerwone flagi, kary stop-and-go, awarie). Jolpica podaje czas przejazdu przez aleję, a nie samo
stanie w boksie: wystarcza do porównania zespołów. Spodziewany efekt mały (waga o niskiej górnej granicy).

### 3.6 `temp_fit` (temperatura)
Ściągana regresja grzbietowa wyniku zespołu względem temperatury powietrza na torach rozegranych wyścigów, jak
`car_track_fit`. **Wejściem jest temperatura powietrza**, bo prognoza (Open-Meteo) podaje powietrze, a nie tor; temperaturę
toru przechowujemy w agregatach tylko do oszacowania poziomu zużycia (3.4). Prognoza na godzinę startu wyścigu
(godzinowa), nie dzienne maksimum. Spodziewany efekt najmniejszy; wymaga ≥ `FIT_MIN_RACES` rund.

## 4. Wpływ na pipeline, plik JSON i interfejs

- `weekend.json`: pola `grid_source` (`official | qualifying | predicted`) i `penalties` (lista zmian pozycji).
  Ekran Weekend pokazuje jedną linijkę o karach, gdy są.
- `calibration.json` i `history/*.json` dochodzą do `public/data/` (workflow już je commituje).
- `model.json` zawiera nowe wagi i ocenę poza próbką (aplikacja jej nie wyświetla, zakładkę Model usunięto).
- Zakładki i ekrany poza linijką o karach bez zmian.

## 5. Testowanie

TDD jak dotąd: testy jednostkowe każdego czynnika na zapisanych próbkach prawdziwych odpowiedzi API (Jolpica,
OpenF1), test integracyjny pipeline z atrapami, test protokołu poza próbką (strojenie na sezonach < S nie widzi
sezonu S), test kalibracji (τ = 1 przy małej próbce, szanse sumują się do 100%), test idempotencji backfillu.
Każda zmienna ma raport "przed/po" z testu wstecznego zapisany w komentarzu konfiguracji.

## 6. Kolejność prac

0. Magazyn agregatów, backfill, test wsteczny 2022–2026, protokół poza próbką, kalibracja.
1. Oficjalna siatka i kary (+ linijka w interfejsie).
2. `quali_gap`.
3. `pit_stop`.
4. `race_vs_quali`.
5. `tyre_deg_fit` (+ wpływ na strategię).
6. `temp_fit`.
Po każdym etapie decyzja według reguły z 2.2: zostawiamy albo wyłączamy.

## 7. Ryzyka

- **OpenF1 niepełne i od 2023:** zmienne 3.3, 3.4 i temperatura toru mają krótką historię (~90 wyścigów). Gdy źródło
  zawiedzie, czynnik się wyłącza, bez zgadywania.
- **Limity API:** backfill rozłożony w czasie; pierwsze dni po wdrożeniu historia jest niepełna.
- **Szum:** nawet 100 wyścigów to mało. Zmienne o małym efekcie (pit stopy, temperatura) mogą nie przejść reguły 2.2,
  i to jest akceptowalny wynik, a nie porażka.
- **Przeuczenie:** mimo rosnącego okna wagi wielu czynników naraz pozostają zagrożone; granice wag i ściąganie ku
  bazie zostają.
- **Źródło oficjalnej siatki** wymaga weryfikacji w pierwszym kroku; jeśli OpenF1 jej nie podaje stabilnie, kary
  uwzględniamy dopiero po zakończeniu wyścigu w ocenie, a na żywo ostrzegamy tylko komunikatem, gdy wykryjemy rozjazd.

## 8. Otwarte kwestie

- Sposób łączenia sesji Q1/Q2/Q3 w jeden numer (`quali_gap`).
- Dokładna korekta na paliwo przy pomiarze zużycia.
- Próg "wysokiego zużycia toru" dla strategii.
- Rozmiar budżetu backfillu na uruchomienie (N wyścigów).
