#!/usr/bin/env python3
"""Vérifie le tri du jour avant de le déposer.

Usage : python scripts/valider_decisions.py AAAA-MM-JJ
        (compare decisions/AAAA-MM-JJ.json aux offres de data/AAAA-MM-JJ.json,
         ou de data/latest.json si le fichier du jour n'existe pas)

Contrôles : chaque offre retenue par la collecte a une décision, les étoiles valent 0, 2 ou 3,
chaque raison est une phrase non vide, aucune décision ne vise une offre inconnue.
Sortie : 0 si tout est bon, 1 sinon.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ETOILES = {0, 2, 3}


def charger(chemin: Path):
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"ERREUR : {chemin.relative_to(ROOT)} illisible ({e})")
        sys.exit(1)


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    date = sys.argv[1]
    data = ROOT / "data" / f"{date}.json"
    if not data.exists():
        data = ROOT / "data" / "latest.json"
    collecte = charger(data)
    dec = charger(ROOT / "decisions" / f"{date}.json")

    erreurs = []
    if dec.get("date") != date:
        erreurs.append(f"« date » vaut {dec.get('date')!r} au lieu de {date!r}")
    offres = {o["url"]: o for o in collecte.get("offres", [])}
    vues = set()
    for i, d in enumerate(dec.get("decisions", []), 1):
        url = d.get("url")
        if url not in offres:
            erreurs.append(f"décision {i} : offre absente de la collecte ({url})")
        if url in vues:
            erreurs.append(f"décision {i} : offre en double ({url})")
        vues.add(url)
        if d.get("etoiles") not in ETOILES:
            erreurs.append(f"décision {i} : « etoiles » doit valoir 0, 2 ou 3 (trouvé {d.get('etoiles')!r})")
        if not str(d.get("raison", "")).strip():
            erreurs.append(f"décision {i} : raison vide")
    manquantes = [u for u in offres if u not in vues]
    for u in manquantes:
        erreurs.append(f"offre sans décision : {offres[u].get('titre', u)}")

    compte = {e: sum(1 for d in dec.get("decisions", []) if d.get("etoiles") == e) for e in (3, 2, 0)}
    print(f"{date} : {len(offres)} offre(s), {len(vues)} décision(s) — "
          f"3 étoiles : {compte[3]}, 2 étoiles : {compte[2]}, écartées : {compte[0]}")
    for e in erreurs:
        print(f"  erreur : {e}")
    return 1 if erreurs else 0


if __name__ == "__main__":
    sys.exit(main())
