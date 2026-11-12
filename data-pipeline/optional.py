"""Wywołania opcjonalnych źródeł danych: błąd nigdy nie przerywa pracy, tylko wyłącza dane."""
from __future__ import annotations

import sys


def optional(label: str, fn, *args):
    """-> (wynik, błąd?). Każdy wyjątek zamienia na (None, True) z ostrzeżeniem na stderr."""
    try:
        return fn(*args), False
    except Exception as exc:  # noqa: BLE001 — świadomie szeroko: zepsuta odpowiedź obcego API nie może zabić przebiegu
        print(f"UWAGA: {label} nie zadziałało ({type(exc).__name__}: {exc}); pomijam to źródło.", file=sys.stderr)
        return None, True
