# Haus-Wiki

Zentrale, interaktive Dokumentation der Haustechnik. Läuft lokal auf dem Raspberry Pi im Heimnetz, ohne Cloud.
Einstieg ist der klickbare Schaltplan; jedes Element führt zu Kenndaten, Gerätetyp, Dokumenten und offenen Punkten.

## Grundprinzipien

- **Daten und Darstellung getrennt.** Alles Inhaltliche steht in YAML-Dateien. Die Website in `site/` wird daraus erzeugt und nie von Hand bearbeitet.
- **BMK verknüpft alles.** Jedes Element hat ein Betriebsmittelkennzeichen nach DIN EN 81346 (z. B. `-4F3`). Dateiname = BMK ohne Minus (`4F3.yaml`).
- **Schaltpläne im QElectroTech-Format.** Die `.qet`-Datei ist die einzige Quelle der Zeichnung. `werkzeuge/render.py` zeichnet daraus die SVG-Pläne; QElectroTech selbst wird nicht gebraucht, kann die Datei aber jederzeit öffnen.
- **Status je Element und je Wert:** `geprueft` (vor Ort oder per Dokument bestätigt), `ungeprueft` (aus dem Plan übernommen), `fehlt` (Angabe fehlt noch).
- **Keine geratenen Werte.** Was unklar ist, kommt unter `offene_punkte` und erscheint auf der Prüfliste.

## Ordner

```
wiki.yaml                 Titel, Repo-Link, Liste der Anlagen
offene-punkte.yaml        Prüfpunkte ohne festes Gerät
CHANGELOG.md              Was sich je Ausbaustufe geändert hat
anlagen/<anlage>/
  anlage.yaml             Name, Ort, Blätter
  plan/                   .qet-Quelle (+ ursprünglicher PDF-Plan zum Nachschlagen)
  elemente/<BMK>.yaml     ein Element pro Datei
typen/<typ>/typ.yaml      Gerätetyp (Hersteller, Modell) + Datenblätter im selben Ordner
dokumente/<anlage>/<BMK>/ Fotos, Messprotokolle zu einem Element
code/                     Software, z. B. ESPHome-YAML
werkzeuge/                build.py, render.py, check.py, qet_import.py, Vorlagen, CSS/JS
deploy/                   systemd-Timer und Caddy-Konfiguration für den Pi
site/                     erzeugte Website (nicht in Git)
```

## Ein Element pflegen

Beispiel `anlagen/verteilung/elemente/4F3.yaml`:

```yaml
bmk: "-4F3"
bezeichnung: "Vorsicherung Wallbox"
art: leitungsschutzschalter
blatt: 4
status: ungeprueft
werte:
  bemessung: { wert: "B25A", status: ungeprueft }
typ: null                 # Verweis auf typen/<id>, z. B. abb-s201
seriennummer: null
einbaudatum: null
links: []                 # - { titel: Weboberfläche, url: "http://..." }
dokumente: []             # - { titel: Foto, datei: foto.jpg }  (liegt in dokumente/verteilung/4F3/)
offene_punkte:
  - "Bemessung B25A gegen Zuleitung -4W2 prüfen."
```

Nach der Prüfung vor Ort: Wert korrigieren, `status: geprueft` setzen, erledigten Punkt löschen.

## Pflege der Pläne

Pläne und Daten pflegt Claude. Jede Änderung kommt als Pull Request mit Vorher/Nachher-Bildern
der betroffenen Blätter; nach der Freigabe („passt“) wird gemergt und der Pi übernimmt sie automatisch.

Ablauf einer Planänderung:

1. `.qet` unter `anlagen/<anlage>/plan/` bearbeiten (Elemente, Leiter, Texte).
2. `python3 werkzeuge/qet_import.py anlagen/<anlage>` legt YAML-Dateien für neue BMK an (bestehende bleiben unberührt).
3. `python3 werkzeuge/check.py` zeigt Abweichungen zwischen Plan und Daten.
4. `python3 werkzeuge/build.py` und Sichtprüfung der Blätter.

## Bauen

```
python3 werkzeuge/check.py     # Widersprüche anzeigen
python3 werkzeuge/build.py     # Website nach site/ erzeugen
```

Benötigt: Python 3, PyYAML, Jinja2. Sonst nichts.

## Einrichtung auf dem Pi

```
sudo apt install git python3-yaml python3-jinja2 caddy
git clone git@github.com:pgrewe89/haus-wiki.git /home/pi/haus-wiki   # Zugriff per Deploy-Key (nur lesen)
cd /home/pi/haus-wiki && python3 werkzeuge/build.py

# Webserver
sudo cp deploy/Caddyfile /etc/caddy/Caddyfile && sudo systemctl reload caddy

# Automatisch aktualisieren (alle 10 Minuten git pull + bauen)
sudo cp deploy/haus-wiki-update.* /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now haus-wiki-update.timer
```

Danach ist das Wiki unter `http://<pi-adresse>:8080/` erreichbar. Benutzername und Pfad in `deploy/` ggf. anpassen.
