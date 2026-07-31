# Roadmap de mise en œuvre

## Étape 1 - Prototype local (réalisée)

- Data Lake Raw/Transformed/Enriched/Exposed.
- Analyses Python, Spark local et Rscript.
- Catalogue, recherche, lineage, qualité et quarantaine.
- Modèles ML avec validation groupée/temporelle.
- Dashboard, carte, API RBAC, monitoring et checkpoint.

## Étape 2 - Préproduction

- Déployer stockage objet/HDFS, Kafka, NiFi, Spark et Hive.
- Importer les flows/configurations et remplacer les adaptateurs locaux.
- Connecter OpenSearch, Atlas et Superset.
- Brancher Prometheus/Grafana et un coffre de secrets.
- Charger météo, sol et conduite culturale sous contrats de données.
- Exécuter tests de charge, restauration et reprise après incident.

Critère de sortie : pipeline quotidien reproductible, aucune perte lors d'une
reprise, SSO/RBAC validé et seuils ML approuvés par un agronome.

## Étape 3 - Production

- Haute disponibilité, sauvegardes, réplication et plan de continuité.
- TLS complet, rotation des secrets et audit centralisé.
- SLA, astreinte, alertes fonctionnelles et suivi des coûts.
- Surveillance de dérive et réentraînement approuvé/versionné.
- Déploiement progressif puis validation par les métiers.

Critère de sortie : SLA respectés, tests de sécurité et de restauration réussis,
validation métier formelle et documentation opérateur signée.

## Paramètres externes

La date de remise ne figure pas dans le cahier des charges (`XX`). Elle doit être
fournie par le responsable et renseignée dans la documentation de remise; aucun
code ne peut déterminer cette information contractuelle.
