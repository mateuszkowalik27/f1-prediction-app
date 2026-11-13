# F1 Prediction App

Darmowa aplikacja na telefon (PWA) do śledzenia weekendów Formuły 1: kalendarz w czasie polskim, pogoda toru,
klasyfikacje oraz predykcje kwalifikacji, wyścigu i strategii opon jako szanse procentowe.

## Jak to działa (w skrócie)

Jak gazeta: redakcja pisze, kiosk wydaje.

- **Robot (GitHub Actions)** co kilka godzin (w weekendy wyścigowe co 30 minut) pobiera dane z darmowych serwisów
  (Jolpica, Open-Meteo, OpenF1), liczy predykcje i zapisuje je jako pliki JSON w `public/data/`.
- **Aplikacja (Vercel)** tylko czyta te pliki i je wyświetla. Nic nie liczy, więc działa szybko, a bez internetu
  pokazuje ostatnio pobrane dane.

Predykcje to symulacja wyścigu 10 000 razy z losowymi wahnięciami. Szanse to odsetek symulacji, w których kierowca
wygrał, stanął na podium albo zdobył punkty.

## Pierwsze uruchomienie (jednorazowo, ok. 15 minut)

Potrzebujesz kont na GitHubie (masz) i Vercel (darmowe, logowanie przez GitHub).

1. **Repozytorium na GitHubie.** Utwórz nowe repozytorium o nazwie `f1-prediction-app`.
   Ustaw je jako **publiczne** (wtedy robot ma nielimitowane darmowe minuty). Nie ma w nim niczego prywatnego.
2. **Wypchnij kod.** W folderze projektu:
   ```bash
   git checkout main
   git merge build/app
   git remote add origin https://github.com/TWOJ_LOGIN/f1-prediction-app.git
   git push -u origin main
   ```
3. **Włącz robota.** W repozytorium wejdź w zakładkę **Actions**, jeśli GitHub o to zapyta, kliknij zielony przycisk
   włączenia workflow. Potem wybierz **Update data** i **Run workflow**. Po 1–2 minutach powinien być zielony
   przebieg, a w repozytorium pojawi się commit od `github-actions[bot]` z nowymi danymi.
4. **Wdróż aplikację na Vercel.** Zaloguj się na vercel.com przez GitHub, kliknij **Add New → Project**, wybierz
   repozytorium. Ustawienia zostaw domyślne (Vercel sam rozpozna Vite: komenda `npm run build`, katalog `dist`).
   Kliknij **Deploy**. Dostaniesz adres typu `f1-prediction-app.vercel.app`.
5. **Dodaj do ekranu głównego Androida.** Otwórz adres w Chrome → menu (trzy kropki) → **Zainstaluj aplikację**
   (albo „Dodaj do ekranu głównego"). Ikona pojawi się jak każdej aplikacji, a otwarta działa pełnoekranowo.
   Sprawdź tryb samolotowy: aplikacja powinna nadal pokazywać ostatnie dane.

Od teraz każdy commit robota z nowymi danymi sam uruchamia wdrożenie na Vercel.

## Co możesz zmieniać

Wszystko, co dotyczy modelu, jest w jednym pliku: `data-pipeline/config.py`.

| Chcesz | Zmień |
|---|---|
| Zablokować wagę, żeby robot jej nie ruszał | dopisz jej nazwę do `LOCKED_WEIGHTS`, np. `{"car_pace"}` (obowiązuje wtedy wartość z `FACTOR_WEIGHTS`) |
| Zmienić bazową wagę czynnika | `FACTOR_WEIGHTS` (robot stroi je ostrożnie w granicach z `WEIGHT_BOUNDS`) |
| Poprawić trudność wyprzedzania lub ryzyko safety cara toru | `TRACK_OVERRIDES`, np. `{"monaco": TrackOverride(overtaking_difficulty=0.95)}` |
| Poprawić profil zakrętów toru | `TRACK_PROFILE_OVERRIDES` |
| Ustawić umiejętność deszczową kierowcy | `WET_SKILL_OVERRIDES`, np. `{"max_verstappen": 2.0}` |
| Zmienić progi strategii opon | `RAIN_START_INTERMEDIATE`, `SC_ALT_THRESHOLD`, `DEFAULT_STOPS` |

Nadpisania są opcjonalne i domyślnie puste: wszystko liczy się samo z danych.

Wagi, które robot dostroił, są w `public/data/weights.json` (z historią zmian), a ocena trafności modelu w
`public/data/model.json`. Aplikacja ich nie pokazuje (zakładkę Model usunięto), ale pliki nadal się aktualizują.

### Dodanie nowego czynnika do modelu

1. Utwórz plik w `data-pipeline/factors/`, np. `nowy_czynnik.py`, z klasą mającą `name` i metodę
   `score(ctx)`. Zwraca słownik `{id_kierowcy: ocena}` (wyższa = lepiej) albo `None`, gdy brak danych.
   Wzoruj się na `driver_form.py`.
2. Dopisz klasę do listy w `data-pipeline/factors/registry.py`.
3. Dopisz wagę w `FACTOR_WEIGHTS` i granice w `WEIGHT_BOUNDS` w `config.py` oraz polską nazwę w
   `src/lib/labels.js` (`FACTOR_LABELS`).
4. Dopisz test w `tests/` i uruchom `pytest`.

## Uruchamianie lokalnie

```bash
# część licząca (Python)
python3 -m venv .venv && .venv/bin/pip install -r data-pipeline/requirements.txt
.venv/bin/pytest -q                                         # testy
.venv/bin/python data-pipeline/run.py --out public/data     # pobranie danych i przeliczenie
.venv/bin/python data-pipeline/evaluation.py --season 2026  # test wsteczny modelu na sezonie

# aplikacja (React)
npm install
npm test -- --run   # testy
npm run dev         # podgląd na http://localhost:5173
npm run build       # wersja produkcyjna do katalogu dist
```

## Model v2: historia, kary na starcie i nowe zmienne

- **Historia wyścigów** (`public/data/history/`): dla każdego zakończonego wyścigu od 2022 roku robot raz liczy i zapisuje
  cechy (strata w kwalifikacjach, czasy pit stopów, tempo wyścigowe, zużycie opon, temperatura, oficjalna siatka).
  Uzupełnia je stopniowo (kilka wyścigów na uruchomienie, żeby mieścić się w limitach API). Ręcznie:
  `.venv/bin/python data-pipeline/backfill.py --out public/data --budget 30`.
- **Kary na starcie:** po kwalifikacjach robot bierze oficjalną siatkę z OpenF1 (z karami i startami z alei serwisowej).
  Na ekranie Weekend pojawia się karta „Kary na starcie". Przed kwalifikacjami kar nie zgadujemy.
- **Uczciwa ocena nowych zmiennych:** każda zmienna przechodzi „bramkę poza próbką": wagi dla danego sezonu są
  strojone tylko na wcześniejszych, a wynik z czynnikiem porównuje się z wynikiem bez niego
  (`.venv/bin/python data-pipeline/oos.py --factor NAZWA`). Zmienna zostaje, gdy średnio poprawia wynik i pogarsza go w
  najwyżej jednym z trzech sezonów testowych (2024–2026). Wyniki bazowe: `public/data/oos.json`.
- **Kalibracja szans:** `.venv/bin/python data-pipeline/calibrate.py` dopasowuje jeden parametr, który spłaszcza lub
  wyostrza szanse na wygraną (plik `public/data/calibration.json`). Stosowana jest dopiero po kwalifikacjach, gdy znamy siatkę.
- **Zużycie opon wpływa na strategię:** na torach o dużym zużyciu wariant alternatywny ma dodatkowy postój, a pewność
  strategii spada o jeden stopień.

### Wyniki bramek (Brier poza próbką, średnio z czynnikiem / bez, mniej = lepiej)

| Czynnik | Wynik | Decyzja |
|---|---|---|
| `quali_gap` (strata w kwalifikacjach) | 0,03210 / 0,03218 | zostaje, ale zysk bardzo mały |
| `pit_stop` (czas pit stopów) | 0,03129 / 0,03210 | zostaje (lepszy w 3 z 3 sezonów) |
| `race_vs_quali` (tempo wyścigowe vs kwalifikacyjne) | 0,03186 / 0,03128 | wypadł (waga 0) |
| `tyre_deg_fit` (zużycie opon dopasowane do toru) | 0,03128 / 0,03129 | wypadł (waga 0) |
| `temp_fit` (temperatura) | 0,03173 / 0,03129 | wypadł (waga 0) |

Czynniki, które wypadły, zostają w kodzie z wagą 0 i wpisem w `LOCKED_WEIGHTS` (`config.py`): można je wrócić, gdy
będzie więcej wyścigów. Uwaga: `pit_stop` może częściowo wynikać z tego, że najlepsze zespoły mają też najlepsze załogi.

## Jak oceniamy model (model v3, etap 1)

Dawniej oceniliśmy model tylko po tym, czy dał dużo szans zwycięzcy: jedno pytanie na wyścig, a 24 wyścigi rocznie to za mało,
żeby odróżnić zysk od szczęścia. Teraz używamy **RPS** (ranked probability score) dla **całej kolejności mety**: każdy z ok.
20 kierowców dostaje karę tym większą, im dalej od prawdziwego miejsca był jego przewidywany rozkład (0 = idealnie, mniej =
lepiej). Z jednego wyścigu mamy więc kilkanaście razy więcej informacji.

Oceniamy **trzy rzeczy osobno**: prognozę *przed kwalifikacjami* (tę widzisz od wtorku do piątku), *po kwalifikacjach* (znana
siatka) i samą *kolejność kwalifikacji*. Każde porównanie dwóch wersji modelu ma **przedział 90%** (bootstrap po wyścigach):
zmiana jest „lepsza" tylko wtedy, gdy cały przedział leży po stronie poprawy, inaczej jest „niejednoznaczna" i zostaje stan
dotychczasowy. Narzędzie: `python data-pipeline/oos.py` (raport) i `python data-pipeline/oos.py --factor NAZWA` (bramka czynnika).

Punkt odniesienia (2026-11-13, po usunięciu `pit_stop`, wyścigi testowe 2024-2026, 68 wyścigów, średni RPS):

| Zestaw wag | przed kwal. | po kwal. | kwalifikacje |
|---|---|---|---|
| bazowe (używa robot) | 0,1224 | 0,1147 | 0,1122 |
| dostrojone walk-forward | 0,1250 | 0,1115 | 0,1162 |
| sama siatka (siła = 0) | 0,1645 | 0,1178 | 0,1740 |

- Model jest **wyraźnie lepszy od samej siatki** na wszystkich trzech poziomach (po kwalifikacjach różnica -0,0031, przedział
  od -0,0045 do -0,0018; przed kwalifikacjami -0,042). Dawna miara (zwycięzca) tego nie wykazywała.
- **Dostrojone wagi nie są lepsze**: poprawiają poziom, pod który je strojono (po kwalifikacjach, -0,0032), ale pogarszają
  prognozy przed kwalifikacjami (+0,0026) i kwalifikacje (+0,0040). Dlatego robot używa teraz **wag bazowych**
  (`USE_TUNED_WEIGHTS = False` w `config.py`). Zastrzeżenie: wagi bazowe były w v1 dobrane na sezonie 2026, więc dla niego
  porównanie jest korzystne dla bazowych.

Bramka nową miarą (2026-11-13) dla czynników z v2:
- `pit_stop` **wypada** (waga 0): po kwalifikacjach i w kwalifikacjach wyraźnie pogarsza wynik, przed kwalifikacjami bez wyraźnej różnicy.
  Dawna miara (zwycięzca) go ratowała; pełna kolejność tego nie potwierdza.
- `quali_gap` **zostaje bez zmian**, choć automat zwróciłby „wypada": pomaga przed kwalifikacjami i w kwalifikacjach, a po
  kwalifikacjach lekko szkodzi (dubluje informację z siatki). Rozstrzyga to etap 2 (osobna siła kwalifikacyjna i wyścigowa).

### Etap 2: osobna siła kwalifikacyjna i wyścigowa

Model ma teraz **dwie siły**: *kwalifikacyjną* (jedno okrążenie; zasila prognozę kwalifikacji i losowanie siatki przed
kwalifikacjami) i *wyścigową* (tempo na dystansie). Mają osobne wagi (`QUALI_FACTOR_WEIGHTS` w `config.py`, ustawione ręcznie).
`quali_gap` służy tylko kwalifikacjom; kwalifikacje wpływają na wyścig wyłącznie przez miejsce na starcie. Losowość kwalifikacji
(`QUALIFYING_NOISE = 0,7`) wybrana na sezonach 2022-2023, na testowych 2024-2026 jest blisko optimum.

Wynik (2026-11-13, 68 wyścigów testowych, średni RPS, osobne siły vs dawna wspólna siła):

| Poziom | osobne | wspólna | różnica, przedział 90% | werdykt |
|---|---|---|---|---|
| przed kwalifikacjami | 0,1206 | 0,1226 | -0,0020 [-0,0030; -0,0010] | lepiej |
| po kwalifikacjach | 0,1148 | 0,1147 | +0,0001 [-0,0000; +0,0002] | bez różnicy |
| kwalifikacje | 0,1066 | 0,1117 | -0,0051 [-0,0066; -0,0036] | lepiej |

Czyli kwalifikacje i prognozy sprzed kwalifikacji są wyraźnie lepsze, a po kwalifikacjach nic się nie pogorszyło.

### Etap 3: nowy rdzeń siły

Dotychczasowa „siła" to średnia punktów (tylko top 10, wrażliwa na pecha). Dodano: **oceny w stylu Elo** (`ratings.py`: model
Plackett-Luce, auto i kierowca osobno, uczone z całej kolejności mety, kierowcy bez mety pomijani w rankingu, rozgrzewka na ośmiu
sezonach wstecz), czynnik **`rating_race`**, czynnik **`pace_race`** (czyste tempo okrążeń z OpenF1, od 2023) i **`rating_quali`**
(rozkład straty w kwalifikacjach na auto i kierowcę). Bramka (RPS, wariant minus baza, przedział 90%, 68 wyścigów):

| Wariant | przed kwal. | po kwal. | werdykt |
|---|---|---|---|
| oceny zamiast punktów (`rating_race`) | -0,0002 [-0,0006; +0,0001] | +0,0000 | bez różnicy |
| czyste tempo (`pace_race`) | -0,0002 [-0,0002; -0,0001] | -0,0001 | wchodzi |
| oceny + połowa punktów | -0,0002 [-0,0004; -0,00003] | -0,0001 | wchodzi |
| **oceny + tempo + połowa punktów (`v3_core`)** | **-0,0003 [-0,0005; -0,0001]** | -0,0001 | **wchodzi (używa robot)** |
| `rating_quali` zamiast `quali_gap` (kwalifikacje) | kwal. +0,0016 [+0,0008; +0,0024] | | **wypada** |

Efekt `v3_core` jest mały (ok. 0,3% RPS przed kwalifikacjami), ale jednoznaczny kierunkowo i nie pogarsza prognoz po kwalifikacjach.
Prosta średnia straty kierowcy (`quali_gap`) okazała się w kwalifikacjach lepsza niż rozkład na auto i kierowcę. Parametry ocen dobrano
na sezonach 2022-2023 (krajobraz płaski: różnice ~0,0001 RPS). Wagi wyścigu: `rating_race` 0,17, `pace_race` 0,10, `car_pace` 0,12,
`driver_form` 0,06. Punkt odniesienia po etapie 3 (średni RPS, wagi bazowe): przed kwal. 0,1203, po kwal. 0,1147, kwalifikacje 0,1066.

## Wyniki sesji w Kalendarzu

Po rozwinięciu rundy zakończone sesje mają przycisk „Wyniki": treningi i kwalifikacje sprintu (najlepszy czas
kierowcy, z OpenF1), kwalifikacje (Q1, Q2, Q3), sprint i wyścig (czas zwycięzcy, straty, DNF z powodem; z Jolpica).
Osobny, lekki workflow (`update-results.yml`) sprawdza to co 10 minut w piątek-niedzielę i zapisuje wyniki do
`public/data/results/<sezon>-<runda>.json` (tylko bieżący sezon) 10 minut po końcu sesji. Przez 3 godziny odświeża je,
bo źródła dopisują dane z opóźnieniem, potem tabela zostaje. Brakujące ponawia do 6 razy na sesję. GitHub nie
gwarantuje punktualności crona, więc wyniki bywają kilka-kilkanaście minut później. Sesji, które się nie odbyły, nie
dotyka. Tabele na wąskim ekranie przewijają się w bok.

### Logo zespołów

W tabelach wyników przy kierowcy jest logo jego zespołu (białe w ciemnym motywie, ciemne w jasnym) i numer w barwach
zespołu. Pliki leżą w `src/assets/teams/<constructorId>.svg`. Źródła: Ferrari, Aston Martin, Audi
i Cadillac z biblioteki simple-icons (CC0); McLaren (sam znak „speedmark", bez napisu), Mercedes, Alpine i Haas z Wikimedia Commons, a Racing Bulls
i Red Bull (dwa byki ze słońcem, z grafiki na Wikipedii, słońce z obwódką wokół byków) z plików Wikipedii (przycięte do samego znaku zmianą `viewBox`). To znaki towarowe zespołów, użyte tylko informacyjnie.
Williams: nowy znak „W" (2026) narysowany ręcznie jako wektor, bo nie znalazłem darmowego pliku SVG (kształt
odmierzony z oficjalnej grafiki). Nowy zespół: dodaj SVG pod jego `constructorId` z Jolpica i kolor w `src/lib/teams.js`.

## Ograniczenia, o których warto wiedzieć

- **Poprawki bolidów model widzi dopiero po piątkowych treningach** (przez zmianę tempa zespołu). Wcześniej nie wie,
  że zespół coś wprowadził.
- **Dane z OpenF1** (treningi, opony, safety car, telemetria toru) pochodzą z nieoficjalnego darmowego źródła i bywają
  niepełne. Gdy ich brakuje, odpowiednie czynniki się wyłączają, a aplikacja pokazuje „mało danych".
- **Profile torów**, gdy telemetria zawiedzie, bierze się z pliku `data-pipeline/data/track_profile_estimates.json`.
  To szacunki autora aplikacji, a nie dane oficjalne.
- **Szanse na żywo w trakcie wyścigu nie są liczone.** Aplikacja aktualizuje się po sesjach.
- **Predykcje to prawdopodobieństwa.** Faworyt z 40% szans przegrywa w 60% wyścigów.
- **Skład kierowców.** Przed pierwszym wyścigiem sezonu pochodzi z poprzedniego roku (aplikacja o tym ostrzega).
  Po kwalifikacjach bierze prawdziwy skład z ich wyników, razem z zastępstwami i zmianami zespołów.
- **Ocena trafności.** Wartości w `public/data/oos.json` są liczone poza próbką (wagi dla sezonu nie widzą tego
  sezonu), ale to nadal tylko ok. 70 wyścigów, a szum jest duży. Uczciwa miara to „Przewidywania, które faktycznie
  widziałeś" (`live_evaluation` w `model.json`): prognoza zapisana tuż przed startem i porównana z wynikiem; pojawi
  się po pierwszych wyścigach z robotem.
- **„Poza próbką" nie jest w pełni czyste.** Bazowe wagi i stałe z v1 (`FACTOR_WEIGHTS`, `GRID_BASE_WEIGHT`,
  `RACE_NOISE_BASE`) były strojone na sezonie 2026, a progi obcinania wartości odstających (`QUALI_GAP_CLIP`,
  `PIT_DELTA_CLIP`, `RACE_PACE_CLIP`) dobrano, patrząc na rundę 20. sezonu 2026. Wynik 2026 jest więc optymistyczny;
  porównania „z czynnikiem / bez" są na to dużo mniej wrażliwe. Kalibracja (τ) jest dopasowana i oceniana na tych
  samych ok. 68 przewidywaniach, więc jej poprawa jest liczona na próbce, na której ją dobrano.
- **Reguła „zostawiamy zmienną" ma małą moc.** Przy zerowym efekcie przechodzi mniej więcej co drugi raz, a
  sprawdzono sześć zmiennych po kolei. `quali_gap` (zysk 0,00008, gorszy w 2025) uznaj za prowizoryczny, a `pit_stop`
  może po części mierzyć ogólną siłę zespołu, nie samą szybkość załogi.
- **Niekompletne agregaty z OpenF1 są dopełniane.** Przegląd znalazł 21 z 90 wyścigów od 2023 roku z brakującą częścią
  danych (okrążenia, pogoda albo siatka), zapisanych jako kompletne. Robot ponawia teraz takie wyścigi do trzech prób
  i nie zamraża świeżo zakończonych (poniżej 2 dni). Dopóki historia się nie dopełni, werdykty bramki dla
  `race_vs_quali`, `tyre_deg_fit` i `temp_fit` opierają się na części danych; po dopełnieniu warto je sprawdzić ponownie.
- **Historia z OpenF1 zaczyna się w 2023 roku**, więc zmienne z okrążeń, opon, temperatury i oficjalnej siatki mają
  krótszą historię niż wyniki z Jolpica (od 2022).
- **Temperatura w modelu to temperatura powietrza** (prognoza podaje powietrze, nie tor); temperaturę toru zapisujemy
  tylko do oszacowania zużycia opon.
- **Kary na starcie** uwzględniamy dopiero po kwalifikacjach. Nie sprawdzono jeszcze, jak szybko po nich OpenF1
  udostępnia oficjalną siatkę przed prawdziwym wyścigiem.
- **Poza sezonem** (grudzień-marzec) klasyfikacja pokazuje ostatnią zakończoną tabelę z oznaczeniem sezonu.
- Jolpica ma limit ok. 200 zapytań na godzinę. Robot zapamiętuje dane zakończonych sezonów w cache GitHub Actions,
  żeby się w nim mieścić.

## Struktura projektu

```
data-pipeline/   Python: pobieranie (fetch/), czynniki (factors/), symulacje (simulate/), auto-wagi (tuning.py)
public/data/     wygenerowane pliki JSON czytane przez aplikację
src/             aplikacja React: ekrany (screens/), klocki (components/), pomocnicze (lib/)
tests/           testy Pythona
.github/         workflow robota (update-data.yml)
docs/            specyfikacja i plan implementacji
```
