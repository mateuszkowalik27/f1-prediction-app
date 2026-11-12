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

Wagi, które robot dostroił, są w `public/data/weights.json` (z historią zmian), a w aplikacji widać je w zakładce
**Model**.

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
- **Ocena trafności jest optymistyczna.** Zakładka Model pokazuje test wsteczny, w którym wagi są dostrajane na tych
  samych wyścigach, na których model oceniamy. Uczciwsza jest sekcja „Przewidywania, które faktycznie widziałeś":
  prognoza zapisana tuż przed startem i porównana z wynikiem. Pojawi się po pierwszych wyścigach z robotem.
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
