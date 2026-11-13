# Model v3: uczciwa ocena, nowy rdzeń siły, osobne kwalifikacje i wyścig

Data: 2026-11-13. Status: do akceptacji. Rozszerza `2026-11-12-model-v2-variables-design.md` (nie zastępuje go).

## 1. Cel i decyzje użytkownika

Poprawić jakość szans (wyścig, kwalifikacje) oraz to, **czy w ogóle umiemy to zmierzyć**. Wyjście: research z 2026-11-13
(ablacje na 68 wyścigach 2024-2026) pokazał, że obecny test nie odróżnia dobrego czynnika od złego:

- Brier zwycięzcy: pełny model 0,0292 vs sama siatka 0,0282, różnica w szumie (przedział od -0,0022 do +0,0042);
  do wykrycia zysku 0,001 potrzeba ok. 1500 wyścigów.
- `practice_pace`, `weekend_shift`, `wet_skill` (30% wag) w teście wstecznym nie mają danych, więc nigdy nie były sprawdzone.
- Prognozy sprzed kwalifikacji (te, które widzi użytkownik) i same kwalifikacje nigdy nie były oceniane.
- Ogony są za cienkie: ok. 6 z 68 wyścigów wygrał kierowca z prognozą poniżej 2% (średnio 0,1%).

**Zatwierdzone przez użytkownika (2026-11-13):** lepsza miara oceny; lepszy rdzeń siły; wspólna losowość zespołu i grubsze
ogony; dynamika sezonu i grupowanie po dostawcy silnika; osobne kwalifikacje i wyścig; tempo z FP3 do kwalifikacji, tempo z
FP2 do wyścigu (obie tylko w weekendach bez sprintu); tempo ze sprintu jako dodatkowa informacja w 6 weekendach sprinterskich
(waga umiarkowana).

**Odrzucone:** rynek (Polymarket, kursy); odtwarzanie danych treningowych wstecz od 2023 (czynniki treningowe działają od
teraz, bez testu wstecznego, patrz sekcja 7).

## 2. Kolejność prac (każdy etap = osobny plan, test, werdykt)

1. Miara oceny (nowy wynik, ocena sprzed kwalifikacji i kwalifikacji, przedziały ufności).
2. Osobne kwalifikacje i wyścig (dwie siły, dwa zestawy wag).
3. Nowy rdzeń siły (oceny dynamiczne w stylu Elo, kierowca osobno od zespołu, czyste tempo okrążeń).
4. Wspólna losowość zespołu i grube ogony.
5. Czynniki treningowe: FP2 long-run, FP3 do kwalifikacji, tempo ze sprintu.
6. Trend sezonu i grupowanie po dostawcy silnika.

Etap 1 jest warunkiem reszty: każdy kolejny etap przechodzi bramkę nową miarą.

## 3. Etap 1: miara oceny

**Problem.** Oceniamy tylko "czy model dał zwycięzcy dużo". To jedno pytanie na wyścig.

**Rozwiązanie.** Oceniamy całą kolejność mety. Dla każdego kierowcy symulacja daje rozkład miejsc (`position_distribution`,
z DNF jako ostatnią kategorią). Główna miara: **RPS** (ranked probability score) dla tego rozkładu względem faktycznego miejsca,
uśredniony po kierowcach i wyścigach; mniej = lepiej. RPS jest miarą "właściwą" dla wyników uporządkowanych (kara rośnie z
odległością od faktycznego miejsca) i daje ok. 20 obserwacji na wyścig zamiast jednej. Pozostają jako pomocnicze: Brier
zwycięzcy, podium i top 10, log-strata zwycięzcy (z dolnym ograniczeniem 0,001) i średni błąd miejsca.

**Trzy poziomy oceny** (każdy osobno, dla sezonów testowych 2024-2026):
1. **Przed kwalifikacjami:** `grid=None` (siatka losowana w symulacji); to widzi użytkownik od wtorku do piątku.
2. **Po kwalifikacjach:** znana siatka (dzisiejszy test).
3. **Kwalifikacje:** przewidziana kolejność kwalifikacji (z `simulate/qualifying.py`) vs faktyczna (Jolpica, od 2022).

**Przedziały ufności.** Każde porównanie dwóch wersji modelu: różnica RPS na wyścig, bootstrap po wyścigach (4000 prób),
przedział 90%. Zasada bramki: czynnik / zmiana **zostaje**, gdy przedział różnicy leży w całości po stronie poprawy na poziomie
"przed" lub "po" kwalifikacjach i nie ma pogorszenia na pozostałym poziomie. W przeciwnym razie werdykt "niejednoznaczny":
istniejące zostaje bez zmian, nowe nie wchodzi (albo wchodzi z wagą 0). Wynik zapisujemy w komentarzu konfiguracji, jak dotąd.

**Strojenie wag.** Wyniki ablacji pokazały, że wagi dostrojone na wcześniejszych sezonach wypadły gorzej od bazowych (0,0316 vs
0,0292, przy zastrzeżeniu, że bazowe były dobrane na 2026). Oceniamy zawsze **wagi bazowe obok dostrojonych**; dostrojone
wchodzą tylko wtedy, gdy wyraźnie wygrywają (ta sama reguła z przedziałem).

**Wynik na zewnątrz.** `oos.json` dostaje nowe pola (RPS i przedziały dla trzech poziomów); aplikacja ich nie wyświetla.

## 4. Etap 2: osobne kwalifikacje i wyścig

Dziś jedna "siła" kierowcy zasila symulację kwalifikacji i wyścigu, a `quali_gap` wpływa na siłę w wyścigu. Zmiana:

- **Siła kwalifikacyjna** (jedno okrążenie): zasila wyłącznie `simulate/qualifying.py`. Czynniki: `quali_gap`, (etap 5) tempo
  z FP3 lub kwalifikacji sprintu, `car_track_fit` w wersji kwalifikacyjnej, ocena kwalifikacyjna z etapu 3.
- **Siła wyścigowa** (tempo na dystansie): zasila symulację wyścigu. Czynniki: ocena wyścigowa z etapu 3, `driver_form`,
  `track_history`, `pit_stop`, (etap 5) FP2 long-run i tempo ze sprintu. `quali_gap` **nie** wchodzi do siły wyścigowej.
- Kwalifikacje wpływają na wyścig **tylko przez pozycję startową** (jak dziś, z oficjalną siatką z karami).
- Dwa zestawy wag, strojone osobno (wyścig miarą RPS wyścigu, kwalifikacje miarą RPS kwalifikacji). Obie siły dzielą bazę
  (ocena auta z etapu 3), więc rozchodzą się tylko tam, gdzie dane to uzasadniają.
- `QUALIFYING_NOISE` (dotąd nieprzestrojony) jest strojony na historycznych kwalifikacjach.

## 5. Etap 3: rdzeń siły

Dziś `car_pace` to średnia punktów zespołu (tylko top 10, wrażliwa na awarie i safety cary), a `driver_form` średnia punktów
kierowcy (miesza kierowcę z autem).

- **Oceny dynamiczne** (uogólnione Elo / Plackett-Luce, aktualizowane online po każdym wyścigu na podstawie **całej kolejności**):
  ocena auta (zespołu) oraz **poprawka kierowcy** względem kolegi z zespołu. Siła = ocena auta + poprawka kierowcy. Osobne
  tory dla wyścigu i kwalifikacji. Tempo uczenia (K) strojone poza próbką.
- **Awarie techniczne** (status z Jolpica: silnik, skrzynia, hydraulika itp.) nie obniżają oceny umiejętności; są modelowane
  osobno przez niezawodność (jak dziś `reliability`).
- **Czyste tempo okrążeń** (agregaty `race_pace` z OpenF1, od 2023) jako drugi sygnał: przeliczone na jednostki oceny i
  mieszane z oceną z wyników. Dla 2022 jest tylko ocena z wyników.
- **Rozgrzewka:** oceny kierowców (poprawki) rozpędzamy na sezonach 2018-2021 (Jolpica, zbiory zakończone, cache na dysku).
  Oceny aut zerujemy na granicy ery przepisów. Sezon `S` startuje od ocen z `S-1` ściągniętych ku średniej.
- Stare czynniki `car_pace` i `driver_form` zostają w kodzie do porównania; nowy rdzeń przechodzi bramkę z etapu 1.

## 6. Etap 4: wspólna losowość zespołu i grube ogony

Dziś każdy kierowca dostaje niezależną porcję losowości z krzywej dzwonowej. Zmiana (w obu symulacjach):

- **Wspólny los zespołu:** każda para dostaje wspólny wstrząs (np. ustawienie auta nie pasuje do toru), a obok niego mały
  wstrząs indywidualny. Dwa parametry: `TEAM_NOISE`, `DRIVER_NOISE`.
- **Chaos (grube ogony):** z pewnym prawdopodobieństwem wyścig dostaje wielokrotnie większą losowość (mieszanka rozkładów).
  Prawdopodobieństwo i mnożnik zależą od ryzyka safety cara toru i szansy deszczu (`track.sc_probability`, prognoza).
- **Cel kalibracji:** udział wyścigów wygranych przez kierowcę z prognozą poniżej 2% ma wyjść zbliżony do prognozowanego;
  faworyci (ponad 35%) nie mają być przeszacowani (dziś średnio 60% przy faktycznych 55%). Parametry strojone miarą z etapu 1.
- Istniejąca kalibracja `tau` zostaje jako ostatni krok; jej wpływ jest raportowany osobno.

## 7. Etap 5: czynniki treningowe (bez danych wstecz)

Źródło: OpenF1 (okrążenia i stinty bieżącego weekendu), już używane w `practice_pace`. **Nie odtwarzamy treningów od 2023**
(decyzja użytkownika), więc te czynniki nie mają testu wstecznego. Zasady zastępcze:

- **Umiarkowana stała waga** (np. 0,08-0,12 siły danego typu), bez automatycznego strojenia, z granicami w `WEIGHT_BOUNDS`.
- **Ocena na bieżąco:** do zamrożonej prognozy zapisujemy **dwie wersje** (z nowymi czynnikami treningowymi i bez nich).
  Po ok. 10 weekendach porównujemy je miarą z etapu 1 (`live_evaluation`); czynnik wypada, jeśli jego wersja nie jest lepsza.
- Brak danych (sesja się nie odbyła, brak okrążeń) wyłącza czynnik, jak dotąd.

**Czynniki i weekendy:**

| Weekend | Do siły wyścigowej | Do siły kwalifikacyjnej |
|---|---|---|
| Zwykły (FP1, FP2, FP3) | `fp2_long_run` (tempo z długich przejazdów FP2) | `fp3_quali_sim` (symulacja kwalifikacji z FP3) |
| Sprinterski (FP1, SQ, Sprint) | `sprint_pace` (czyste tempo ze sprintu, waga umiarkowana) | kwalifikacje sprintu (SQ), patrz niżej |

- `fp2_long_run`: stinty min. 5 czystych okrążeń na tej samej mieszance (bez okrążeń wyjazdowych, wjazdowych, wolnych o ponad
  `SLOW_LAP_RATIO`), korekta na paliwo (`FUEL_EFFECT_S_PER_LAP`) i na mieszankę (jak w `adjusted_practice`), mediana na
  kierowcę, względem stawki. Ryzyka: sandbagging, nierówne obciążenie paliwem.
- `fp3_quali_sim`: najlepsze okrążenie na najmiększej mieszance z końcówki sesji (wykrywanie symulacji kwalifikacji, nie
  samego najlepszego czasu), względem stawki. Ryzyko: różne tryby silnika, zmiana przyczepności toru.
- `sprint_pace`: czyste tempo okrążeń ze sprintu względem stawki; dodatkowa informacja tylko w 6 weekendach; krótszy dystans,
  więc inne zużycie opon niż w niedzielę.
- **Weekend sprinterski, kwalifikacje:** nie ma FP3, więc czynnika z treningu do kwalifikacji nie liczymy (zgodnie z decyzją
  użytkownika). **Do rozstrzygnięcia:** czy użyć wyniku kwalifikacji sprintu (SQ, prawdziwa sesja kwalifikacyjna z tego samego
  weekendu) jako sygnału do głównych kwalifikacji. Propozycja: tak, jako `sq_quali` z umiarkowaną wagą, bo to dane kwalifikacyjne,
  a nie trening.

## 8. Etap 6: trend sezonu i silniki

- **Trend:** ocena auta dostaje składnik tempa zmiany (lokalny trend): zespół z poprawkami przyspiesza, inny zwalnia. Dziś
  stały okres połowicznego zaniku (`FORM_HALF_LIFE_ROUNDS`). Siłę trendu strojemy miarą z etapu 1.
- **Grupowanie po dostawcy silnika:** tabela `ENGINE_SUPPLIER` w konfiguracji (ręcznie, co sezon), np. 2026: Mercedes
  (mercedes, mclaren, williams, alpine), Ferrari (ferrari, haas, cadillac), Honda (aston_martin), Red Bull-Ford (red_bull, rb),
  Audi (audi). Ocena auta bez własnych wyników startuje od średniej dostawcy, w miarę zbierania wyników przechodzi na własną
  (ściąganie `n/(n+K)`). Klienci nie jadą jak fabryka (McLaren w Melbourne ok. 0,85 s za Mercedesem), więc to punkt startowy,
  nie wyrok.

## 9. Testowanie

TDD jak dotąd. Etap 1: testy RPS na prostych przypadkach (idealna prognoza = 0, odwrotna = max), bootstrap deterministyczny przy
ziarnie, ocena trzech poziomów na atrapach. Etapy 2-6: test jednostkowy każdej zmiennej na zapisanych próbkach prawdziwych
odpowiedzi, test integracyjny pipeline z atrapami, bramka z etapu 1 uruchamiana ręcznie (`oos.py --factor`, jak dotąd).
Raport "przed i po" każdego etapu trafia do komentarza w `config.py` i do README.

## 10. Wpływ na pipeline i interfejs

- `oos.json`: nowe pola; `weekend.json`: możliwa druga lista przewidywań (kwalifikacje z osobnej siły); `predictions/*.json`:
  dwie wersje prognozy (z czynnikami treningowymi i bez).
- Interfejs bez zmian poza tym, że liczby się zmienią. Ewentualna karta "skąd się wzięły szanse" jest poza zakresem.

## 11. Poza zakresem

Rynek i kursy; odtwarzanie danych treningowych wstecz; modele czarnoskrzynkowe (lasy losowe, sieci); symulacja okrążenie po
okrążeniu; temperatura toru jako czynnik; przeliczanie historii przed 2018.

## 12. Ryzyka

- **Szum i mało wyścigów:** nawet z RPS to 68 wyścigów testowych; werdykty "niejednoznaczny" będą częste i to jest uczciwy wynik.
- **Czynniki treningowe bez testu wstecznego:** zaczynają z ostrożną wagą i dowodem na bieżąco; mogą wypaść po 10 weekendach.
- **Czas strojenia:** walk-forward z wieloma wersjami modelu trwa minuty; uruchamiane ręcznie, nie w robocie.
- **Przeuczenie dwóch zestawów wag:** granice wag i ściąganie ku bazie zostają; dostrojone wagi tylko, gdy wyraźnie lepsze od bazowych.
- **Ręczna tabela silników:** wymaga aktualizacji co sezon (jeden plik, test sprawdza pokrycie wszystkich zespołów kalendarza).

## 13. Otwarte kwestie

- Czy `sq_quali` (SQ do głównych kwalifikacji) wchodzi (propozycja: tak).
- Dokładny kształt "chaosu" (mieszanka dwóch rozkładów normalnych czy rozkład t) oraz początkowe wartości parametrów.
- Zakres rozgrzewki ocen kierowców (2018-2021 jako punkt wyjścia; sprawdzić koszt zapytań do Jolpica).
- Czy dwie wersje zamrożonej prognozy wystarczą do oceny na bieżąco, czy dodać też zapis surowych czynników.
