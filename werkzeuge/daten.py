"""Lädt alle Daten des Wikis (YAML + .qet) und prüft sie auf Widersprüche."""
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
import qet  # noqa: E402

STATUS = ("geprueft", "ungeprueft", "fehlt")
STATUS_TEXT = {"geprueft": "geprüft", "ungeprueft": "ungeprüft", "fehlt": "fehlt noch"}
ART_TEXT = {
    "energiezaehler": "Energiezähler (Smartmeter)",
    "zaehler": "Zähler (EVU)",
    "klemmenblock": "Klemmenblock",
    "klemmleiste": "Klemmleiste",
    "kabel": "Kabel",
    "sls-schalter": "SLS-Schalter",
    "ueberspannungsschutz": "Überspannungsschutz",
    "lasttrennschalter": "Lasttrennschalter",
    "sicherungstrenner": "Sicherungstrenner",
    "fehlerstromschutzschalter": "Fehlerstromschutzschalter (RCD)",
    "leitungsschutzschalter": "Leitungsschutzschalter",
    "fi-ls-schalter": "FI/LS-Schalter (RCBO)",
    "sonstiges": "Sonstiges",
}
# Arten, bei denen Hersteller/Typ erwartet wird.
GERAETE_ARTEN = set(ART_TEXT) - {"kabel", "klemmleiste", "sonstiges"}


def _yaml(pfad):
    return yaml.safe_load(Path(pfad).read_text(encoding="utf-8")) or {}


def dateiname(bmk):
    return bmk.lstrip("-")


def werte_liste(element):
    """Werte als Liste (name, wert, status, notiz); Kurzform 'name: wert' erlaubt."""
    aus = []
    for name, v in (element.get("werte") or {}).items():
        if isinstance(v, dict):
            aus.append((name, v.get("wert"), v.get("status") or element.get("status"), v.get("notiz")))
        else:
            aus.append((name, v, element.get("status"), None))
    return aus


def lade(wurzel):
    wurzel = Path(wurzel)
    wiki = _yaml(wurzel / "wiki.yaml")
    d = {"wurzel": wurzel, "wiki": wiki, "anlagen": {}, "typen": {}, "offene": []}
    for tdatei in sorted((wurzel / "typen").glob("*/typ.yaml")):
        t = _yaml(tdatei)
        t["_datei"] = tdatei.relative_to(wurzel).as_posix()
        t["_ordner"] = tdatei.parent.relative_to(wurzel).as_posix()
        d["typen"][t.get("id") or tdatei.parent.name] = t
    for aid in wiki.get("anlagen", []):
        ordner = wurzel / "anlagen" / aid
        cfg = _yaml(ordner / "anlage.yaml")
        cfg["_ordner"] = ordner.relative_to(wurzel).as_posix()
        elemente = {}
        for edatei in sorted((ordner / "elemente").glob("*.yaml")):
            e = _yaml(edatei)
            e["_datei"] = edatei.relative_to(wurzel).as_posix()
            e["_name"] = edatei.stem
            elemente[e.get("bmk")] = e
        plan = qet.lade(ordner / cfg["plan"]["qet"]) if cfg.get("plan", {}).get("qet") else []
        d["anlagen"][aid] = {"id": aid, "cfg": cfg, "elemente": elemente, "plan": plan}
    op = wurzel / "offene-punkte.yaml"
    if op.exists():
        d["offene"] = yaml.safe_load(op.read_text(encoding="utf-8")) or []
    return d


def plan_bmks(anlage):
    """BMK -> {'blatt', 'info'} aus Elementen und BMK-Texten (Kabel, Klemmleisten) der Plan-Blätter."""
    ansichten = {b["nr"] for b in anlage["cfg"].get("blaetter", []) if b.get("ansicht")}
    gefunden = {}
    for b in anlage["plan"]:
        if b["nr"] in ansichten:
            continue
        for e in b["elemente"]:
            if e["bmk"]:
                gefunden.setdefault(e["bmk"], {"blatt": b["nr"], "info": e["info"]})
        for t in b["texte"]:
            bmk = qet.bmk_normal(t["zeilen"][0])
            if bmk:
                gefunden.setdefault(bmk, {"blatt": b["nr"], "info": {"text": t["zeilen"]}})
    return gefunden


def pruefe(d):
    """Liefert Meldungen (stufe, text, bezug). stufe: 'fehler' oder 'hinweis'."""
    m = []
    w = d["wurzel"]
    for tid, t in d["typen"].items():
        if t.get("status") not in STATUS:
            m.append(("fehler", f"Ungültiger Status '{t.get('status')}'", t["_datei"]))
        for doc in t.get("dokumente") or []:
            if doc.get("datei") and not (w / t["_ordner"] / doc["datei"]).exists():
                m.append(("fehler", f"Dokument fehlt: {doc['datei']}", t["_datei"]))
    for aid, a in d["anlagen"].items():
        for b in a["plan"]:
            if b["spalten"] != (17, 60):
                m.append(("hinweis", f"Blatt {b['nr']} hat ein anderes Format; Klickflächen prüfen", a["cfg"]["_ordner"]))
        im_plan = plan_bmks(a)
        for bmk, p in im_plan.items():
            if bmk not in a["elemente"]:
                m.append(("fehler", f"{bmk} steht im Plan (Blatt {p['blatt']}), hat aber keine YAML-Datei", a["cfg"]["_ordner"]))
        for bmk, e in a["elemente"].items():
            ort = e["_datei"]
            if not bmk or not qet.BMK_MUSTER.match(bmk) or not bmk.startswith("-"):
                m.append(("fehler", f"Ungültiges BMK '{bmk}'", ort))
                continue
            if e["_name"] != dateiname(bmk):
                m.append(("fehler", f"Dateiname passt nicht zum BMK {bmk}", ort))
            if e.get("status") not in STATUS:
                m.append(("fehler", f"Ungültiger Status '{e.get('status')}'", ort))
            for name, _, st, _ in werte_liste(e):
                if st not in STATUS:
                    m.append(("fehler", f"Wert '{name}': ungültiger Status '{st}'", ort))
            if e.get("typ") and e["typ"] not in d["typen"]:
                m.append(("fehler", f"Typ '{e['typ']}' gibt es nicht unter typen/", ort))
            for doc in e.get("dokumente") or []:
                pfad = w / "dokumente" / aid / e["_name"] / (doc.get("datei") or "")
                if doc.get("datei") and not pfad.exists():
                    m.append(("fehler", f"Dokument fehlt: {pfad.relative_to(w).as_posix()}", ort))
            for ziel in e.get("unterplaene") or []:
                z_anlage, _, z_blatt = str(ziel).partition("/")
                za = d["anlagen"].get(z_anlage)
                if not za or (z_blatt and int(z_blatt) not in {b["nr"] for b in za["cfg"].get("blaetter", [])}):
                    m.append(("fehler", f"Unterplan '{ziel}' existiert nicht", ort))
            if bmk not in im_plan:
                m.append(("hinweis", f"{bmk} ist in den Daten, aber nicht im Plan", ort))
                continue
            # Abgleich: steht ein Wert aus dem Plan nicht (mehr) in den Daten?
            info = im_plan[bmk]["info"]
            daten_werte = {str(v) for _, v, _, _ in werte_liste(e)}
            for feld in ("comment", "description"):
                if feld in info and info[feld] not in daten_werte:
                    m.append(("hinweis", f"Plan sagt '{info[feld]}' ({feld}), die Daten nicht", ort))
            if e.get("blatt") != im_plan[bmk]["blatt"]:
                m.append(("hinweis", f"Blatt in den Daten ({e.get('blatt')}) ≠ Blatt im Plan ({im_plan[bmk]['blatt']})", ort))
    return m
