"""Prüft die Daten auf Widersprüche. Exit-Code 1 bei Fehlern.

Aufruf:  python3 werkzeuge/check.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import daten  # noqa: E402


def main():
    wurzel = Path(__file__).resolve().parent.parent
    meldungen = daten.pruefe(daten.lade(wurzel))
    for stufe, text, bezug in meldungen:
        print(f"{stufe.upper():8} {bezug}: {text}")
    fehler = sum(1 for s, _, _ in meldungen if s == "fehler")
    print(f"\n{fehler} Fehler, {len(meldungen) - fehler} Hinweise")
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
