"""Liest eine QElectroTech-Projektdatei (.qet) und liefert Blätter, Elemente,
freie Texte und Rechtecke mit ihren Koordinaten.

Die .qet ist die Quelle für Positionen im Plan. Gerätedaten werden NICHT von
hier gelesen, sondern aus den YAML-Dateien (Ausnahme: qet_import.py beim
erstmaligen Anlegen und check.py beim Abgleich).
"""
import html
import re
import xml.etree.ElementTree as ET

# Umrechnung QElectroTech-Szene -> PDF-Seite (A4 quer, 842 x 595 pt).
# QElectroTech skaliert den Folio-Rahmen (17 x 60 + 20 breit, plus 2 x 5 Rand)
# auf die Seitenbreite und zentriert ihn. Für Blätter mit anderer Spaltenzahl
# muss das neu bestimmt werden (check.py warnt, wenn das Format abweicht).
SEITE_B, SEITE_H = 842.0, 595.0
_SZENE_B = 17 * 60 + 20 + 10
MASSSTAB = (SEITE_B - 2 * 24.25) / _SZENE_B
VERSATZ = 24.25

BMK_MUSTER = re.compile(r"^-?\d+[A-Z]+\d+$")


def nach_pdf(x, y):
    return VERSATZ + x * MASSSTAB, VERSATZ + y * MASSSTAB


def rechteck_nach_pdf(x, y, b, h):
    px, py = nach_pdf(x, y)
    return [round(px, 2), round(py, 2), round(b * MASSSTAB, 2), round(h * MASSSTAB, 2)]


def bmk_normal(label):
    """'1P3' -> '-1P3'; liefert None, wenn es kein BMK ist."""
    label = (label or "").strip()
    if not BMK_MUSTER.match(label):
        return None
    return label if label.startswith("-") else "-" + label


def _vereinige(a, b):
    x1, y1 = min(a[0], b[0]), min(a[1], b[1])
    x2, y2 = max(a[0] + a[2], b[0] + b[2]), max(a[1] + a[3], b[1] + b[3])
    return (x1, y1, x2 - x1, y2 - y1)


def html_zu_text(h):
    h = re.sub(r"(?s)<head>.*?</head>", "", h or "")
    h = re.sub(r"<br ?/?>|</p>", "\n", h)
    t = html.unescape(re.sub(r"<[^>]+>", "", h))
    return [z.strip() for z in t.splitlines() if z.strip()]


def _definitionen(wurzel):
    defs = {}

    def lauf(knoten, pfad):
        for k in knoten:
            if k.tag == "element":
                d = k.find("definition")
                defs[pfad + "/" + k.get("name")] = {
                    n: float(d.get(n)) for n in ("width", "height", "hotspot_x", "hotspot_y")
                }
            elif k.tag == "category":
                lauf(k, pfad + "/" + k.get("name"))

    sammlung = wurzel.find("collection")
    if sammlung is not None:
        lauf(sammlung, "embed:/")
    return defs


def lade(pfad):
    wurzel = ET.parse(pfad).getroot()
    defs = _definitionen(wurzel)
    blaetter = []
    for d in wurzel.iter("diagram"):
        blatt = {
            "nr": int(d.get("order")),
            "titel": d.get("title"),
            "spalten": (int(d.get("cols")), int(d.get("colsize"))),
            "elemente": [],
            "texte": [],
            "rechtecke": [],
        }
        for e in d.iterfind("elements/element"):
            info = {}
            for ei in e.iterfind("elementInformations/elementInformation"):
                if ei.text and ei.text.strip():
                    info[ei.get("name")] = ei.text.strip()
            typ = e.get("type")
            df = defs.get(typ)
            x, y = float(e.get("x")), float(e.get("y"))
            rect = None
            if df and e.get("orientation", "0") == "0":
                rect = (x - df["hotspot_x"], y - df["hotspot_y"], df["width"], df["height"])
                # Beschriftung (BMK, Bemessung) neben dem Symbol mit in die Klickfläche nehmen
                for dt in e.iter("dynamic_elmt_text"):
                    feld = dt.findtext("info_name")
                    if feld in ("label", "comment") and info.get(feld):
                        tb = (x + float(dt.get("x")), y + float(dt.get("y")), len(info[feld]) * 6.5 + 4, 16)
                        rect = _vereinige(rect, tb)
            blatt["elemente"].append({
                "symbol": typ.rsplit("/", 1)[-1].removesuffix(".elmt"),
                "info": info,
                "bmk": bmk_normal(info.get("label")),
                "x": x, "y": y,
                "rect": rect,
                "orientierung": e.get("orientation", "0"),
            })
        for t in d.iterfind("inputs/input"):
            zeilen = html_zu_text(t.get("text"))
            if zeilen:
                blatt["texte"].append({"x": float(t.get("x")), "y": float(t.get("y")), "zeilen": zeilen})
        for s in d.iterfind("shapes/shape"):
            if s.get("type") == "Rectangle":
                x1, x2 = sorted((float(s.get("x1")), float(s.get("x2"))))
                y1, y2 = sorted((float(s.get("y1")), float(s.get("y2"))))
                blatt["rechtecke"].append((x1, y1, x2 - x1, y2 - y1))
        blaetter.append(blatt)
    return sorted(blaetter, key=lambda b: b["nr"])


def text_rechteck(t):
    """Grobe Fläche eines freien Textes (QElectroTech-Standardschrift ~9 pt)."""
    breite = max(len(z) for z in t["zeilen"]) * 6.0 + 8
    hoehe = len(t["zeilen"]) * 13.0 + 8
    return (t["x"], t["y"], breite, hoehe)
