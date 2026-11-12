# F1 Prediction App — specyfikacja projektu (sezony 2026/2027)

Data: 2026-11-12. Status: do akceptacji (wersja 2: pełna automatyzacja czynników).

## 1. Cel

Darmowa, osobista aplikacja PWA na telefon z Androidem do śledzenia weekendów F1 w sezonach 2026 i 2027. Pokazuje kalendarz w czasie polskim, pogodę toru, klasyfikacje oraz predykcje (kwalifikacje, wyścig, strategia opon) jako szanse procentowe.

Kryterium sukcesu: w weekend wyścigowy użytkownik otwiera ikonę na ekranie głównym i od razu widzi godziny sesji, pogodę i tabelę szans wszystkich kierowców (w 2026 jest 11 zespołów, czyli 22 bolidy). Po wyścigu klasyfikacje i predykcje aktualizują się bez ręcznej pracy.

Założenia: użytkownik jest jeden (ewentualnie znajomi), bez logowania. Koszt 0 zł. Użytkownik **nie musi niczego wpisywać ręcznie**: wszystkie czynniki są wyliczane z danych, a ręczne nadpisania są tylko opcjonalnym bezpiecznikiem. Dziś (12.11.2026) sezon 2026 jest praktycznie zakończony, więc dane 2026 służą do kalibracji i testu wstecznego, a 2027 jest głównym sezonem na żywo.

## 2. Architektura (statyczna PWA + robot)

1. **Pobieranie i liczenie** — skrypt Pythona uruchamiany przez GitHub Actions. Pobiera dane, liczy predykcje, zapisuje JSON.
2. **Przechowywanie** — pliki JSON w repozytorium (`public/data/`). Bez bazy danych.
3. **Wyświetlanie** — aplikacja React (Vite) na Vercel. Tylko czyta JSON, przelicza godziny na `Europe/Warsaw`, działa offline (service worker).

## 3. Źródła danych i ograniczenia

| Dane | Źródło | Uwagi |
|---|---|---|
| Kalendarz, sesje, sprinty, wyniki, klasyfikacje, historia torów | Jolpica F1 API | Wyniki po zakończeniu sesji. |
| Prognoza pogody toru | Open-Meteo (forecast) | Bez klucza, do 16 dni naprzód. |
| Historyczna pogoda wyścigów | Open-Meteo (archive) | Do ustalenia, które wyścigi były mokre. |
| Tempo z treningów, mieszanki i stinty opon, zdarzenia SC/VSC, prędkość na okrążeniu | OpenF1 (nieoficjalne, darmowe) | Wsadowo, nie na żywo. Bywa niepełne. |
| Profile torów (szacunki awaryjne) | Plik w repozytorium, szacunki autora aplikacji | Oznaczone jako "szacunek". Używane tylko, gdy telemetria zawiedzie. |

Poprawki bolidów nie są wpisywane ręcznie. Ich skutek wykrywa czynnik "zmiana formy w weekendzie" (sekcja 4.1) po pierwszym treningu. Przed pierwszym treningiem model o poprawkach nie wie.

Zasady awaryjne:
- Brak OpenF1: czynniki zależne od niego są pomijane (waga 0), aplikacja pokazuje "mało danych".
- Awaria Jolpica: żaden plik nie jest nadpisany, proces kończy się błędem (powiadomienie z GitHub).
- Brak prognozy pogody (wyścig za więcej niż 16 dni): pole puste, komunikat "Brak prognozy".

## 4. Model predykcji

### 4.1 Czynniki (jeden plik = jeden czynnik)

Każdy czynnik zwraca ocenę dla każdego kierowcy lub `None`, gdy nie ma danych. Model łączy je z wagami.

- siła bolidu w sezonie (tempo zespołu, nowsze wyniki ważą więcej),
- forma kierowcy (ostatnie 5 rund),
- historia kierowcy na torze (nowsze lata ważą więcej),
- tempo z treningów, sprowadzone do wspólnej mieszanki opon,
- **zmiana formy w weekendzie** — tempo zespołu w treningach minus jego tempo sezonowe. Wykrywa skutek poprawek bez wpisywania ich,
- **dopasowanie bolidu do toru** — po co najmniej 6 rundach sezonu model sprawdza, na jakich typach zakrętów dany zespół jest mocny (regresja grzbietowa, ostrożna), i stosuje to do profilu bieżącego toru,
- **umiejętność deszczowa** — z historii: wyścigi mokre wskazuje pogoda archiwalna, a kierowca jest porównywany z **partnerem z zespołu** (odsunięcie wpływu bolidu). Wynik jest ściągany ku zeru zależnie od liczby mokrych wyścigów; debiutant ma 0. Czynnik aktywny, gdy prognozowane prawdopodobieństwo deszczu ≥ 0,2,
- niezawodność zespołu i kierowcy (odsetek DNF, wygładzony ku średniej),
- pozycja startowa (tylko w modelu wyścigu), z wagą zależną od toru.

### 4.2 Statystyki toru

Dla każdego toru: **trudność wyprzedzania** (średnia zmiana pozycji względem startu, odsetek wygranych z pole, odsetek wygranych spoza top 3, nowsze lata ważą więcej), prawdopodobieństwo SC i VSC (z historii OpenF1, od 2023). Tor bez historii: średnia ze wszystkich torów albo stałe domyślne. Opcjonalne ręczne nadpisanie zawsze wygrywa.

### 4.3 Profil toru

Podział zakrętów na wolne, średnie i szybkie oraz udział prostych. Liczony z prędkości bolidu na okrążeniu (OpenF1): zakręt = lokalne minimum prędkości o wyraźnej głębokości, klasyfikowane po minimalnej prędkości. Gdy telemetria zawiedzie, używany jest plik szacunków. Opcjonalne nadpisanie ma pierwszeństwo.

### 4.4 Kwalifikacje i wyścig

- Kwalifikacje: osobny model (bez pozycji startowej).
- Wyścig: pozycja startowa (przewidziana albo rzeczywista po kwalifikacjach) wchodzi do tempa z wagą `siła startu × trudność wyprzedzania toru`.
- Początek sezonu (pierwsze 3 rundy): ryzyko DNF i SC jest mnożone przez stałą większą od 1.

### 4.5 Symulacja

Monte Carlo, 10 000 rozegrań, stałe ziarno. Losowość: gorszy dzień, błędy w boksie (więcej pit-stopów = więcej chaosu), awarie, SC/VSC. Wynik: szansa na wygraną, podium, punkty, rozkład pozycji, oczekiwane punkty dla każdego kierowcy.

### 4.6 Strategia opon

Najbardziej prawdopodobna strategia i alternatywa z temperatury, deszczu, historii stintów toru i szansy na SC. Reguły i progi są stałe (patrz sekcja 4.8).

### 4.7 Auto-wagi

Po każdym wyścigu robot dostraja **wagi czynników, siłę startu i poziom losowości**, minimalizując błąd przewidywania zwycięzcy (Brier) na rundach bieżącego sezonu. Zabezpieczenia:
- zmiana jest ostrożna: nowa waga = baza + λ × (najlepsza − baza), gdzie λ rośnie z liczbą rund (`rundy / (rundy + K)`),
- każda waga ma dolną i górną granicę,
- waga wpisana na listę zablokowanych nie jest ruszana,
- poniżej 3 rund nic się nie zmienia,
- historia wag jest zapisywana i widoczna w aplikacji.

### 4.8 Co jest statyczne, a co dynamiczne

**Statyczne (ustawienia w pliku, zmienia je tylko użytkownik):** tempo zanikania starych lat (połowa wagi co 3 lata), przelicznik siły, wpływ liczby pit-stopów i ryzyka SC na chaos, mnożnik początku sezonu, domyślne SC/VSC (55% / 25%), próg deszczu dla opon przejściowych (0,6), próg SC dla alternatywnej strategii (0,6), domyślna liczba pit-stopów, progi klasyfikacji zakrętów, liczba symulacji, ziarno, tabela punktów, baza i granice wag.
**Dynamiczne (liczy robot):** wszystkie wartości czynników, wagi czynników, siła startu, poziom losowości, statystyki i profile torów.
**Opcjonalne nadpisania (domyślnie puste):** statystyki toru, profile torów, umiejętności deszczowe.

### 4.9 Ocena modelu

Po każdym wyścigu zapisywane jest przewidywanie obok wyniku wraz z miarami trafności. Test wsteczny na sezonie 2026 (bez podglądania przyszłości) służy do dostrojenia wartości bazowych.

## 5. Harmonogram aktualizacji

GitHub Actions (cron, czasy przybliżone). Poza weekendem co kilka godzin, w weekend wyścigowy (pt–nd) co 30–60 min, po wyścigu: wyniki, klasyfikacje, ocena, auto-wagi. Etapy predykcji: przed weekendem, po treningach, po kwalifikacjach, po sprincie, po zmianie prognozy, po wyścigu.

**Poza zakresem (wersja 1):** szanse na żywo w trakcie wyścigu.

## 6. Ekrany (zakładki na dole)

1. **Weekend** (ekran startowy) — godziny sesji, pogoda, strategia, szansa SC/VSC, szanse procentowe (kwalifikacje i wyścig).
2. **Klasyfikacje** — kierowcy i zespoły.
3. **Kalendarz** — cały sezon, szczegóły rundy po kliknięciu.
4. **Model** — czynniki użyte i pominięte, wagi z historią zmian, trafność predykcji.

Brak nadchodzącej rundy (koniec sezonu, kalendarz nieopublikowany): komunikat zamiast pustego ekranu.

## 7. Struktura plików

```
f1-prediction-app/
├── data-pipeline/
│   ├── fetch/          Jolpica, Open-Meteo, OpenF1
│   ├── factors/        czynniki, statystyki i profile torów
│   ├── simulate/       kwalifikacje, wyścig, strategia
│   ├── data/           szacunki profili torów
│   ├── config.py  tuning.py  evaluation.py  run.py
├── public/data/        wygenerowane JSON (w tym weights.json)
├── src/                screens, components, lib
└── .github/workflows/
```

## 8. Obsługa błędów

Zachowanie poprzednich plików przy awarii API, walidacja JSON przed zapisem, wartości domyślne i oznaczenie "mało danych" przy braku danych, wyłączanie czynników bez danych zamiast zgadywania.

## 9. Testowanie

- Python (pytest, zapisane próbki, stałe ziarno): czynniki, statystyki i profile torów, symulacja (np. waga pozycji startowej większa na Monako niż na Monzy, szanse sumują się do 100%), auto-wagi (granice, blokady, ostrożność), pipeline i awarie.
- Frontend (vitest): konwersja czasu (w tym zmiana czasu i inna strefa urządzenia), ekrany na przykładowych JSON, stany brzegowe.
- Ręcznie: PWA na Androidzie (instalacja, offline).

## 10. Hosting

GitHub (konto istnieje; repozytorium publiczne dla nielimitowanych minut Actions) i Vercel (konto do założenia, logowanie przez GitHub). Oba plany darmowe.

## 11. Otwarte kwestie

- Wartości bazowe wag zostaną dostrojone testem wstecznym na sezonie 2026.
- Jakość czynników zależnych od OpenF1 (trening, profile torów, SC) zależy od kompletności tego źródła. Przy braku danych czynnik jest wyłączany.
- Szacunki profili torów w pliku to wiedza ogólna autora aplikacji, nie dane oficjalne, i zostają oznaczone jako szacunek.
