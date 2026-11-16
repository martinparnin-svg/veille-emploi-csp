# Veille emploi — Choisir le service public

Collecte automatique des offres publiées sur
[Choisir le service public](https://choisirleservicepublic.gouv.fr), puis tri et
récapitulatif envoyés chaque matin.

1. **6h30 — GitHub Actions** (`.github/workflows/collecte.yml`) lance
   `scripts/collect.py` : recherches par mots-clés, offres de la veille
   (le lundi : vendredi → dimanche), Île-de-France, catégorie A/A+, hors
   ministère de l'Intérieur. Résultat dans `data/latest.json`.
2. **8h30 — tâche Claude planifiée** : lit `data/latest.json`, classe les offres
   selon le profil recherché et envoie le récapitulatif en notification.

Réglages (mots-clés, exclusions, zone) : `config.yml`.
Collecte d'essai : modifier `run/demande.yml` (dates, `debug: true`) et pousser,
ou lancer le workflow à la main depuis l'onglet Actions.
