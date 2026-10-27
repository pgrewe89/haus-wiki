# Änderungen

Jede Ausbaustufe bekommt hier einen kurzen Eintrag. Die einzelnen Änderungen stehen zusätzlich in der Git-Historie.

## Stufe 1: Hauptverteilung (27.10.2026)

- Grundgerüst: YAML-Daten je BMK, Gerätetypen, Generator `werkzeuge/build.py`, Prüfung `werkzeuge/check.py`.
- Schaltplan "Elektroverteilung 2026" übernommen: QElectroTech-Datei unter `anlagen/verteilung/plan/`, der ursprüngliche PDF-Plan liegt daneben zum Nachschlagen.
- Eigener Renderer `werkzeuge/render.py`: zeichnet alle Blätter direkt aus der .qet als SVG. Kein QElectroTech und kein PDF-Export mehr nötig; abgeglichen gegen den PDF-Plan.
- Alle 5 Blätter klickbar (Einspeisung, Wärmepumpe, Photovoltaik, Haus 1, Schaltschrankansicht). Die Klickflächen kommen aus den Positionen in der .qet-Datei.
- 41 Elemente angelegt, alle mit Status **ungeprüft**. Bezeichnungen aus der BMK-Legende (Blatt 5), Werte aus den Feldern der .qet-Datei.
- 7 Gerätetypen angelegt (ABB S201, S203, F204 B, S751/3-E35, Hager SH363N, Victron EM540, DEHN 909396), noch ohne Datenblätter.
- Prüfliste mit den ersten Widersprüchen aus dem Plan, u. a. -2F3 (C16A oder B16A?), -1P3 (BMK ohne Minus), -4F3/-4W2 (B25A an 5x2,5 mm²).
- Einrichtung auf dem Pi vorbereitet: `deploy/` mit systemd-Timer und Caddy-Konfiguration.
- Automatische Prüfung bei jedem Pull Request (GitHub Actions: `check.py` und `build.py`).
