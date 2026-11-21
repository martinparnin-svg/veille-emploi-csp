# Veille emploi — Choisir le service public

Collecte automatique des offres publiées sur
[Choisir le service public](https://choisirleservicepublic.gouv.fr), puis tri et
récapitulatif envoyés chaque matin.

1. **Vers 5h — GitHub Actions** (`.github/workflows/collecte.yml`) lance
   `scripts/collect.py` : recherches par mots-clés, offres de la veille,
   Île-de-France, catégorie A, hors ministère de l'Intérieur. Résultat dans `data/latest.json`.
2. **8h10 — tâche de l'agent** (Hermes, ou une tâche Claude planifiée) : lit `data/latest.json`,
   classe les offres selon le profil recherché et envoie le récapitulatif.

Réglages (mots-clés, exclusions, zone) : `config.yml`.
Collecte d'essai : modifier `run/demande.yml` (dates, `debug: true`) et pousser,
ou lancer le workflow à la main depuis l'onglet Actions.

Chaque matin, l'agent enregistre son tri dans `decisions/AAAA-MM-JJ.json`
(vérifié par `scripts/valider_decisions.py AAAA-MM-JJ`)
et fabrique le tableur du jour avec `scripts/excel.py jour AAAA-MM-JJ` ;
le vendredi, il ajoute le tableur de la semaine (`scripts/excel.py semaine`),
avec une feuille « Mots-clés » pour vérifier leur réglage.

## Utilisation par Hermes

Cloner le dépôt dans `~/outils/veille-emploi-csp`, puis déclarer le dossier de compétences dans
`~/.hermes/config.yaml` du profil de la personne qui cherche un emploi :

```yaml
skills:
  external_dirs:
    - ~/outils/veille-emploi-csp/skills
```

La compétence `veille-emploi` décrit le tri quotidien. Le profil recherché est dans `profil.md`,
**jamais versionné** (modèle : `profil.exemple.md`). Les leçons retenues sont dans `AMELIORATIONS.md`.

**Confidentialité** : les décisions de tri (`decisions/`) révèlent les critères de recherche.
Garder ce dépôt **privé** (Settings › General › Danger Zone › Change visibility).
