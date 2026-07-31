# Conformité au cahier des charges - Projet SEMENCE

Dernière validation : 31 juillet 2026

## Preuves de la validation finale

- Exécution complète non reprise : `reports/pipeline_run.json`, 17/17 phases,
  statut OK, 173,8 secondes, fin le 31 juillet 2026 à 11:57:16.
- La durée de référence est toujours lue dans `reports/pipeline_run.json`; les
  pages statiques ne figent plus de chronométrage susceptible de devenir obsolète.
- Checkpoint final : 17/17 phases réussies dans
  `reports/pipeline_checkpoint.json`; une phase en erreur n'y est jamais marquée
  comme terminée.
- Tests automatisés : 18/18 réussis avec
  `python -m unittest discover -s tests -v`.
- API HTTP : santé 200/UP, recherche chercheur 200 (25 résultats), prédiction
  opérateur refusée 403; événements écrits dans `reports/api_audit.jsonl`.
- HBase local : 50 000 reçues, 50 000 insérées, 0 rejetée, 0 collision;
  SQLite confirme 50 000 lignes et 50 000 clés distinctes.

## Résultats ML réels

Le protocole utilise 42 940 lignes de 2015-2017 pour l'entraînement et 12 306
lignes de 2018 pour le test temporel final. Le chevauchement des identifiants
d'essais entre entraînement et test est nul. Les variables `%MOIS`, `YD16QH`,
`SL_TRIAL`, `LK_STOCK_S1_DATA_ID` et `MAIN_NAME` sont exclues pour limiter la
fuite et la mémorisation.

| Mesure | Valeur test 2018 |
|---|---:|
| MAE | 13,2904 |
| RMSE | 16,9167 |
| R² | 0,4548 |
| Accuracy | 75,51 % |
| Précision | 65,87 % |
| Rappel | 91,06 % |
| F1-score | 76,45 % |

Ces valeurs ne satisfont pas les objectifs souhaités de plus de 80 %
d'accuracy, plus de 75 % de précision et plus de 80 % de F1. Elles ne sont pas
modifiées artificiellement. La qualité prédictive reste partielle, surtout par
espèce, tant que les variables météo, sol et conduite culturale manquent.

## Correction du référentiel espèces

Le code `S` est désormais traduit en `Soja`, conformément à
`CSV/REF_ESPECES_20190108.csv`. Les codes non confirmés `A`, `D` et `F` sont
exposés comme `INCONNU_CODE_A`, `INCONNU_CODE_D` et `INCONNU_CODE_F` plutôt que
de recevoir une signification inventée. La preuve est dans
`reports/species_mapping.json` et couverte par test.

## Verdict

Toutes les exigences sont couvertes au niveau **prototype fonctionnel local**.
Le pipeline complet comporte 17 phases, toutes validées. Les services lourds
(HDFS, NiFi, Sqoop, Kafka, HBase, Hive et Drill) conservent une implémentation
locale simulant leurs contrats; l'architecture de production correspondante est
documentée mais nécessite un cluster externe pour être déployée.

## Matrice finale

| Exigence | Statut prototype | Preuve |
|---|---|---|
| Inventaire et profiling | Oui | `reports/profiling.json` |
| Dictionnaire métier | Oui | `docs/DATA_MODEL.md` |
| Choix et justification d'architecture | Oui | `docs/ARCHITECTURE_CHOICES.md` |
| Schéma d'architecture | Oui | `deliverables/architecture_big_data.png` |
| Couches Raw/Transformed/Enriched/Exposed | Oui | `data/*` |
| Ingestion et transformation | Oui | Phases Sqoop, NiFi et ETL |
| Modèle relationnel et cardinalités | Oui | Diagramme ER dans `docs/DATA_MODEL.md` |
| Catalogue de métadonnées | Oui | `catalog/semences_catalog.db` |
| Lineage | Oui | Table `lineage` du catalogue |
| Moteur de recherche | Oui | SQLite FTS5 et `GET /api/search` |
| Base NoSQL | Oui, simulation locale | `hbase/semences_hbase.db` |
| Bus de données | Oui, simulation locale | Producteur/consommateur et rapports Kafka |
| Requêtes SQL Hive/Drill | Oui, simulation locale | 5 requêtes Hive et 6/6 Drill réussies |
| Spark | Oui | PySpark `local[*]` |
| Accès et analyses R | Oui | R 4.6.1, phase Rscript et `reports/r/` |
| Statistiques et ANOVA | Oui | Python, Spark et R |
| Reporting et dashboard | Oui | `reports/dashboard.html` |
| Graphes | Oui | `reports/images/` et `reports/r/` |
| Géolocalisation | Oui | `reports/carte_essais.html` |
| Prédiction culturale | Oui | `models/yield_yd15qh.joblib` |
| Validation et métriques ML | Oui | `reports/prediction_report.json` |
| API de prédiction | Oui | `POST /api/predict` |
| Administration et santé | Oui | `GET /api/health` |
| Monitoring et historique | Oui | `pipeline_run.json`, `pipeline_history.jsonl` |
| Checkpoint et reprise | Oui | `pipeline_checkpoint.json`, option `--resume` |
| Qualité et quarantaine | Oui | `data_quality_report.json`, `data/quarantine/` |
| Procédure nouveaux flux | Oui | `docs/OPERATIONS.md` |
| Météo et drones anticipés | Oui | Topic de démonstration et architecture cible |
| Sécurité locale | Oui | RBAC 3 rôles et `api_audit.jsonl` |
| Sécurité cible | Oui, spécifiée | TLS, SSO, RBAC, coffre et audit documentés |
| Diagramme exportable | Oui | `deliverables/architecture_big_data.png` |
| Présentation de soutenance | Oui | `deliverables/presentation_semences.pptx` |
| Roadmap | Oui | `docs/ROADMAP.md` |
| Tests automatisés | Oui | `tests/test_platform.py`, 18/18 réussis |
| Installation reproductible | Oui | `requirements.txt`, README et orchestrateur |

## Résultats vérifiés

- Pipeline : 17/17 phases réussies; durée dans `reports/pipeline_run.json`.
- Prédiction YD15QH : 42 940 lignes d'entraînement et 12 306 de test (2018).
- Modèle : MAE 13,2904; RMSE 16,9167; R² 0,4548.
- Baseline : MAE 18,6639; RMSE 22,9662.
- R : 55 268 mesures analysées, sorties statistiques, ANOVA et PNG produites.
- Catalogue : 6 jeux de données et 28 697 matériels indexés.
- API : santé `UP`, pipeline `OK`, recherche et prédiction vérifiées.
- Qualité : 6 contrats validés et lignes invalides mises en quarantaine.
- Reprise : 17/17 phases restaurées depuis checkpoint en moins d'une seconde.
- RBAC : chercheur autorisé, opérateur refusé pour la prédiction, audit écrit.
- Tests : 18/18 réussis, dont HTTP/RBAC/audit, Kafka, carte, images, PowerPoint,
  absence de doublons de prédictions et propagation d'erreur.

## Limites à annoncer pendant la soutenance

1. Il s'agit d'un prototype local, pas d'un cluster de production. Les noms des
   technologies simulées ne doivent pas être présentés comme des serveurs réels.
2. Les métadonnées ESSAI ne couvrent pas toutes les mesures : environ 81,4 % des
   régions et coordonnées sont absentes après jointure.
3. Le modèle bat la baseline mais doit être validé par un agronome. Les données
   météo, sol et conduite culturale amélioreraient sa portée.
4. Un passage en production exige infrastructure distribuée, TLS/SSO/RBAC,
   sauvegardes, haute disponibilité, tests de charge et supervision centralisée.
