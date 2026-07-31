# Exploitation, nouveaux flux et sécurité

## Ajouter un flux

1. Enregistrer le propriétaire, la finalité, le format et la fréquence.
2. Ajouter un échantillon sans donnée sensible et définir le contrat de schéma.
3. Définir clés, types, champs obligatoires, unités et seuils qualité.
4. Créer l'ingestion idempotente vers Raw sans modifier la source.
5. Ajouter transformation, quarantaine et lineage Raw vers Trusted.
6. Ajouter tests unitaires et test d'intégration sur l'échantillon.
7. Faire valider les données Curated par le propriétaire métier.
8. Déployer, superviser volumes/durée/erreurs et documenter la reprise.

Pour météo : événements JSON horodatés, clé site/date. Pour drones : objet image
dans le stockage objet, métadonnées dans le catalogue, caractéristiques calculées
dans Curated.

## Administration

- Lancer le pipeline : `python main.py`
- Reprendre les phases déjà validées : `python main.py --resume`
- Lancer l'API : `python platform_api.py`
- Santé publique : `GET /api/health`
- Catalogue : `GET /api/catalog` avec `X-API-Key`
- Recherche : `GET /api/search?q=Blé` avec `X-API-Key`
- Prédiction : `POST /api/predict` avec un rôle chercheur/sélectionneur
- Exécution courante : `reports/pipeline_run.json`
- Historique : `reports/pipeline_history.jsonl`
- Checkpoint : `reports/pipeline_checkpoint.json`
- Audit API : `reports/api_audit.jsonl`
- Rapports par composant : `reports/*_report.json`

Toute phase en exception est marquée en erreur. L'opérateur corrige la cause puis
relance; les sorties sont régénérées de manière déterministe, sauf les événements
de démonstration météo/drone.

## Sécurité

Le prototype écoute uniquement sur `127.0.0.1`. Les routes utilisent :

| Rôle | Variable | Catalogue/recherche | Prédiction | Exploitation |
|---|---|---:|---:|---:|
| Chercheur | `SEMENCES_RESEARCHER_KEY` | Oui | Oui | Non |
| Sélectionneur | `SEMENCES_BREEDER_KEY` | Oui | Oui | Non |
| Opérateur | `SEMENCES_OPERATOR_KEY` | Oui | Non | Oui |

Les valeurs `*-demo` par défaut servent uniquement à la démonstration locale.
Chaque accès protégé est écrit dans `reports/api_audit.jsonl`.
En production : TLS, SSO, RBAC chercheur/sélectionneur/opérateur, secrets dans un
coffre, chiffrement au repos, journal d'audit, sauvegardes et politique de
rétention. Les données génétiques sont classées confidentielles.
