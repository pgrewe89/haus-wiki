"""Zeichnet die Blätter einer QElectroTech-Datei (.qet) als SVG.

Damit wird kein QElectroTech und kein PDF-Export gebraucht: Die .qet ist die
einzige Quelle der Zeichnung. Unterstützt wird, was in den Plänen dieses
Projekts vorkommt (Elemente mit eingebetteten Definitionen, Leiter mit und
ohne gespeicherte Segmente, freie Texte, Formen, Rahmen und Schriftfeld).

Koordinaten im SVG sind Szenen-Koordinaten von QElectroTech (1 Einheit = 1 px).
"""
import html
import math
import re
import xml.etree.ElementTree as ET

RAND = 5                    # Rand um den Folio-Rahmen (wie QElectroTech beim Export)
KOPF = 20                   # Höhe der Spaltenköpfe / Breite der Zeilenköpfe
SCHRIFTFELD_H = 50
SCHRIFT = "'Liberation Sans', Arial, Helvetica, sans-serif"
PT_PX = 96 / 72             # Qt-Punktgröße -> Pixel
KLEMMEN_LAENGE = 4          # Terminal::terminalSize
LEITER_AUSLAUF = 9          # Verlängerung eines Leiters aus der Klemme
ASZENT = 0.905              # Oberkante -> Grundlinie (Liberation Sans)
ZEILE = 1.15                # Zeilenabstand
TEXT_DX, TEXT_DY = 2.0, 4.0  # Versatz dynamischer/freier Texte (QGraphicsTextItem)
TEIL_DX, TEIL_DY = 0.0, 0.0  # Versatz statischer Texte in Elementdefinitionen
ORI = {"n": 0, "e": 1, "s": 2, "w": 3}
RICHTUNG = {0: (0, -1), 1: (1, 0), 2: (0, 1), 3: (-1, 0)}
FARBEN = {"black": "#000", "white": "#fff", "green": "#008000", "red": "#f00", "blue": "#00f",
          "gray": "#a0a0a4", "brown": "#a52a2a", "yellow": "#ff0", "cyan": "#0ff",
          "magenta": "#f0f", "lightgray": "#c0c0c0", "orange": "#ffa500", "purple": "#800080",
          "none": "none"}
LINIENSTAERKE = {"none": 0, "thin": 0.5, "normal": 1, "hight": 2, "eleve": 5}
STRICHEL = {"dashed": "4 2", "dotted": "1 2", "dashdotted": "4 2 1 2"}
# Beschriftung des eingebauten Standard-Schriftfelds von QElectroTech
STANDARD_LABEL = {"author": "Autor", "date": "Datum", "file": "Datei", "folio": "Seite"}
QT_STRICHEL = {"DashLine": "4 2", "DotLine": "1 2", "DashDotLine": "4 2 1 2", "DashDotDotLine": "4 2 1 2 1 2"}


def _f(v, d=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def _n(v):
    """Zahl kompakt formatieren."""
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def _e(s):
    return html.escape(str(s), quote=True)


def _schrift(font, standard_pt=9):
    """Qt-Fontstring 'Familie,Punkt,...' -> (px, fett)."""
    teile = (font or "").split(",")
    pt = _f(teile[1], standard_pt) if len(teile) > 1 else standard_pt
    fett = len(teile) > 4 and _f(teile[4]) >= 63
    return pt * PT_PX, fett


# ---------------------------------------------------------------- Definitionen

def lade_definitionen(wurzel):
    defs = {}

    def lauf(knoten, pfad):
        for k in knoten:
            if k.tag == "element":
                defs[pfad + "/" + k.get("name")] = k.find("definition")
            elif k.tag == "category":
                lauf(k, pfad + "/" + k.get("name"))

    sammlung = wurzel.find("collection")
    if sammlung is not None:
        lauf(sammlung, "embed:/")
    return defs


def _stil(style):
    s = dict(p.split(":", 1) for p in (style or "").split(";") if ":" in p)
    farbe = FARBEN.get(s.get("color", "black"), s.get("color", "#000"))
    breite = LINIENSTAERKE.get(s.get("line-weight", "normal"), 1)
    fuell = s.get("filling", "none")
    fuell = FARBEN.get(fuell, fuell if fuell.startswith("#") else "none")
    attr = f'stroke="{farbe if breite else "none"}" stroke-width="{_n(breite)}" fill="{fuell}"'
    if s.get("line-style") in STRICHEL:
        attr += f' stroke-dasharray="{STRICHEL[s["line-style"]]}"'
    return attr


def _pfeil(x, y, wx, wy, art, laenge):
    """Linienende (end1/end2) als SVG. (wx, wy) zeigt vom Linieninneren zum Ende."""
    if art in (None, "none"):
        return ""
    n = math.hypot(wx, wy) or 1
    ux, uy = wx / n, wy / n
    px, py = -uy, ux
    L = laenge or 1.5
    if art == "simple":
        a = (x - ux * L + px * L, y - uy * L + py * L)
        b = (x - ux * L - px * L, y - uy * L - py * L)
        return f'<polyline points="{_n(a[0])},{_n(a[1])} {_n(x)},{_n(y)} {_n(b[0])},{_n(b[1])}" fill="none"/>'
    if art == "triangle":
        a = (x - ux * L + px * L, y - uy * L + py * L)
        b = (x - ux * L - px * L, y - uy * L - py * L)
        return f'<polygon points="{_n(a[0])},{_n(a[1])} {_n(x)},{_n(y)} {_n(b[0])},{_n(b[1])}" fill="#000"/>'
    if art == "circle":
        return f'<circle cx="{_n(x - ux * L)}" cy="{_n(y - uy * L)}" r="{_n(L)}" fill="#000"/>'
    if art == "diamond":
        m = (x - ux * L, y - uy * L)
        pts = [(x, y), (m[0] + px * L, m[1] + py * L), (x - 2 * ux * L, y - 2 * uy * L), (m[0] - px * L, m[1] - py * L)]
        return '<polygon points="' + " ".join(f"{_n(a)},{_n(b)}" for a, b in pts) + '" fill="#000"/>'
    return ""


def _text_svg(x, y, text, px, fett=False, farbe="#000", drehung=0, anker="start", grundlinie="auto", zeilenabstand=None):
    zeilen = str(text).split("\n")
    za = zeilenabstand or px * 1.15
    trans = f' transform="rotate({_n(drehung)} {_n(x)} {_n(y)})"' if drehung else ""
    attr = f'font-size="{_n(px)}" fill="{farbe}" text-anchor="{anker}"'
    if fett:
        attr += ' font-weight="bold"'
    if grundlinie != "auto":
        attr += f' dominant-baseline="{grundlinie}"'
    if len(zeilen) == 1:
        return f'<text x="{_n(x)}" y="{_n(y)}" {attr}{trans}>{_e(zeilen[0])}</text>'
    spans = "".join(f'<tspan x="{_n(x)}" dy="{_n(0 if i == 0 else za)}">{_e(z)}</tspan>' for i, z in enumerate(zeilen))
    return f'<text x="{_n(x)}" y="{_n(y)}" {attr}{trans}>{spans}</text>'


def definition_svg(defn):
    """Statische Grafik einer Elementdefinition (ohne dynamische Texte)."""
    teile = []
    for p in defn.find("description"):
        a = p.attrib
        t = p.tag
        if t == "line":
            x1, y1, x2, y2 = (_f(a.get(k)) for k in ("x1", "y1", "x2", "y2"))
            teile.append(f'<g {_stil(a.get("style"))}><line x1="{_n(x1)}" y1="{_n(y1)}" x2="{_n(x2)}" y2="{_n(y2)}"/>'
                         + _pfeil(x1, y1, x1 - x2, y1 - y2, a.get("end1"), _f(a.get("length1"), 1.5))
                         + _pfeil(x2, y2, x2 - x1, y2 - y1, a.get("end2"), _f(a.get("length2"), 1.5)) + "</g>")
        elif t == "rect":
            teile.append(f'<rect x="{_n(_f(a.get("x")))}" y="{_n(_f(a.get("y")))}" width="{_n(_f(a.get("width")))}" '
                         f'height="{_n(_f(a.get("height")))}" rx="{_n(_f(a.get("rx")))}" ry="{_n(_f(a.get("ry")))}" {_stil(a.get("style"))}/>')
        elif t == "ellipse":
            w, h = _f(a.get("width")), _f(a.get("height"))
            teile.append(f'<ellipse cx="{_n(_f(a.get("x")) + w / 2)}" cy="{_n(_f(a.get("y")) + h / 2)}" rx="{_n(w / 2)}" ry="{_n(h / 2)}" {_stil(a.get("style"))}/>')
        elif t == "circle":
            d = _f(a.get("diameter"))
            teile.append(f'<circle cx="{_n(_f(a.get("x")) + d / 2)}" cy="{_n(_f(a.get("y")) + d / 2)}" r="{_n(d / 2)}" {_stil(a.get("style"))}/>')
        elif t == "arc":
            x, y, w, h = (_f(a.get(k)) for k in ("x", "y", "width", "height"))
            start, winkel = _f(a.get("start")), _f(a.get("angle"))
            cx, cy, rx, ry = x + w / 2, y + h / 2, w / 2, h / 2
            # Qt: Winkel gegen den Uhrzeigersinn ab 3 Uhr, y-Achse nach unten
            p0 = (cx + rx * math.cos(math.radians(start)), cy - ry * math.sin(math.radians(start)))
            p1 = (cx + rx * math.cos(math.radians(start + winkel)), cy - ry * math.sin(math.radians(start + winkel)))
            gross = 1 if abs(winkel) > 180 else 0
            sweep = 0 if winkel > 0 else 1
            stil = _stil(a.get("style")).replace(re.search(r'fill="[^"]*"', _stil(a.get("style"))).group(0), 'fill="none"')
            teile.append(f'<path d="M{_n(p0[0])} {_n(p0[1])}A{_n(rx)} {_n(ry)} 0 {gross} {sweep} {_n(p1[0])} {_n(p1[1])}" {stil}/>')
        elif t == "polygon":
            pts = []
            i = 1
            while f"x{i}" in a:
                pts.append((_f(a[f"x{i}"]), _f(a[f"y{i}"])))
                i += 1
            punkte = " ".join(f"{_n(x)},{_n(y)}" for x, y in pts)
            geschlossen = a.get("closed", "true") != "false"
            stil = _stil(a.get("style"))
            if not geschlossen:
                stil = re.sub(r'fill="[^"]*"', 'fill="none"', stil)
            teile.append(f'<{"polygon" if geschlossen else "polyline"} points="{punkte}" {stil}/>')
        elif t == "text":
            px, fett = _schrift(a.get("font"), _f(a.get("size"), 9))
            farbe = a.get("color", "#000")
            # Position = linke Grundlinie der ersten Zeile
            teile.append(_text_svg(_f(a.get("x")) + TEIL_DX, _f(a.get("y")) + TEIL_DY, a.get("text", ""), px, fett, farbe, _f(a.get("rotation"))))
    return "".join(teile)


def definition_klemmen(defn):
    """uuid -> (x, y, orientierung) der Klemmen in Definitions-Koordinaten."""
    k = {}
    for t in defn.find("description").iter("terminal"):
        k[t.get("uuid")] = (_f(t.get("x")), _f(t.get("y")), ORI.get(t.get("orientation"), 0))
    return k


# ---------------------------------------------------------------- Geometrie

def _drehe(x, y, ori):
    """Drehung um 90°-Schritte im Uhrzeigersinn (QElectroTech-Orientierung)."""
    for _ in range(ori % 4):
        x, y = -y, x
    return x, y


def _leiter_punkte(p1, o1, p2, o2):
    """Automatischer Leiterverlauf wie in QElectroTech (Conductor::generateConductorPath)."""
    N, E, S, W = 0, 1, 2, 3

    def aus(p, o, l):
        dx, dy = RICHTUNG[o]
        return (p[0] + dx * l, p[1] + dy * l)

    d1, d2 = aus(p1, o1, KLEMMEN_LAENGE), aus(p2, o2, KLEMMEN_LAENGE)
    if d1[0] <= d2[0]:
        dep, arr, od, oa = d1, d2, o1, o2
        umkehr = False
    else:
        dep, arr, od, oa = d2, d1, o2, o1
        umkehr = True
    dep0, arr0 = aus(dep, od, LEITER_AUSLAUF), aus(arr, oa, LEITER_AUSLAUF)
    pts = [dep, dep0]
    if arr0[0] > dep0[0]:
        if arr0[1] > dep0[1]:
            if (od == N and oa in (S, W)) or (od == E and oa == W):
                xm = (dep0[0] + arr0[0]) / 2
                pts += [(xm, dep0[1]), (xm, arr0[1])]
            elif (od == S and oa in (N, E)) or (od == W and oa == E):
                ym = (dep0[1] + arr0[1]) / 2
                pts += [(dep0[0], ym), (arr0[0], ym)]
            elif od in (N, E) and oa in (N, E):
                pts.append((arr0[0], dep0[1]))
            else:
                pts.append((dep0[0], arr0[1]))
        else:
            if (od == S and oa in (N, W)) or (od == E and oa == W):
                xm = (dep0[0] + arr0[0]) / 2
                pts += [(xm, dep0[1]), (xm, arr0[1])]
            elif (od == N and oa in (S, E)) or (od == W and oa == E):
                ym = (dep0[1] + arr0[1]) / 2
                pts += [(dep0[0], ym), (arr0[0], ym)]
            elif od in (S, E) and oa in (S, E):
                pts.append((arr0[0], dep0[1]))
            else:
                pts.append((dep0[0], arr0[1]))
    else:
        if arr0[1] > dep0[1]:
            if od == W and oa in (E, S):
                xm = (dep0[0] + arr0[0]) / 2
                pts += [(xm, dep0[1]), (xm, arr0[1])]
            elif od == S and oa in (N, W):
                ym = (dep0[1] + arr0[1]) / 2
                pts += [(dep0[0], ym), (arr0[0], ym)]
            elif od in (W, N) and oa in (W, N):
                pts.append((arr0[0], dep0[1]))
            else:
                pts.append((dep0[0], arr0[1]))
        else:
            if od == W and oa in (E, N):
                xm = (dep0[0] + arr0[0]) / 2
                pts += [(xm, dep0[1]), (xm, arr0[1])]
            elif od == N and oa in (S, W):
                ym = (dep0[1] + arr0[1]) / 2
                pts += [(dep0[0], ym), (arr0[0], ym)]
            elif od in (W, S) and oa in (W, S):
                pts.append((arr0[0], dep0[1]))
            else:
                pts.append((dep0[0], arr0[1]))
    pts += [arr0, arr]
    return list(reversed(pts)) if umkehr else pts


def _profil(start, ziel, segmente):
    """Segmente ab start gehen; Restabstand zu ziel proportional auf innere Segmente verteilen."""
    laengen = [(s.get("orientation") == "horizontal", _f(s.get("length"))) for s in segmente]
    ende_x = start[0] + sum(l for h, l in laengen if h)
    ende_y = start[1] + sum(l for h, l in laengen if not h)
    rest = {True: ziel[0] - ende_x, False: ziel[1] - ende_y}
    neu = list(laengen)
    innen = range(1, len(laengen) - 1) if len(laengen) > 2 else range(len(laengen))
    for horizontal in (True, False):
        if abs(rest[horizontal]) < 0.01:
            continue
        idx = [i for i in innen if laengen[i][0] == horizontal]
        if not idx:
            idx = [i for i in range(len(laengen)) if laengen[i][0] == horizontal]
        if not idx:
            return None
        for i in idx:
            anteil = 1 / len(idx)
            neu[i] = (horizontal, neu[i][1] + rest[horizontal] * anteil)
    if sum(abs(l) for _, l in neu) > 4 * (sum(abs(l) for _, l in laengen) + 1) + 200:
        return None
    pts = [start]
    x, y = start
    for horizontal, l in neu:
        if horizontal:
            x += l
        else:
            y += l
        pts.append((x, y))
    return pts


def _restfrei(start, ziel, segmente):
    ex = start[0] + sum(_f(s.get("length")) for s in segmente if s.get("orientation") == "horizontal")
    ey = start[1] + sum(_f(s.get("length")) for s in segmente if s.get("orientation") != "horizontal")
    return math.hypot(ziel[0] - ex, ziel[1] - ey) < 1


def _auf_weg(p, pts):
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        if (min(ax, bx) - 0.5 <= p[0] <= max(ax, bx) + 0.5 and min(ay, by) - 0.5 <= p[1] <= max(ay, by) + 0.5
                and abs((bx - ax) * (p[1] - ay) - (by - ay) * (p[0] - ax)) < 0.5 * (abs(bx - ax) + abs(by - ay) + 1)):
            return True
    return False


def _verbindungspunkte(wege):
    """Punkte, an denen sich Leiter derselben Klemme trennen (wie Conductor::junctions)."""
    punkte = set()
    for i, (a1, a2, w1) in enumerate(wege):
        for j, (b1, b2, w2) in enumerate(wege):
            if i == j or not ({a1, a2} & {b1, b2}):
                continue
            weg = w1 if a1 in (b1, b2) else list(reversed(w1))   # von der gemeinsamen Klemme aus
            for k in range(1, len(weg) - 1):
                p, weiter = weg[k], weg[k + 1]
                mitte = ((p[0] + weiter[0]) / 2, (p[1] + weiter[1]) / 2)
                if _auf_weg(p, w2) and not _auf_weg(mitte, w2):
                    punkte.add((round(p[0], 1), round(p[1], 1)))
                    break
    return "".join(f'<circle cx="{_n(x)}" cy="{_n(y)}" r="2.5" fill="#000"/>' for x, y in sorted(punkte))


def _vereinfache(pts):
    aus = []
    for p in pts:
        if aus and abs(aus[-1][0] - p[0]) < 1e-6 and abs(aus[-1][1] - p[1]) < 1e-6:
            continue
        if len(aus) >= 2:
            a, b = aus[-2], aus[-1]
            if (abs(a[0] - b[0]) < 1e-6 and abs(b[0] - p[0]) < 1e-6) or (abs(a[1] - b[1]) < 1e-6 and abs(b[1] - p[1]) < 1e-6):
                aus[-1] = p
                continue
        aus.append(p)
    return aus


# ---------------------------------------------------------------- Blatt

class Blatt:
    def __init__(self, diagramm, defs, gesamt):
        self.d = diagramm
        self.defs = defs
        self.gesamt = gesamt
        self.spalten = int(diagramm.get("cols"))
        self.spaltenbreite = _f(diagramm.get("colsize"))
        self.zeilen = int(diagramm.get("rows"))
        self.zeilenhoehe = _f(diagramm.get("rowsize"))
        self.breite = KOPF + self.spalten * self.spaltenbreite
        self.hoehe = KOPF + self.zeilen * self.zeilenhoehe
        self.klemmen_id = {}    # Instanz-Klemmen-ID -> (x, y, ori)
        self.klemmen_uuid = {}  # (Element-uuid, Klemmen-uuid) -> (x, y, ori)
        self.elemente = {}      # Element-uuid -> Instanz

    # Spalte/Zeile wie im Rahmen (für Querverweise)
    def ort(self, x, y):
        sp = int((x - RAND - KOPF) // self.spaltenbreite) + 1
        ze = int((y - RAND - KOPF) // self.zeilenhoehe)
        sp = min(max(sp, 1), self.spalten)
        ze = min(max(ze, 0), self.zeilen - 1)
        return f"{chr(ord('A') + ze)}{sp}"

    def _rahmen(self, titel_felder, vorlage):
        b, h = self.breite, self.hoehe
        t = [f'<g class="rahmen" stroke="#000" stroke-width="1" fill="none">'
             f'<rect x="0" y="0" width="{_n(b)}" height="{_n(h)}"/>'
             + (f'<line x1="{KOPF}" y1="0" x2="{KOPF}" y2="{_n(h)}"/>' if self.d.get("displayrows", "true") == "true" else "")
             + (f'<line x1="0" y1="{KOPF}" x2="{_n(b)}" y2="{KOPF}"/>' if self.d.get("displaycols", "true") == "true" else "")]
        spalten_an = self.d.get("displaycols", "true") == "true"
        zeilen_an = self.d.get("displayrows", "true") == "true"
        if spalten_an:
            for i in range(1, self.spalten):
                x = KOPF + i * self.spaltenbreite
                t.append(f'<line x1="{_n(x)}" y1="0" x2="{_n(x)}" y2="{KOPF}"/>')
        if zeilen_an:
            for i in range(1, self.zeilen):
                y = KOPF + i * self.zeilenhoehe
                t.append(f'<line x1="0" y1="{_n(y)}" x2="{KOPF}" y2="{_n(y)}"/>')
        t.append("</g><g class=\"rahmen-text\" font-size=\"12\" fill=\"#000\" text-anchor=\"middle\">")
        if spalten_an:
            for i in range(self.spalten):
                x = KOPF + (i + 0.5) * self.spaltenbreite
                t.append(f'<text x="{_n(x)}" y="{KOPF / 2 + 4}">{i + 1}</text>')
        if zeilen_an:
            for i in range(self.zeilen):
                y = KOPF + (i + 0.5) * self.zeilenhoehe
                t.append(f'<text x="{KOPF / 2}" y="{_n(y + 4)}">{chr(ord("A") + i)}</text>')
        t.append("</g>")
        t.append(self._schriftfeld(titel_felder, vorlage, standard=not self.d.get("titleblocktemplate")))
        return "".join(t)

    def _schriftfeld(self, werte, vorlage, standard=False):
        y0, b, h = self.hoehe, self.breite, SCHRIFTFELD_H
        if vorlage is None:
            return f'<rect x="0" y="{_n(y0)}" width="{_n(b)}" height="{h}" fill="none" stroke="#000"/>'
        grid = vorlage.find("grid")
        spec = [s for s in grid.get("cols").split(";") if s]
        zeilen_h = [_f(s) for s in grid.get("rows").split(";") if s]
        fest = sum(_f(s[1:-1]) / 100 * b for s in spec if s.startswith("t"))
        breiten = [(_f(s[1:-1]) / 100 * b if s.startswith("t") else (b - fest) * _f(s[1:-1]) / 100 if s.startswith("r") else _f(s)) for s in spec]
        xs = [sum(breiten[:i]) for i in range(len(breiten) + 1)]
        ys = [y0 + sum(zeilen_h[:i]) for i in range(len(zeilen_h) + 1)]
        belegt = {}
        for f in grid.iterfind("field"):
            belegt[(int(f.get("row")), int(f.get("col")))] = f
        t = [f'<g class="schriftfeld"><rect x="0" y="{_n(y0)}" width="{_n(b)}" height="{_n(sum(zeilen_h))}" fill="none" stroke="#000"/>']
        for z in range(len(zeilen_h)):
            for s in range(len(breiten)):
                f = belegt.get((z, s))
                if f is None:
                    # Zelle gehört zu einem Feld darüber (Zeilen-Verbund) -> keine Linie
                    continue
                rs = int(f.get("rowspan", "0")) + 1 if f.get("rowspan") else 1
                if f.get("name") == "title" or (s == 1 and (z + 1, s) not in belegt):
                    rs = len(zeilen_h) - z
                x, y, w, hh = xs[s], ys[z], breiten[s], sum(zeilen_h[z:z + rs])
                t.append(f'<rect x="{_n(x)}" y="{_n(y)}" width="{_n(w)}" height="{_n(hh)}" fill="none" stroke="#000"/>')
                wert = f.findtext("value/translation") or ""
                if standard and f.get("name") == "file":
                    wert = "%filename"
                wert = re.sub(r"%(\w+)", lambda m: werte.get(m.group(1), ""), wert)
                label = ""
                if f.get("displaylabel") == "true":
                    lab = f.find("label/translation[@lang='de']")
                    label = (lab.text + ": ") if lab is not None and lab.text else ""
                    if standard and f.get("name") in STANDARD_LABEL:
                        label = STANDARD_LABEL[f.get("name")] + ": "
                text = label + wert
                if f.get("align") == "center" or f.get("name") == "title" or s == 1:
                    t.append(_text_svg(x + w / 2, y + hh / 2 + 4, text, 12, anker="middle"))
                else:
                    t.append(_text_svg(x + 2, y + hh / 2 + 4, text, 12))
        t.append("</g>")
        return "".join(t)

    def _element(self, e, folio_von_uuid):
        typ = e.get("type")
        defn = self.defs.get(typ)
        x, y, ori = _f(e.get("x")), _f(e.get("y")), int(e.get("orientation", "0"))
        uuid = e.get("uuid")
        self.elemente[uuid] = e
        dk = definition_klemmen(defn) if defn is not None else {}
        for ku, (kx, ky, ko) in dk.items():
            rx, ry = _drehe(kx, ky, ori)
            self.klemmen_uuid[(uuid, ku)] = (x + rx, y + ry, (ko + ori) % 4)
        for t in e.iterfind("terminals/terminal"):
            self.klemmen_id[t.get("id")] = (x + _f(t.get("x")), y + _f(t.get("y")), int(t.get("orientation", "0")))
        teile = []
        info = {ei.get("name"): (ei.text or "") for ei in e.iterfind("elementInformations/elementInformation")}
        label = info.get("label", "")
        attr = f' data-bmk="{_e(label)}"' if label else ""
        teile.append(f'<g class="element"{attr} transform="translate({_n(x)} {_n(y)})">')
        if defn is not None:
            teile.append(f'<g transform="rotate({ori * 90})">{definition_svg(defn)}</g>' if ori else definition_svg(defn))
        # dynamische Texte der Instanz (Position relativ zum Element, nicht mitgedreht)
        for dt in e.iterfind("dynamic_texts/dynamic_elmt_text"):
            text = dt.findtext("text") or ""
            if dt.get("text_from") == "ElementInfo":
                feld = dt.findtext("info_name")
                text = info.get(feld, text) if feld != "label" or label else text
                if defn is not None and defn.get("link_type") in ("next_report", "previous_report"):
                    text = folio_von_uuid(e) or text
            if not text.strip():
                continue
            px, fett = _schrift(dt.get("font"))
            tx, ty = _f(dt.get("x")), _f(dt.get("y"))
            # QGraphicsTextItem: Ursprung oben links, Dokumentrand 4 px
            teile.append(_text_svg(tx + TEXT_DX, ty + TEXT_DY + px * ASZENT, text, px, fett, drehung=_f(dt.get("rotation"))))
        # alte Textfelder (input) der Definition, Wert aus der Instanz
        if defn is not None:
            inst = {i.get("x") + "," + i.get("y"): i.get("text") for i in e.iterfind("inputs/input")}
            for inp in defn.find("description").iterfind("input"):
                text = inst.get(inp.get("x") + "," + inp.get("y"), inp.get("text", ""))
                if text and text.strip() and inp.get("tagg") != "label":
                    px, fett = _schrift(inp.get("font"), _f(inp.get("size"), 9))
                    teile.append(_text_svg(_f(inp.get("x")), _f(inp.get("y")), text, px, fett, drehung=_f(inp.get("rotation"))))
        teile.append("</g>")
        return "".join(teile)

    def _leiter(self, c):
        def klemme(nr):
            t = c.get(f"terminal{nr}")
            el = c.get(f"element{nr}")
            if el and (el, t) in self.klemmen_uuid:
                return self.klemmen_uuid[(el, t)]
            return self.klemmen_id.get(t)

        k1, k2 = klemme(1), klemme(2)
        if not k1 or not k2:
            return ""

        def dock(k):
            dx, dy = RICHTUNG[k[2]]
            return (k[0] + dx * KLEMMEN_LAENGE, k[1] + dy * KLEMMEN_LAENGE)

        segmente = c.findall("segment")
        if segmente:
            # Gespeichertes Profil an die aktuellen Klemmen anpassen (wie
            # QElectroTech): Abweichung auf die inneren Segmente verteilen.
            pts = None
            # Das Profil beginnt an der Klemme von terminal1 (seltener terminal2).
            for a_, b_ in ((k1, k2), (k2, k1)):
                kand = _profil(a_[:2], b_[:2], segmente)
                if kand is not None and math.hypot(kand[-1][0] - b_[0], kand[-1][1] - b_[1]) < 1:
                    if _restfrei(a_[:2], b_[:2], segmente):
                        pts = kand
                        break
            if pts is None:
                kand = _profil(k1[:2], k2[:2], segmente)
                pts = kand
            if pts is None:
                pts = [(k1[0], k1[1])] + _leiter_punkte(dock(k1), k1[2], dock(k2), k2[2]) + [(k2[0], k2[1])]
        else:
            pts = [(k1[0], k1[1])] + _leiter_punkte(dock(k1), k1[2], dock(k2), k2[2]) + [(k2[0], k2[1])]
        pts = _vereinfache(pts)
        self.leiterwege.append(((round(k1[0]), round(k1[1])), (round(k2[0]), round(k2[1])), pts))
        farbe = c.get("color") or "#000"
        teile = [f'<polyline points="{" ".join(f"{_n(x)},{_n(y)}" for x, y in pts)}" fill="none" stroke="{_e(farbe)}" stroke-width="1"/>']
        num = (c.get("num") or "").strip()
        if c.get("displaytext") == "1" and num:
            px = _f(c.get("numsize"), 7) * PT_PX
            if c.get("userx") is not None:
                tx, ty = _f(c.get("userx")), _f(c.get("usery"))
                senkrecht = True
                for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                    if min(ay, by) - 1 <= ty <= max(ay, by) + 1 and min(ax, bx) - 30 <= tx <= max(ax, bx) + 30:
                        senkrecht = abs(ax - bx) < 1e-6
                        break
            else:
                # Text in die Mitte des längsten Segments
                (ax, ay), (bx, by) = max(zip(pts, pts[1:]), key=lambda s: math.hypot(s[1][0] - s[0][0], s[1][1] - s[0][1]))
                tx, ty = (ax + bx) / 2, (ay + by) / 2
                senkrecht = abs(ax - bx) < 1e-6
            if senkrecht:
                dreh = -(360 - _f(c.get("vertirotatetext"), 270)) if _f(c.get("vertirotatetext"), 270) > 180 else _f(c.get("vertirotatetext"))
                teile.append(_text_svg(tx + TEXT_DX, ty + TEXT_DY + px * ASZENT, num, px)
                             .replace("<text ", f'<text transform="rotate({_n(dreh)} {_n(tx)} {_n(ty)})" ', 1))
            else:
                teile.append(_text_svg(tx + TEXT_DX, ty + TEXT_DY + px * ASZENT, num, px))
        return "".join(teile)

    def _freitext(self, inp):
        zeilen, px, fett = _html_zeilen(inp.get("text"), inp.get("font"))
        if not zeilen:
            return ""
        x, y = _f(inp.get("x")), _f(inp.get("y"))
        dreh = _f(inp.get("rotation"))
        t = []
        oben = y
        for z, zpx, zfett in zeilen:
            t.append(_text_svg(x + TEXT_DX, oben + TEXT_DY + zpx * ASZENT, z, zpx, zfett))
            oben += zpx * ZEILE
        g = "".join(t)
        return f'<g transform="rotate({_n(dreh)} {_n(x)} {_n(y)})">{g}</g>' if dreh else g

    def _form(self, s):
        pen, brush = s.find("pen"), s.find("brush")
        farbe = pen.get("color", "#000") if pen is not None else "#000"
        breite = _f(pen.get("widthF"), 1) if pen is not None else 1
        strich = QT_STRICHEL.get(pen.get("style")) if pen is not None else None
        fuell = "none"
        if brush is not None and brush.get("style") not in (None, "NoBrush"):
            stil, bf = brush.get("style"), brush.get("color", "#000")
            fuell = bf if stil == "SolidPattern" else f"url(#{_muster_id(stil, bf)})"
            self.muster.add((stil, bf))
        attr = f'stroke="{farbe}" stroke-width="{_n(breite)}" fill="{fuell}"' + (f' stroke-dasharray="{strich}"' if strich else "")
        x1, y1, x2, y2 = (_f(s.get(k)) for k in ("x1", "y1", "x2", "y2"))
        typ = s.get("type")
        if typ == "Line":
            return f'<line x1="{_n(x1)}" y1="{_n(y1)}" x2="{_n(x2)}" y2="{_n(y2)}" {attr}/>'
        if typ == "Rectangle":
            x, y = min(x1, x2), min(y1, y2)
            return f'<rect x="{_n(x)}" y="{_n(y)}" width="{_n(abs(x2 - x1))}" height="{_n(abs(y2 - y1))}" rx="{_n(_f(s.get("rx")))}" {attr}/>'
        if typ == "Ellipse":
            return f'<ellipse cx="{_n((x1 + x2) / 2)}" cy="{_n((y1 + y2) / 2)}" rx="{_n(abs(x2 - x1) / 2)}" ry="{_n(abs(y2 - y1) / 2)}" {attr}/>'
        if typ == "Polygon":
            pts = [(_f(p.get("x")), _f(p.get("y"))) for p in s.iterfind("points/point")]
            tag = "polygon" if s.get("closed") == "1" else "polyline"
            return f'<{tag} points="{" ".join(f"{_n(a)},{_n(b)}" for a, b in pts)}" {attr}/>'
        return ""

    def svg(self, folio_von_uuid, titel_felder, vorlage, klick=""):
        self.muster = set()
        teile = []
        elemente = sorted(self.d.iterfind("elements/element"), key=lambda e: _f(e.get("z"), 10))
        el_svg = [self._element(e, folio_von_uuid) for e in elemente]
        self.leiterwege = []
        leiter = [self._leiter(c) for c in self.d.iterfind("conductors/conductor")]
        leiter.append(_verbindungspunkte(self.leiterwege))
        formen = [self._form(s) for s in sorted(self.d.iterfind("shapes/shape"), key=lambda s: _f(s.get("z")))]
        texte = [self._freitext(i) for i in self.d.iterfind("inputs/input")]
        defs = "".join(_muster_svg(stil, farbe) for stil, farbe in sorted(self.muster))
        hoehe_gesamt = self.hoehe + SCHRIFTFELD_H
        teile.append(f'<svg xmlns="http://www.w3.org/2000/svg" class="plan-svg" viewBox="0 0 '
                     f'{_n(self.breite + 2 * RAND)} {_n(hoehe_gesamt + 2 * RAND)}" font-family="{SCHRIFT}">')
        teile.append(f'<defs>{defs}</defs>')
        teile.append(f'<rect x="0" y="0" width="{_n(self.breite + 2 * RAND)}" height="{_n(hoehe_gesamt + 2 * RAND)}" fill="#fff"/>')
        teile.append(f'<g transform="translate({RAND} {RAND})">{self._rahmen(titel_felder, vorlage)}</g>')
        teile.append('<g class="formen">' + "".join(formen) + "</g>")
        teile.append('<g class="leiter">' + "".join(leiter) + "</g>")
        teile.append('<g class="elemente" stroke-linecap="square">' + "".join(el_svg) + "</g>")
        teile.append('<g class="texte">' + "".join(texte) + "</g>")
        teile.append(klick)
        teile.append("</svg>")
        return "\n".join(teile)


def _muster_id(stil, farbe):
    return f"m-{stil}-{farbe.lstrip('#')}"


def _muster_svg(stil, farbe):
    """Qt-Pinselmuster näherungsweise als SVG-Pattern."""
    pid = _muster_id(stil, farbe)
    if stil.startswith("Dense"):
        dichte = {"Dense1Pattern": 0.94, "Dense2Pattern": 0.88, "Dense3Pattern": 0.63, "Dense4Pattern": 0.5,
                  "Dense5Pattern": 0.37, "Dense6Pattern": 0.12, "Dense7Pattern": 0.06}.get(stil, 0.5)
        return (f'<pattern id="{pid}" width="4" height="4" patternUnits="userSpaceOnUse">'
                f'<rect width="4" height="4" fill="{farbe}" fill-opacity="{dichte}"/></pattern>')
    linien = {"HorPattern": "M0 2H8", "VerPattern": "M2 0V8", "CrossPattern": "M0 2H8M2 0V8",
              "BDiagPattern": "M0 8L8 0", "FDiagPattern": "M0 0L8 8", "DiagCrossPattern": "M0 8L8 0M0 0L8 8"}.get(stil, "M0 2H8")
    return (f'<pattern id="{pid}" width="8" height="8" patternUnits="userSpaceOnUse">'
            f'<path d="{linien}" stroke="{farbe}" stroke-width="1"/></pattern>')


def _html_zeilen(h, font):
    """Freitext (Qt-Rich-Text) -> [(zeile, px, fett)]."""
    if not h:
        return [], 0, False
    px_std, fett_std = _schrift(font)
    m = re.search(r"<body style=\"([^\"]*)\"", h)
    if m:
        g = re.search(r"font-size:([\d.]+)pt", m.group(1))
        if g:
            px_std = _f(g.group(1)) * PT_PX
        w = re.search(r"font-weight:(\d+)", m.group(1))
        if w:
            fett_std = int(w.group(1)) >= 600
    zeilen = []
    for p in re.findall(r"(?s)<p[^>]*>(.*?)</p>", h):
        px = px_std
        g = re.search(r"font-size:([\d.]+)pt", p)
        if g:
            px = _f(g.group(1)) * PT_PX
        fett = fett_std or bool(re.search(r"font-weight:(6|7|8|9)00", p))
        for teil in re.split(r"<br ?/?>", p):
            text = html.unescape(re.sub(r"<[^>]+>", "", teil))
            zeilen.append((text, px, fett))
    while zeilen and not zeilen[-1][0].strip():
        zeilen.pop()
    if not any(z[0].strip() for z in zeilen):
        return [], 0, False
    return zeilen, px_std, fett_std


# ---------------------------------------------------------------- Projekt

def lade(pfad):
    """Liefert {nr: Blatt} und eine Funktion svg(nr, klick='') -> str."""
    wurzel = ET.parse(pfad).getroot()
    defs = lade_definitionen(wurzel)
    vorlagen = {t.get("name"): t for t in wurzel.iterfind("titleblocktemplates/titleblocktemplate")}
    diagramme = sorted(wurzel.iter("diagram"), key=lambda d: int(d.get("order")))
    gesamt = len(diagramme)
    blaetter = {int(d.get("order")): Blatt(d, defs, gesamt) for d in diagramme}
    # Lage aller Elemente für Querverweise (Folio/Spalte)
    lage = {}
    for nr, b in blaetter.items():
        for e in b.d.iterfind("elements/element"):
            lage[e.get("uuid")] = (nr, b.ort(_f(e.get("x")), _f(e.get("y"))))

    def folio_von_uuid(e):
        ziel = e.find("links_uuids/link_uuid")
        if ziel is None or ziel.get("uuid") not in lage:
            return None
        nr, o = lage[ziel.get("uuid")]
        return f"{nr}/{o}"

    def svg(nr, klick=""):
        b = blaetter[nr]
        d = b.d
        datum = d.get("date", "")
        if re.fullmatch(r"\d{8}", datum):
            datum = f"{datum[6:8]}.{datum[4:6]}.{datum[0:4]}"
        felder = {"author": d.get("author", ""), "title": d.get("title", ""), "date": datum,
                  "folio": f"{nr}/{gesamt}", "filename": d.get("filename", ""),
                  "plant": d.get("plant", ""), "locmach": d.get("locmach", ""), "indexrev": d.get("indexrev", "")}
        vorlage = vorlagen.get(d.get("titleblocktemplate")) or (next(iter(vorlagen.values())) if vorlagen else None)
        return b.svg(folio_von_uuid, felder, vorlage, klick)

    return blaetter, svg
