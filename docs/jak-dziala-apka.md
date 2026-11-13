# Jak działa F1 Prediction App (po ludzku)

Ten dokument tłumaczy całą aplikację bez żargonu: skąd bierze dane, co robi robot, jak liczy szanse i jak to trafia na Twój telefon.
Techniczne szczegóły (liczby, wyniki testów) są w `README.md`.

## 1. Całość na jednym obrazku

```
  ŹRÓDŁA DANYCH                ROBOT (GitHub)                    STRONA (Vercel)            TELEFON
  ─────────────                ──────────────                    ───────────────            ───────
  Jolpica   (wyniki)    ─┐
  OpenF1    (okrążenia) ─┼──►  Skrypt Pythona liczy szanse ──►  pliki JSON w repozytorium ──► Vercel buduje  ──► aplikacja
  Open-Meteo (pogoda)   ─┘     i zapisuje wyniki do plików       (folder public/data)        stronę z plików      czyta pliki
                                     ▲                                                                              i je pokazuje
                                     └── uruchamia się sam co kilka minut / godzin
```

Najważniejsza myśl: **aplikacja na telefonie niczego nie liczy**. Cała „głowa" (model) siedzi w robocie. Robot zapisuje gotowe wyniki do
zwykłych plików, a aplikacja tylko je wczytuje i ładnie pokazuje. Dlatego jest darmowa i szybka: nie ma serwera ani bazy danych.

## 2. Skąd biorą się dane

| Źródło | Co daje | Uwagi |
|---|---|---|
| **Jolpica** | kalendarz, wyniki wyścigów, kwalifikacji i sprintów, klasyfikacje, skład kierowców | limit ok. 200 zapytań na godzinę, więc robot zapamiętuje zakończone sezony na dysku |
| **OpenF1** | okrążenia i opony z treningów, kwalifikacji i wyścigów, safety cary, pogoda na torze, oficjalna siatka startowa z karami | dane od 2023 roku; bywa, że ogranicza liczbę zapytań (robot wtedy czeka i ponawia) |
| **Open-Meteo** | prognoza pogody na godzinę startu wyścigu (czas lokalny toru) | do 16 dni do przodu |

Żadnych kluczy ani kont nie potrzeba.

## 3. Robot: co robi krok po kroku

Robot to dwa „zadania" na GitHubie (`.github/workflows/`), które uruchamiają skrypty Pythona z folderu `data-pipeline/`:

- **`update-data.yml`**: co 6 godzin, a w piątek, sobotę i niedzielę co 30 minut. Liczy prognozy i klasyfikacje.
- **`update-results.yml`**: w weekendy wyścigowe co 10 minut. Pobiera tylko wyniki zakończonych sesji (treningi, kwalifikacje, sprint, wyścig).

Główny przebieg (`data-pipeline/run.py`) robi po kolei:

1. Pobiera kalendarz i klasyfikacje (Jolpica).
2. Uzupełnia **historię**: dla zakończonych wyścigów liczy raz „agregaty" (m.in. różnice czasów w kwalifikacjach, tempo okrążeń) i zapisuje je w `public/data/history/`.
3. Wybiera **najbliższy wyścig** (taki, którego wyścig jeszcze się nie skończył).
4. Zbiera dane o tym weekendzie: skład kierowców, pogodę, safety cary toru, oficjalną siatkę po kwalifikacjach, tempo z treningów.
5. Liczy **siłę** każdego kierowcy (jak szybki jest, patrz niżej) i symuluje wyścig i kwalifikacje 10 000 razy.
6. Zapisuje wyniki do plików JSON. Jeśli coś się zmieniło, robot robi commit, a Vercel buduje nową wersję strony.

Jeśli któreś źródło zawiedzie (np. OpenF1 ma przerwę), robot nie wywraca się: wyłącza tylko to, co zależało od tego źródła, i liczy resztę.

## 4. Pliki z danymi (`public/data/`)

| Plik | Co w nim jest |
|---|---|
| `weekend.json` | prognoza najbliższego weekendu: harmonogram, pogoda, strategia opon, szanse w kwalifikacjach i wyścigu, kary |
| `standings.json` | klasyfikacja kierowców i zespołów (z numerami, skrótami i zespołami) |
| `calendar.json` | cały kalendarz sezonu |
| `results/<sezon>-<runda>.json` | wyniki zakończonych sesji rundy (to widzisz po kliknięciu „Wyniki") |
| `history/…` | policzone raz cechy zakończonych wyścigów (pamięć robota) |
| `predictions/…` | **zamrożona** prognoza tuż przed startem wyścigu, żeby po wyścigu uczciwie sprawdzić, jak się pomyliliśmy |
| `model.json`, `oos.json`, `weights.json`, `calibration.json` | wagi modelu, oceny jakości, korekta „zbyt pewnych siebie" prognoz |
| `meta.json` | kiedy robot ostatnio działał i które źródła zadziałały |

## 5. Jak model liczy szanse

**Krok 1: „siła" kierowcy.** To jedna liczba mówiąca, jak szybki jest teraz. Powstaje z kilku **czynników** (każdy to osobny „sygnał"),
łączonych z wagami. Najważniejsze:
- **oceny aut i kierowców** (jak szachowy ranking; uczone z całej kolejności mety, osobno auto i kierowca),
- **czyste tempo okrążeń** (szybkość bez wpływu pecha),
- **forma i punkty** z ostatnich wyścigów,
- **historia na tym torze**, dopasowanie auta do toru, **umiejętności w deszczu**, **niezawodność**,
- **trening** z bieżącego weekendu (długie przejazdy z FP2, symulacja kwalifikacji z FP3, tempo ze sprintu).

Są **dwie siły**: *kwalifikacyjna* (jedno okrążenie) i *wyścigowa* (tempo na dystansie), z osobnymi wagami.

**Krok 2: symulacja.** Robot „rozgrywa" wyścig 10 000 razy. W każdej symulacji do siły każdego dodaje losowość (pech, szczęście, błędy)
i odejmuje karę za słabe miejsce startowe (na wąskim torze, jak Monako, start znaczy dużo, na Monzie mniej). W części symulacji dodaje **chaos**
(deszcz, safety car, kolizje na starcie: losowość jest wtedy 3 razy większa). Do tego losuje awarie. Ile razy kierowca wygrał, tyle procent szans pokazuje aplikacja.

**Krok 3: korekta.** Po kwalifikacjach, gdy siatka jest znana (z oficjalnymi karami), model liczy od nowa. Szanse są dodatkowo lekko „ściągane"
(kalibracja), bo model bywał zbyt pewny siebie.

## 6. Skąd wiemy, że model jest dobry

Sprawdzamy go na starych wyścigach (2024–2026), udając, że wyniku nie znamy. Miara to **RPS**: dla całej kolejności mety liczy, jak daleko od
prawdy był rozkład miejsc każdego kierowcy (mniej = lepiej). Mierzymy trzy rzeczy osobno: prognozę **przed kwalifikacjami**, **po kwalifikacjach** i
samą **kolejność kwalifikacji**, zawsze z przedziałem „na ile to pewne". Nowy czynnik wchodzi do modelu tylko wtedy, gdy ten test pokaże wyraźną poprawę.
Czynniki z treningów nie mają testu wstecznego, więc robot zapisuje dwie wersje prognozy (z nimi i bez) i po wyścigu je porównuje (`live_comparison`).

## 7. Aplikacja na telefonie

- Napisana w **React** (strona w przeglądarce), zbudowana narzędziem **Vite**. Kod jest w folderze `src/`.
- Trzy zakładki: **Weekend** (`src/screens/Weekend.jsx`), **Klasyfikacje** (`Standings.jsx`), **Kalendarz** (`Calendar.jsx`). Wspólne klocki
  (komórka kierowcy z logo i numerem, tabela wyników, lista sesji) są w `src/components/`.
- To **PWA**: da się ją „zainstalować" na ekranie głównym, a działa jak aplikacja. Pobiera nową wersję sama (sprawdza przy wracaniu do aplikacji i co 30 minut).
  Jeśli coś się wywali, zamiast białego ekranu pokazuje komunikat z przyciskiem „Wyczyść i odśwież".
- Logo zespołów i kolory numerów są w `src/assets/teams/` i `src/lib/teams.js`.

## 8. Hosting i wdrażanie

Kod i dane leżą w repozytorium GitHub. **Vercel** obserwuje gałąź `main`: każdy commit (Twój albo robota) uruchamia budowanie strony i publikację.
Dlatego, żeby coś trafiło do aplikacji, trzeba wypchnąć gałąź `main` (a nie inną). Napis „wersja xxxxxxx" na dole aplikacji to początek numeru commita,
z którego zbudowano stronę.

## 9. Mapa folderów

```
f1-prediction-app/
├── data-pipeline/        ← „mózg": skrypty Pythona robota
│   ├── run.py              główny przebieg (prognoza weekendu)
│   ├── fetch/              pobieranie danych (jolpica.py, openf1.py, openmeteo.py)
│   ├── factors/            czynniki siły (po jednym pliku na sygnał)
│   ├── simulate/           symulacja wyścigu i kwalifikacji (race.py, qualifying.py, noise.py)
│   ├── ratings.py          oceny aut i kierowców (Elo)
│   ├── oos.py, scoring.py  sprawdzanie jakości modelu (RPS, przedziały)
│   └── config.py           wszystkie ustawienia i wagi w jednym miejscu
├── src/                  ← aplikacja (React): zakładki, komponenty, logo
├── public/data/          ← pliki JSON, które czyta aplikacja (zapisuje je robot)
├── tests/                ← testy automatyczne robota
├── .github/workflows/    ← definicje robota (kiedy i co uruchamiać)
└── docs/                 ← specyfikacje i plany prac (docs/superpowers/)
```

## 10. Co jest ręczne (o czym pamiętać)

- **Tabela dostawców silników** (`ENGINE_SUPPLIER` w `data-pipeline/config.py`): sprawdzaj co sezon. Robot ostrzega, gdy brakuje wpisu.
- **Logo i kolory zespołów** nowego zespołu: plik SVG w `src/assets/teams/` i kolor w `src/lib/teams.js`.
- **Decyzja o czynnikach treningowych** po ok. 10 weekendach (czy zostają), na podstawie `live_comparison` w `model.json`.

## 11. Słowniczek

- **Czynnik**: jeden sygnał o sile kierowcy (np. forma, tempo, historia toru).
- **Waga**: jak mocno dany czynnik się liczy w łącznej sile.
- **Symulacja Monte Carlo**: „rozegranie" wyścigu tysiące razy z losowością i policzenie, jak często co się zdarzyło.
- **RPS**: miara błędu prognozy całej kolejności mety (mniej = lepiej).
- **Przedział pewności**: zakres, w którym prawdziwy wynik leży z dużą szansą; jeśli obejmuje zero, nie wiemy, czy jest lepiej, czy gorzej.
- **Kalibracja**: lekkie spłaszczenie prognoz, gdy model okazuje się zbyt pewny siebie.
- **Zamrożona prognoza**: kopia prognozy z chwili tuż przed startem, do uczciwego sprawdzenia po wyścigu.
