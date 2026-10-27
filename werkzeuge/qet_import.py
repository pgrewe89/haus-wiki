"""Legt für jedes BMK aus der .qet eine YAML-Datei an (nur wenn sie fehlt).

Aufruf:  python3 werkzeuge/qet_import.py anlagen/verteilung

Alle übernommenen Werte bekommen den Status "ungeprueft". Bestehende Dateien
werden nie überschrieben; Abweichungen zwischen .qet und YAML meldet check.py.
"""
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
import qet  # noqa: E402

ART = {
    "victronem540": "energiezaehler",
    "drehstromzaehler": "zaehler",
    "klemmenblock": "klemmenblock",
    "selektiver_leitungsschutzschalter": "sls-schalter",
    "dehn909396": "ueberspannungsschutz",
    "disjoncteur4": "lasttrennschalter",
    "sec_fus4": "sicherungstrenner",
    "int_diff_3f-1": "fehlerstromschutzschalter",
    "leitungsschuzschalter_1p": "leitungsschutzschalter",
    "leitungsschutzschalter_3p": "leitungsschutzschalter",
    "rcbo_01": "fi-ls-schalter",
}


def legende(blaetter):
    """BMK -> Bezeichnung aus der BMK-Legende (Texte links auf dem Ansichtsblatt)."""
    paare = {}
    for b in blaetter:
        bmks = {}
        texte = {}
        for t in b["texte"]:
            if t["x"] < 40 and qet.bmk_normal(t["zeilen"][0]):
                bmks[round(t["y"])] = qet.bmk_normal(t["zeilen"][0])
            elif 40 <= t["x"] < 100:
                texte[round(t["y"])] = " ".join(t["zeilen"])
        for y, bmk in bmks.items():
            if y in texte:
                paare[bmk] = texte[y]
    return paare


def q(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def schreibe(ziel, bmk, blatt, art, bezeichnung, werte, typ_id, extra):
    zeilen = [
        f"bmk: {q(bmk)}",
        f"bezeichnung: {q(bezeichnung) if bezeichnung else 'null'}",
        f"art: {art}",
        f"blatt: {blatt}",
        "status: ungeprueft",
        f'quelle: "Schaltplan Elektroverteilung 2026 (.qet/PDF), Blatt {blatt}"',
        "",
        "werte:",
    ]
    for k, v in werte.items():
        zeilen.append(f"  {k}: {{ wert: {q(v)}, status: ungeprueft }}")
    if not werte:
        zeilen[-1] = "werte: {}"
    zeilen += [
        "",
        f"typ: {typ_id or 'null'}",
        "seriennummer: null",
        "einbaudatum: null",
        "",
        "links: []",
        "dokumente: []",
        "",
        "offene_punkte: []",
    ]
    text = "\n".join(zeilen) + "\n"
    if extra:
        text += yaml.safe_dump(extra, allow_unicode=True, sort_keys=False)
    ziel.write_text(text, encoding="utf-8")


def main(anlage_ordner):
    anlage = Path(anlage_ordner)
    cfg = yaml.safe_load((anlage / "anlage.yaml").read_text(encoding="utf-8"))
    blaetter = qet.lade(anlage / cfg["plan"]["qet"])
    namen = legende(blaetter)
    ordner = anlage / "elemente"
    ordner.mkdir(exist_ok=True)
    neu = 0
    for b in blaetter:
        for e in b["elemente"]:
            if not e["bmk"]:
                continue
            datei = ordner / (e["bmk"].lstrip("-") + ".yaml")
            if datei.exists():
                continue
            i = e["info"]
            werte = {}
            if "comment" in i:
                werte["bemessung"] = i["comment"]
            if "description" in i:
                werte["beschreibung_im_plan"] = i["description"]
            schreibe(datei, e["bmk"], b["nr"], ART.get(e["symbol"], "sonstiges"),
                     namen.get(e["bmk"]), werte, None, None)
            neu += 1
        for t in b["texte"]:
            bmk = qet.bmk_normal(t["zeilen"][0])
            if not bmk or bmk[2] not in "WX" or t["x"] < 40:
                continue
            datei = ordner / (bmk.lstrip("-") + ".yaml")
            if datei.exists():
                continue
            werte = {}
            if bmk[2] == "W" and len(t["zeilen"]) >= 3:
                werte = {"kabeltyp": t["zeilen"][1], "aufbau": t["zeilen"][2]}
            schreibe(datei, bmk, b["nr"], "kabel" if bmk[2] == "W" else "klemmleiste",
                     namen.get(bmk), werte, None, None)
            neu += 1
    print(f"{neu} neue Element-Dateien angelegt in {ordner}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "anlagen/verteilung")
