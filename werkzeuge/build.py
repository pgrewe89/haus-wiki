"""Erzeugt die statische Website in site/.

Aufruf:  python3 werkzeuge/build.py
Benötigt: python3-yaml, python3-jinja2. Die Pläne zeichnet werkzeuge/render.py direkt aus der .qet.
"""
import html
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

sys.path.insert(0, str(Path(__file__).parent))
import daten  # noqa: E402
import qet  # noqa: E402
import render  # noqa: E402

WURZEL = Path(__file__).resolve().parent.parent
SITE = WURZEL / "site"
WERKZEUGE = Path(__file__).resolve().parent


# ---------------------------------------------------------------- Klickflächen

def _enthaltend(rechtecke, px, py, max_seite=130):
    passend = [r for r in rechtecke
               if r[0] <= px <= r[0] + r[2] and r[1] <= py <= r[1] + r[3] and max(r[2], r[3]) <= max_seite]
    return min(passend, key=lambda r: r[2] * r[3]) if passend else None


def klickflaechen(blatt, ansicht):
    """Liste von (bmk, rechteck_in_svg_koordinaten) für ein Blatt."""
    flaechen = []
    if not ansicht:
        schon = set()
        for e in blatt["elemente"]:
            if e["bmk"] and e["rect"]:
                flaechen.append((e["bmk"], qet.rechteck(*e["rect"])))
                schon.add(e["bmk"])
        for t in blatt["texte"]:
            bmk = qet.bmk_normal(t["zeilen"][0])
            if bmk and bmk not in schon:
                flaechen.append((bmk, qet.rechteck(*qet.text_rechteck(t))))
        return flaechen
    # Ansichtsblatt: Beschriftungen liegen in Rechtecken (Geräte in der Front,
    # Zeilen der BMK-Legende). Die Klickfläche ist das kleinste umgebende Rechteck.
    for t in blatt["texte"]:
        bmk = qet.bmk_normal(t["zeilen"][0])
        if not bmk:
            continue
        r = _enthaltend(blatt["rechtecke"], t["x"] + 8, t["y"] + 8)
        if r and r[0] < 40:
            # Legendenzeile: BMK-Zelle und Text-Zelle daneben zusammenfassen
            r = (r[0], r[1], 355 - r[0], r[3])
        elif not r:
            # Beschriftung über einem Gerät: das Gerät direkt darunter mit einbeziehen
            r = qet.text_rechteck(t)
            mitte = t["x"] + 10
            darunter = [g for g in blatt["rechtecke"]
                        if t["y"] <= g[1] <= t["y"] + 30 and g[0] <= mitte <= g[0] + g[2] and max(g[2], g[3]) <= 130]
            if darunter:
                g = min(darunter, key=lambda g: g[1])
                r = qet._vereinige((t["x"], t["y"] + 2, 20, 12), g)
        flaechen.append((bmk, qet.rechteck(*r)))
    return flaechen


# ---------------------------------------------------------------- SVG

def svg_mit_flaechen(svg, flaechen, elemente, link):
    teile = ['<g class="klick">']
    for bmk, (x, y, b, h) in flaechen:
        e = elemente.get(bmk)
        status = e.get("status", "fehlt") if e else "fehlt"
        titel = html.escape(f"{bmk} {e.get('bezeichnung') or ''}".strip() if e else f"{bmk} (keine Daten)")
        ziel = link(bmk) if e else "#"
        teile.append(
            f'<a href="{ziel}" class="hs st-{status}" data-bmk="{html.escape(bmk)}">'
            f'<title>{titel}</title><rect x="{x}" y="{y}" width="{b}" height="{h}" rx="2"/></a>')
    teile.append("</g>")
    return svg.replace("</svg>", "\n".join(teile) + "\n</svg>")


# ---------------------------------------------------------------- Markdown (klein)

def markdown(text):
    def inline(s):
        s = html.escape(s)
        s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
        return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)

    aus, liste = [], False
    for zeile in text.splitlines():
        z = zeile.rstrip()
        if z.startswith("- "):
            if not liste:
                aus.append("<ul>")
                liste = True
            aus.append(f"<li>{inline(z[2:])}</li>")
            continue
        if liste:
            aus.append("</ul>")
            liste = False
        if m := re.match(r"(#{1,3}) (.*)", z):
            n = len(m.group(1)) + 1
            aus.append(f"<h{n}>{inline(m.group(2))}</h{n}>")
        elif z:
            aus.append(f"<p>{inline(z)}</p>")
    if liste:
        aus.append("</ul>")
    return "\n".join(aus)


# ---------------------------------------------------------------- Prüfliste

def pruefpunkte(d):
    """Je Element: offene Punkte, ungeprüfte/fehlende Werte, fehlende Pflichtangaben."""
    zeilen = []
    for aid, a in d["anlagen"].items():
        for bmk, e in sorted(a["elemente"].items(), key=lambda kv: (kv[1].get("blatt") or 0, kv[0])):
            punkte = list(e.get("offene_punkte") or [])
            if not e.get("bezeichnung"):
                punkte.append("Bezeichnung fehlt.")
            if e.get("art") in daten.GERAETE_ARTEN and not e.get("typ"):
                punkte.append("Hersteller und Typ fehlen.")
            fehlt = [n for n, _, st, _ in daten.werte_liste(e) if st == "fehlt"]
            unge = [n for n, _, st, _ in daten.werte_liste(e) if st == "ungeprueft"]
            if e.get("status") == "geprueft" and not punkte and not fehlt and not unge:
                continue
            zeilen.append({"anlage": aid, "e": e, "punkte": punkte, "fehlt": fehlt, "ungeprueft": unge})
    return zeilen


# ---------------------------------------------------------------- Bauen

def kopiere_dateien(d):
    """Dokumente, Typ-Dateien und Plan-Quellen nach site/dateien/ (ohne YAML)."""
    ohne_yaml = shutil.ignore_patterns("*.yaml")
    if (WURZEL / "dokumente").exists():
        shutil.copytree(WURZEL / "dokumente", SITE / "dateien" / "dokumente", ignore=ohne_yaml)
    shutil.copytree(WURZEL / "typen", SITE / "dateien" / "typen", ignore=ohne_yaml)
    for a in d["anlagen"].values():
        for datei in a["cfg"].get("plan", {}).values():
            quelle = WURZEL / a["cfg"]["_ordner"] / datei
            ziel = SITE / "dateien" / a["cfg"]["_ordner"] / datei
            ziel.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(quelle, ziel)


def main():
    d = daten.lade(WURZEL)
    meldungen = daten.pruefe(d)
    for stufe, text, bezug in meldungen:
        print(f"{stufe.upper():8} {bezug}: {text}")

    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir()
    shutil.copytree(WERKZEUGE / "static", SITE / "static")
    kopiere_dateien(d)

    env = Environment(loader=FileSystemLoader(WERKZEUGE / "vorlagen"), autoescape=select_autoescape(["html"]))
    wiki = d["wiki"]
    repo = (wiki.get("repo_url") or "").rstrip("/")
    zweig = wiki.get("zweig", "main")
    env.globals.update(
        wiki=wiki, anlagen=d["anlagen"], STATUS_TEXT=daten.STATUS_TEXT, ART_TEXT=daten.ART_TEXT,
        werte_liste=daten.werte_liste, dateiname=daten.dateiname, typen=d["typen"],
        bearbeiten=lambda pfad: f"{repo}/edit/{zweig}/{pfad}" if repo else None,
        gebaut=datetime.now().strftime("%d.%m.%Y %H:%M"),
    )

    def schreibe(rel, vorlage, **kw):
        ziel = SITE / rel
        ziel.parent.mkdir(parents=True, exist_ok=True)
        tiefe = rel.count("/")
        ziel.write_text(env.get_template(vorlage).render(root="../" * tiefe, **kw), encoding="utf-8")

    anzahl = 0
    for aid, a in d["anlagen"].items():
        cfg = a["cfg"]
        _, zeichne = render.lade(WURZEL / cfg["_ordner"] / cfg["plan"]["qet"])
        plan = {b["nr"]: b for b in a["plan"]}
        vorkommen = {}  # bmk -> [(blatt, ansicht)]
        for b in cfg.get("blaetter", []):
            ansicht = bool(b.get("ansicht"))
            flaechen = klickflaechen(plan[b["nr"]], ansicht) if b["nr"] in plan else []
            for bmk, _ in flaechen:
                vorkommen.setdefault(bmk, [])
                if (b["nr"], ansicht) not in vorkommen[bmk]:
                    vorkommen[bmk].append((b["nr"], ansicht))
            svg = svg_mit_flaechen(zeichne(b["nr"]), flaechen, a["elemente"],
                                   lambda bmk: f"{daten.dateiname(bmk)}.html")
            schreibe(f"{aid}/blatt-{b['nr']}.html", "blatt.html", anlage=a, blatt=b, svg=svg,
                     fehlende=[bmk for bmk, _ in flaechen if bmk not in a["elemente"]])
        for bmk, e in a["elemente"].items():
            schreibe(f"{aid}/{e['_name']}.html", "element.html", anlage=a, e=e,
                     vorkommen=vorkommen.get(bmk, []), typ=d["typen"].get(e.get("typ")))
            anzahl += 1
        schreibe(f"{aid}/index.html", "anlage.html", anlage=a)

    for tid, t in d["typen"].items():
        nutzer = [(aid, e) for aid, a in d["anlagen"].items() for e in a["elemente"].values() if e.get("typ") == tid]
        schreibe(f"typen/{tid}.html", "typ.html", t=t, nutzer=nutzer)

    start = d["anlagen"][wiki["anlagen"][0]]
    schreibe("index.html", "start.html",
             ziel=f"{start['id']}/blatt-{start['cfg'].get('startblatt', 1)}.html")
    schreibe("elemente.html", "elemente.html")
    schreibe("pruefliste.html", "pruefliste.html", zeilen=pruefpunkte(d), offene=d["offene"], meldungen=meldungen)
    cl = WURZEL / "CHANGELOG.md"
    schreibe("aenderungen.html", "aenderungen.html",
             inhalt=markdown(cl.read_text(encoding="utf-8")) if cl.exists() else "")
    print(f"Fertig: {anzahl} Elemente, {len(d['typen'])} Typen -> {SITE}")


if __name__ == "__main__":
    main()
