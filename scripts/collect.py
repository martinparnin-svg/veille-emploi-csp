#!/usr/bin/env python3
"""Collecte des offres Choisir le service public (CSP).

Lance chaque mot-clé de config.yml sur le moteur de recherche CSP, garde les
offres publiées dans la fenêtre demandée, en Île-de-France, hors ministère de
l'Intérieur, puis ouvre chaque offre retenue pour en extraire la catégorie,
la nature de l'emploi, le télétravail et un extrait de description.

Résultat : data/AAAA-MM-JJ.json (date de collecte) et data/latest.json.

Usage :
  python scripts/collect.py                       # veille = hier (lundi : ven.→dim.)
  python scripts/collect.py --since 2026-11-13 --until 2026-11-16
  python scripts/collect.py --debug               # sauvegarde le HTML brut dans debug/
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import time
import unicodedata
from pathlib import Path
from urllib.parse import quote, urljoin

import requests
import yaml
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
PARIS = dt.timezone(dt.timedelta(hours=1))  # suffisant pour choisir la date du jour

MOIS = {
    "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11,
    "decembre": 12,
}
RE_DATE = re.compile(r"(\d{1,2})\s+([a-zéèêûôîâäëïöüç]+)\s+(\d{4})", re.I)
RE_DEP = re.compile(r"\((\d{2}|2A|2B|97\d)\)")

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36 veille-emploi-csp")


def norm(s: str) -> str:
    """Minuscules, sans accents, espaces simples, apostrophes droites."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("’", "'").replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip().lower()


def parse_date_fr(text: str) -> dt.date | None:
    m = RE_DATE.search(norm(text))
    if not m:
        return None
    jour, mois, annee = m.groups()
    mois_n = MOIS.get(mois)
    if not mois_n:
        return None
    try:
        return dt.date(int(annee), mois_n, int(jour))
    except ValueError:
        return None


class Client:
    def __init__(self, pause: float, debug_dir: Path | None):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA, "Accept-Language": "fr-FR,fr;q=0.9"})
        self.pause = pause
        self.debug_dir = debug_dir
        self.n = 0

    def get(self, url: str, tag: str = "") -> str | None:
        for essai in range(3):
            try:
                r = self.s.get(url, timeout=30)
                if r.status_code == 404:
                    return None
                r.raise_for_status()
                time.sleep(self.pause)
                self.n += 1
                if self.debug_dir and tag:
                    self.debug_dir.mkdir(parents=True, exist_ok=True)
                    (self.debug_dir / f"{tag}.html").write_text(r.text, encoding="utf-8")
                return r.text
            except requests.RequestException as e:
                print(f"  ! {url} : {e} (essai {essai + 1})", file=sys.stderr)
                time.sleep(3 * (essai + 1))
        return None


# ---------------------------------------------------------------- liste

def is_offer_href(href: str) -> bool:
    return bool(href) and "/offre-emploi/" in href and "/nos-offres/" not in href


def card_for(a) -> object:
    """Remonte depuis le lien jusqu'au bloc qui contient la fiche de l'offre."""
    node = a
    for _ in range(8):
        if node.parent is None:
            break
        node = node.parent
        t = node.get_text(" ", strip=True)
        if "En ligne depuis" in t or "Localisation" in t:
            # le bloc ne doit contenir qu'une seule offre
            liens = {x.get("href") for x in node.find_all("a", href=True) if is_offer_href(x["href"])}
            if len(liens) <= 1:
                return node
            break
    return a.parent


def field(text: str, label: str) -> str:
    m = re.search(label + r"\s*:\s*(.+?)(?=\s+(?:Localisation|Fonction publique|Employeur|En ligne depuis|Catégorie|Domaine)\b|$)",
                  text, re.I)
    return m.group(1).strip(" •-") if m else ""


def parse_listing(html: str, base: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    out, vus = [], set()
    for a in soup.find_all("a", href=True):
        href = urljoin(base, a["href"])
        if not is_offer_href(href) or href in vus:
            continue
        titre = a.get_text(" ", strip=True)
        if not titre:
            continue
        vus.add(href)
        card = card_for(a)
        t = card.get_text(" ", strip=True)
        m = re.search(r"En ligne depuis le\s+(.{6,25}?\d{4})", t)
        out.append({
            "titre": titre,
            "url": href,
            "localisation": field(t, "Localisation"),
            "fonction_publique": field(t, "Fonction publique"),
            "employeur": field(t, "Employeur"),
            "date_publication": (parse_date_fr(m.group(1)).isoformat()
                                 if m and parse_date_fr(m.group(1)) else None),
        })
    return out


def total_results(html: str) -> int | None:
    m = re.search(r"([\d\s \xa0]+)\s+offres? d'emploi trouv", html)
    return int(re.sub(r"\D", "", m.group(1))) if m else None


def dump_filters(html: str, path: Path) -> None:
    """Debug : liste les liens et champs de filtres pour régler filtres_site."""
    soup = BeautifulSoup(html, "html.parser")
    lignes = []
    for a in soup.find_all("a", href=True):
        h = a["href"]
        if "/filtres/" in h or "feed" in h or "rss" in h.lower():
            lignes.append(f"A\t{a.get_text(' ', strip=True)[:60]}\t{h}")
    for inp in soup.find_all(["input", "option", "select"]):
        lab = inp.get_text(" ", strip=True)[:60]
        if inp.name == "input" and inp.get("id"):
            l = soup.find("label", attrs={"for": inp["id"]})
            if l:
                lab = l.get_text(" ", strip=True)[:60]
        lignes.append(f"{inp.name.upper()}\t{inp.get('name')}\t{inp.get('value')}\t{lab}\t{dict((k, v) for k, v in inp.attrs.items() if k.startswith('data-'))}")
    path.write_text("\n".join(lignes), encoding="utf-8")


# ---------------------------------------------------------------- fiche

LABELS = [
    "Organisme de rattachement", "Employeur", "Versant", "Fonction publique",
    "Catégorie", "Nature de l'emploi", "Nature de l’emploi", "Expérience souhaitée",
    "Rémunération", "Domaine", "Métier", "Télétravail", "Management",
    "Date de vacance de l'emploi", "Date de vacance de l’emploi",
    "Localisation du poste", "Localisation", "Référence", "Date limite de candidature",
]


def parse_detail(html: str, extrait_max: int) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    for x in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        x.decompose()
    main = soup.find("main") or soup.body or soup
    lignes = [l.strip() for l in main.get_text("\n").split("\n") if l.strip()]
    texte = "\n".join(lignes)
    info = {}
    for i, l in enumerate(lignes):
        for lab in LABELS:
            if norm(l).startswith(norm(lab)):
                reste = l[len(lab):].strip(" : ")
                if not reste and i + 1 < len(lignes):
                    reste = lignes[i + 1]
                cle = norm(lab).replace("’", "'")
                info.setdefault(cle, reste[:200])
    # extrait : à partir de la description du poste si on la trouve
    debut = 0
    for marq in ("Description du poste", "Vos missions", "Missions", "Descriptif"):
        k = texte.find(marq)
        if k >= 0:
            debut = k
            break
    extrait = re.sub(r"\s+", " ", texte[debut:])[:extrait_max]
    return {"champs": info, "extrait": extrait, "texte_norm": norm(texte)}


# ---------------------------------------------------------------- filtres

def in_idf(loc: str, cfg: dict) -> bool | None:
    if not loc:
        return None
    if any(norm(r) in norm(loc) for r in cfg["libelles_region"]):
        return True
    deps = RE_DEP.findall(loc)
    if deps:
        return any(d in cfg["departements"] for d in deps)
    villes = ["paris", "versailles", "nanterre", "creteil", "bobigny", "evry",
              "cergy", "melun", "boulogne", "saint-denis", "montreuil", "vincennes",
              "issy", "la defense", "ivry", "arcueil", "malakoff", "courbevoie"]
    return True if any(v in norm(loc) for v in villes) else False


def excluded(text: str, motifs: list[str]) -> str | None:
    t = norm(text)
    for m in motifs:
        mm = norm(m)
        if len(mm) <= 5:  # sigles : mot entier
            if re.search(rf"\b{re.escape(mm)}\b", t):
                return m
        elif mm in t:
            return m
    return None


def category_ok(cat: str, cfg: dict) -> bool | None:
    if not cat:
        return None
    c = norm(cat)
    if "a+" in c.replace(" ", ""):
        return True
    if re.search(r"\b(categorie\s*)?a\b", c) and not re.search(r"\b[bc]\b", c):
        return True
    return False


# ---------------------------------------------------------------- principal

def default_window(today: dt.date) -> tuple[dt.date, dt.date]:
    hier = today - dt.timedelta(days=1)
    if today.weekday() == 0:  # lundi : vendredi, samedi, dimanche
        return today - dt.timedelta(days=3), hier
    return hier, hier


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since")
    ap.add_argument("--until")
    ap.add_argument("--debug", action="store_true")
    ap.add_argument("--max-keywords", type=int, default=0)
    args = ap.parse_args()

    cfg = yaml.safe_load((ROOT / "config.yml").read_text(encoding="utf-8"))
    today = dt.datetime.now(PARIS).date()
    since, until = default_window(today)
    if args.since:
        since = dt.date.fromisoformat(args.since)
    if args.until:
        until = dt.date.fromisoformat(args.until)
    print(f"Fenêtre : {since} → {until}")

    debug_dir = ROOT / "debug" if args.debug else None
    cli = Client(cfg.get("pause", 1.0), debug_dir)
    site = cfg["site"].rstrip("/")
    filtres = cfg.get("filtres_site", "").strip("/")

    candidats: dict[str, dict] = {}
    stats = {"mots_cles": {}, "pages": 0, "anomalies": []}
    mots = cfg["mots_cles"][: args.max_keywords or None]

    for i_kw, kw in enumerate(mots):
        base = f"{site}/nos-offres/filtres/mot-cles/{quote(kw, safe='')}/"
        if filtres:
            base += filtres + "/"
        vus_kw, dans_fenetre = 0, 0
        for page in range(1, cfg.get("pages_max", 15) + 1):
            url = base if page == 1 else f"{base}page/{page}/"
            tag = f"liste-{i_kw}-p{page}" if (args.debug and page <= 2 and i_kw < 2) else ""
            html = cli.get(url, tag)
            stats["pages"] += 1
            if not html:
                break
            if args.debug and i_kw == 0 and page == 1:
                dump_filters(html, debug_dir / "filtres.tsv")
            offres = parse_listing(html, site)
            if page == 1:
                stats["mots_cles"][kw] = {"total_site": total_results(html)}
            if not offres:
                break
            vus_kw += len(offres)
            dates = [o["date_publication"] for o in offres if o["date_publication"]]
            for o in offres:
                d = o["date_publication"]
                if d is None or not (since.isoformat() <= d <= until.isoformat()):
                    continue
                dans_fenetre += 1
                o.setdefault("mots_cles", [])
                prev = candidats.setdefault(o["url"], o)
                prev.setdefault("mots_cles", [])
                if kw not in prev["mots_cles"]:
                    prev["mots_cles"].append(kw)
            # résultats triés du plus récent au plus ancien ? alors on s'arrête
            # dès que toute la page est antérieure à la fenêtre.
            if dates and dates == sorted(dates, reverse=True) and max(dates) < since.isoformat():
                break
        else:
            stats["anomalies"].append(f"pages_max atteint pour « {kw} »")
        stats["mots_cles"][kw].update({"offres_vues": vus_kw, "dans_fenetre": dans_fenetre})
        print(f"« {kw} » : {vus_kw} vues, {dans_fenetre} dans la fenêtre")

    # filtres sur la liste
    retenues, ecartees = [], []
    for o in candidats.values():
        motif = excluded(o["titre"], cfg["exclusions_intitule"])
        if motif:
            ecartees.append({**o, "motif": f"intitulé ({motif})"})
            continue
        motif = excluded(o["employeur"], cfg["exclusions_employeur"])
        if motif:
            ecartees.append({**o, "motif": f"Intérieur ({motif})"})
            continue
        if in_idf(o["localisation"], cfg) is False:
            ecartees.append({**o, "motif": "hors Île-de-France"})
            continue
        retenues.append(o)

    # fiches détaillées
    final = []
    for k, o in enumerate(retenues):
        html = cli.get(o["url"], f"fiche-{k}" if args.debug and k < 3 else "")
        if not html:
            o["fiche"] = "indisponible"
            final.append(o)
            continue
        d = parse_detail(html, cfg.get("extrait_max", 1500))
        ch = d["champs"]
        o["categorie"] = ch.get("categorie", "")
        o["nature_emploi"] = ch.get("nature de l'emploi", "")
        o["teletravail"] = ch.get("teletravail", "")
        o["management"] = ch.get("management", "")
        o["rattachement"] = ch.get("organisme de rattachement", "")
        o["date_limite"] = ch.get("date limite de candidature", "")
        o["reference"] = ch.get("reference", "")
        o["extrait"] = d["extrait"]
        motif = excluded(" ".join([o["rattachement"], o["employeur"]]), cfg["exclusions_employeur"])
        if motif:
            ecartees.append({**o, "motif": f"Intérieur ({motif})"})
            continue
        if cfg.get("exclure_reserve_fonctionnaires") and re.search(
                r"reserve aux fonctionnaires|reserve aux titulaires|uniquement aux fonctionnaires",
                norm(o["nature_emploi"])):
            ecartees.append({**o, "motif": "réservé aux fonctionnaires"})
            continue
        if category_ok(o["categorie"], cfg) is False:
            ecartees.append({**o, "motif": f"catégorie {o['categorie']}"})
            continue
        if in_idf(ch.get("localisation du poste", "") or o["localisation"], cfg) is False:
            ecartees.append({**o, "motif": "hors Île-de-France"})
            continue
        final.append(o)

    sortie = {
        "collecte": dt.datetime.now(PARIS).isoformat(timespec="minutes"),
        "fenetre": {"du": since.isoformat(), "au": until.isoformat()},
        "nb_offres": len(final),
        "offres": final,
        "ecartees": [{k: v for k, v in e.items() if k in ("titre", "employeur", "localisation", "url", "motif")} for e in ecartees],
        "stats": {**stats, "requetes": cli.n},
    }
    data = ROOT / "data"
    data.mkdir(exist_ok=True)
    txt = json.dumps(sortie, ensure_ascii=False, indent=1)
    (data / f"{today.isoformat()}.json").write_text(txt, encoding="utf-8")
    (data / "latest.json").write_text(txt, encoding="utf-8")
    print(f"{len(final)} offres retenues, {len(ecartees)} écartées, {cli.n} requêtes.")
    if not candidats and stats["pages"]:
        print("ATTENTION : aucune offre lue — la structure du site a peut-être changé.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
