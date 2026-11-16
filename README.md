# Veille emploi — Choisir le service public

Collecte automatique des offres publiées sur
[Choisir le service public](https://choisirleservicepublic.gouv.fr), puis tri et
récapitulatif envoyés chaque matin.

1. **6h30 — GitHub Actions** (`.github/workflows/collecte.yml`) lance
   `scripts/collect.py` : recherches par mots-clés, offres de la veille
  , Île-de-France, catégorie A, hors
   ministère de l'Intérieur. Résultat dans `data/latest.json`.
2. **8h30 — tâche Claude planifiée** : lit `data/latest.json`, classe les offres
   selon le profil recherché et envoie le récapitulatif en notification.

Réglages (mots-clés, exclusions, zone) : `config.yml`.
Collecte d'essai : modifier `run/demande.yml` (dates, `debug: true`) et pousser,
ou lancer le workflow à la main depuis l'onglet Actions.

Chaque matin, la tâche Claude enregistre son tri dans `decisions/AAAA-MM-JJ.json`
et fabrique le tableur du jour avec `scripts/excel.py jour AAAA-MM-JJ` ;
le vendredi, elle ajoute le tableur de la semaine (`scripts/excel.py semaine`),
avec une feuille « Mots-clés » pour vérifier leur réglage.
