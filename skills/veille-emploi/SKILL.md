---
name: veille-emploi
description: Trier chaque matin les offres d'emploi public collectées sur Choisir le service public (étoiles et raison d'une phrase), produire les tableurs Excel et envoyer le récapitulatif. À utiliser pour le tri quotidien, la synthèse du vendredi, ou pour régler les mots-clés et le profil recherché.
version: 1.0.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [emploi, fonction-publique, veille, tri, excel]
---

# Veille emploi — Choisir le service public

GitHub Actions collecte chaque matin (vers 5 h 45) les offres de la veille dans `data/latest.json`.
Toi, Hermes, tu tries ces offres selon le profil de la personne, puis tu lui envoies le récapitulatif.

## Confidentialité (à lire en premier)

- C'est une donnée **personnelle** : modèle Mistral uniquement (fournisseur `mistral-prive`,
  GLM-5.3-Flash), jamais Claude, sauf demande explicite de la personne concernée.
- Le profil détaillé vit dans `profil.md`, **ignoré par git** : ne le commite jamais, ne le copie
  dans aucun fichier versionné, ne le résume pas dans une raison de tri.
- Tâche à faire tourner dans le profil Hermes de la personne qui cherche un emploi.

## Repères rapides

| Élément | Où |
|---|---|
| Dépôt local | `~/outils/veille-emploi-csp` (faire `git pull` avant chaque travail) |
| Offres du jour | `data/latest.json` → `offres` (les `ecartees` sont déjà filtrées par le script) |
| Profil recherché | `profil.md` (local) ; modèle : `profil.exemple.md` |
| Filtres de collecte | `config.yml` (mots-clés, zone, catégories, exclusions) |
| Tri du jour | `decisions/AAAA-MM-JJ.json` |
| Vérification | `python3 scripts/valider_decisions.py AAAA-MM-JJ` |
| Tableurs | `python3 scripts/excel.py jour|semaine AAAA-MM-JJ -o tableurs/<nom>.xlsx` |
| Journal de collecte | `logs/derniere-collecte.log` |
| Leçons apprises | `AMELIORATIONS.md` |

## Procédure quotidienne (vers 8 h 10)

1. `cd ~/outils/veille-emploi-csp && git pull --rebase`. Lis `profil.md` et `AMELIORATIONS.md`.
   Si `profil.md` manque : construis-en un brouillon à partir de `profil.exemple.md`, de `config.yml`
   et des raisons de `decisions/*.json`, montre-le à la personne et attends sa validation.
2. Vérifie que `data/latest.json` → `collecte` porte la date du jour (heure de Paris).
   Sinon, lis `logs/derniere-collecte.log` ; si la collecte n'a pas tourné, relance-la en modifiant
   `run/demande.yml` (`since` et `until` = la veille, incrémente `essai`), commit, push, puis attends
   une dizaine de minutes et refais `git pull`.
3. Pour **chaque** offre de `offres` : 3, 2 ou 0 étoile et une raison d'une phrase (le poste, ce qui
   colle, la réserve). Appuie-toi sur le titre, l'employeur, le métier de référence, la nature de
   l'emploi et l'extrait. Les décisions passées dans `decisions/` montrent le niveau d'exigence.
4. Écris `decisions/AAAA-MM-JJ.json` (date de la collecte) :
   `{"date": "AAAA-MM-JJ", "decisions": [{"url": "…", "etoiles": 3, "raison": "…"}]}`.
5. `python3 scripts/valider_decisions.py AAAA-MM-JJ` doit répondre sans erreur.
6. `mkdir -p tableurs && python3 scripts/excel.py jour AAAA-MM-JJ -o "tableurs/Veille CSP AAAA-MM-JJ.xlsx"` ;
   le vendredi, ajoute `semaine` (« Veille CSP semaine AAAA-MM-JJ.xlsx »).
7. `git add decisions/AAAA-MM-JJ.json && git commit -m "Tri du AAAA-MM-JJ" && git push`.
8. Envoie le récapitulatif : d'abord les 3 étoiles, puis les 2 étoiles, chacune avec intitulé,
   employeur, lieu, date limite, lien et raison ; puis le nombre d'offres écartées. Joins le
   tableur si la messagerie le permet. Aucune offre retenue : un message d'une ligne suffit.

## Pièges connus

- Pas d'étoile 1 : le barème est 0, 2 ou 3 (le tableur colore 2 et 3).
- Les offres réservées aux fonctionnaires sont gardées et signalées si la personne est contractuelle.
- Le moteur du site trie par pertinence : ne conclus jamais « pas d'offre » sans avoir vérifié que la
  collecte du jour a bien tourné.
- Un CDD très court ou un niveau au-dessus de celui visé : 2 étoiles au plus, réserve dite.

## S'améliorer

- **Après chaque remarque de la personne** (« trop sévère sur… », « ignore… »), ajoute une ligne
  datée dans `AMELIORATIONS.md` (rubrique « Leçons ») et, si elle touche au profil, propose la
  modification de `profil.md`.
- **Mots-clés** : le tableur du vendredi a une feuille « Mots-clés ». Si un mot-clé ne ramène
  jamais d'offre retenue, ou si des offres pertinentes passent à travers, propose un réglage de
  `config.yml`.
- **Contenus** (`decisions/`, `run/demande.yml`, `AMELIORATIONS.md`) : commit direct sur `main`.
- **Tout le reste** (`config.yml`, ce fichier, scripts) : branche `hermes/<sujet>` et demande de
  fusion (`gh pr create`), ou lien de la branche envoyé à la personne, qui relit et fusionne.
- **Jamais** : `profil.md` dans git, modification de `.github/workflows/` ou des secrets.
