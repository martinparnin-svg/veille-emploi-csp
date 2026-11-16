#!/usr/bin/env python3
"""Tableurs de la veille emploi CSP.

Quotidien : toutes les annonces de la collecte du jour (data/AAAA-MM-JJ.json),
avec la décision du tri (decisions/AAAA-MM-JJ.json, écrit par la tâche Claude).
Hebdomadaire : les 7 derniers jours de collecte, plus une synthèse par jour et
par mot-clé pour vérifier le réglage des mots-clés.

Usage :
  python scripts/excel.py jour AAAA-MM-JJ -o "Veille CSP AAAA-MM-JJ.xlsx"
  python scripts/excel.py semaine AAAA-MM-JJ -o "Veille CSP semaine AAAA-MM-JJ.xlsx"

Format de decisions/AAAA-MM-JJ.json :
  {"date": "AAAA-MM-JJ",
   "decisions": [{"url": "...", "etoiles": 0|2|3, "raison": "une phrase"}]}
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parent.parent
GENERIQUES = ("communes", "conseils departementaux", "conseils regionaux",
              "centres communaux", "etablissements publics de cooperation",
              "mairie de paris", "departements")

ENTETE = Font(bold=True, color="FFFFFF")
FOND_ENTETE = PatternFill("solid", fgColor="1F3864")
FOND_3 = PatternFill("solid", fgColor="C6EFCE")
FOND_2 = PatternFill("solid", fgColor="FFF2CC")
LIEN = Font(color="0563C1", underline="single")


def sans_accents(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def administration(o: dict) -> str:
    emp = (o.get("employeur") or "").strip()
    if emp and not sans_accents(emp).startswith(GENERIQUES):
        return emp
    # employeur générique (« Communes »…) : la collectivité figure en fin d'intitulé
    m = re.search(r"\s[-–]\s([^-–]+)$", o.get("titre", ""))
    return f"{emp} — {m.group(1).strip()}" if m and emp else (m.group(1).strip() if m else emp)


def categorie(o: dict) -> str:
    c = o.get("categorie") or ""
    m = re.search(r"Cat[ée]gorie\s*(A\+|[ABC])", c)
    return m.group(1) if m else (c or "non précisée")


FONCTIONS = [
    (r"adjoint\w* (au |a la |du )?chef\w* (du |de )?bureau", "Adjoint(e) au chef de bureau"),
    (r"chef\w* (du |de )?bureau", "Chef(fe) de bureau"),
    (r"charge\w* de mission", "Chargé(e) de mission"),
    (r"chef\w* de mission", "Chef(fe) de mission"),
    (r"adjoint\w* .*(chef|responsable|direct)|(chef|responsable)\w* .*adjoint", "Adjoint(e) à un responsable"),
    (r"(chef\w*|charge\w*|directeur|directrice) de projets?", "Chef(fe) / chargé(e) de projet"),
    (r"chef\w* (de |du |d.)?(la )?(service|pole|departement|division|unite|cellule|section)", "Chef(fe) de service ou de pôle"),
    (r"(sous-)?direct(eur|rice)", "Direction"),
    (r"charge\w* d.etudes|analyste", "Chargé(e) d'études"),
    (r"juriste|charge\w* d.affaires juridiques", "Juriste"),
    (r"conseill(er|ere)", "Conseiller(e)"),
    (r"redact(eur|rice)", "Rédacteur(rice)"),
    (r"coordo?n?n?at(eur|rice)|coordinat", "Coordinateur(rice)"),
    (r"responsable", "Responsable"),
    (r"referent", "Référent(e)"),
    (r"gestionnaire", "Gestionnaire"),
    (r"inspect(eur|rice)", "Inspecteur(rice)"),
    (r"ingenieu?r", "Ingénieur(e)"),
    (r"educat|travailleu|social|psycholog|medecin|infirmi|enseignant|puericult|petite enfance", "Éducatif, social ou santé"),
    (r"assistant", "Assistant(e)"),
    (r"expert", "Expert(e)"),
    (r"collaborat(eur|rice) de cabinet|cabinet", "Cabinet"),
    (r"^charge|charge\w* d", "Chargé(e) de dossiers"),
    (r"postdoc|doctorant|chercheu", "Recherche"),
]


def fonction(o: dict) -> str:
    """Fonction déduite de l'intitulé, sinon le métier de référence de CSP."""
    t = sans_accents(o.get("titre", ""))
    t = re.sub(r"[.(·]\s*(e|fe|ne|rice|ice|trice|euse|ere)\)?(?=\W|$)", "", t)
    for motif, libelle in FONCTIONS:
        if re.search(motif, t):
            return libelle
    return o.get("metier_reference") or "Autre"


def domaine(o: dict) -> str:
    return o.get("domaine") or "non précisé"


def type_poste(o: dict) -> str:
    n = sans_accents(o.get("nature_emploi") or "")
    if "uniquement aux contractuels" in n:
        return "Contractuels uniquement"
    if "titulaires et aux contractuels" in n:
        return "Titulaires et contractuels"
    if "fonctionnaires" in n or "titulaires" in n:
        return "Réservé aux fonctionnaires"
    return o.get("nature_emploi") or "non précisé"


def charger(date: str) -> tuple[dict | None, dict]:
    f = ROOT / "data" / f"{date}.json"
    data = json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
    fd = ROOT / "decisions" / f"{date}.json"
    dec = {}
    if fd.exists():
        for d in json.loads(fd.read_text(encoding="utf-8")).get("decisions", []):
            dec[d["url"]] = d
    return data, dec


def lignes(date: str) -> list[dict]:
    data, dec = charger(date)
    if not data:
        return []
    out = []
    for o in data.get("offres", []) + data.get("ecartees", []):
        d = dec.get(o["url"], {})
        etoiles = int(d.get("etoiles") or 0)
        if o.get("motif"):
            raison = f"Écarté automatiquement : {o['motif']}"
        else:
            raison = d.get("raison") or ("Non retenu au tri" if dec else "Tri non effectué")
        out.append({
            "Récap du": date,
            "Publiée le": o.get("date_publication") or "",
            "Ministère / administration": administration(o),
            "Catégorie": categorie(o),
            "Intitulé du poste": o.get("titre", ""),
            "Fonction": fonction(o),
            "Domaine": domaine(o),
            "Ouvert à": type_poste(o),
            "Lien": o["url"],
            "Retenu": "Oui" if etoiles >= 2 else "Non",
            "Étoiles": "★" * etoiles,
            "Raison": raison,
            "_etoiles": etoiles,
            "_mots_recherche": o.get("mots_cles_recherche") or o.get("mots_cles") or [],
            "_mots_texte": o.get("mots_cles_texte") or [],
        })
    out.sort(key=lambda r: (-r["_etoiles"], r["Retenu"] != "Oui", r["Ministère / administration"]))
    return out


def feuille(ws, rows: list[dict], colonnes: list[str], largeurs: dict[str, int]) -> None:
    ws.append(colonnes)
    for c in ws[1]:
        c.font, c.fill = ENTETE, FOND_ENTETE
        c.alignment = Alignment(vertical="center", wrap_text=True)
    for r in rows:
        ws.append([r.get(c, "") for c in colonnes])
        i = ws.max_row
        if "Lien" in colonnes:
            cell = ws.cell(i, colonnes.index("Lien") + 1)
            cell.hyperlink, cell.value, cell.font = r["Lien"], "Voir l'annonce", LIEN
        fond = FOND_3 if r.get("_etoiles") == 3 else FOND_2 if r.get("_etoiles") == 2 else None
        if fond:
            for c in ws[i]:
                c.fill = fond
        for c in ws[i]:
            c.alignment = Alignment(vertical="top", wrap_text=True)
    for k, col in enumerate(colonnes, 1):
        ws.column_dimensions[get_column_letter(k)].width = largeurs.get(col, 14)
    ws.freeze_panes = "A2"
    if ws.max_row > 1:
        ws.auto_filter.ref = ws.dimensions


COLS = ["Publiée le", "Ministère / administration", "Catégorie", "Intitulé du poste",
        "Fonction", "Domaine", "Ouvert à", "Lien", "Retenu", "Étoiles", "Raison"]
LARG = {"Récap du": 11, "Publiée le": 11, "Ministère / administration": 34, "Catégorie": 10,
        "Intitulé du poste": 48, "Fonction": 24, "Domaine": 28, "Ouvert à": 22, "Lien": 15, "Retenu": 8,
        "Étoiles": 8, "Raison": 60}


def jour(date: str, sortie: Path) -> int:
    rows = lignes(date)
    wb = Workbook()
    ws = wb.active
    ws.title = f"Annonces {date}"
    feuille(ws, rows, COLS, LARG)
    wb.save(sortie)
    print(f"{sortie} : {len(rows)} annonces, {sum(r['Retenu'] == 'Oui' for r in rows)} retenues")
    return 0


def semaine(date: str, sortie: Path) -> int:
    fin = dt.date.fromisoformat(date)
    jours = [(fin - dt.timedelta(days=k)).isoformat() for k in range(6, -1, -1)]
    toutes, synth = [], []
    for j in jours:
        data, dec = charger(j)
        rows = lignes(j)
        toutes += rows
        synth.append({
            "Récap du": j,
            "Annonces trouvées": len(rows) if data else "pas de collecte",
            "Écartées automatiquement": sum(r["Raison"].startswith("Écarté") for r in rows),
            "Examinées au tri": sum(not r["Raison"].startswith("Écarté") for r in rows),
            "Retenues ★★★": sum(r["_etoiles"] == 3 for r in rows),
            "Retenues ★★": sum(r["_etoiles"] == 2 for r in rows),
            "Tri effectué": "oui" if dec else "non",
        })
    wb = Workbook()
    ws = wb.active
    ws.title = "Synthèse"
    cs = list(synth[0].keys())
    feuille(ws, synth, cs, {c: 16 for c in cs})
    ws.append([])
    ws.append(["Total", sum(s["Annonces trouvées"] for s in synth if isinstance(s["Annonces trouvées"], int)),
               sum(s["Écartées automatiquement"] for s in synth), sum(s["Examinées au tri"] for s in synth),
               sum(s["Retenues ★★★"] for s in synth), sum(s["Retenues ★★"] for s in synth)])
    for c in ws[ws.max_row]:
        c.font = Font(bold=True)

    ws2 = wb.create_sheet("Annonces de la semaine")
    feuille(ws2, toutes, ["Récap du"] + COLS, LARG)

    # Par mot-clé : la recherche le trouve-t-elle, figure-t-il dans le texte,
    # mène-t-il à des postes retenus ?
    import yaml
    mots = yaml.safe_load((ROOT / "config.yml").read_text(encoding="utf-8"))["mots_cles"]
    stats = []
    for m in mots:
        par_recherche = [r for r in toutes if m in r["_mots_recherche"]]
        dans_texte = [r for r in toutes if m in r["_mots_texte"]]
        stats.append({
            "Mot-clé": m,
            "Annonces trouvées par la recherche": len(par_recherche),
            "Mot-clé présent dans la description": len(dans_texte),
            "Retenues (★★ ou ★★★)": sum(r["Retenu"] == "Oui" for r in dans_texte),
            "Utilité": ("à revoir : aucune annonce" if not par_recherche else
                        "efficace" if any(r["Retenu"] == "Oui" for r in dans_texte) else
                        "bruit : aucune retenue cette semaine"),
        })
    ws3 = wb.create_sheet("Mots-clés")
    cs3 = list(stats[0].keys())
    feuille(ws3, stats, cs3, {c: 24 for c in cs3} | {"Utilité": 36})
    wb.save(sortie)
    print(f"{sortie} : {len(toutes)} annonces sur {jours[0]} → {jours[-1]}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["jour", "semaine"])
    ap.add_argument("date")
    ap.add_argument("-o", "--output", required=True)
    a = ap.parse_args()
    return (jour if a.mode == "jour" else semaine)(a.date, Path(a.output))


if __name__ == "__main__":
    raise SystemExit(main())
