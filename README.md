# Semences R&D — Pipeline Big Data

Plateforme d'analyse de données d'essais agronomiques pour une organisation de sélection variétale. Le système ingère, transforme, analyse et visualise des données multi-annuelles d'essais au champ (2015–2018) portant sur **8 espèces végétales**, **17 régions françaises**, **2 116 essais** et **136 358 mesures**.

---

## Table des matières

1. [Vue d'ensemble](#vue-densemble)
2. [Architecture du pipeline](#architecture-du-pipeline)
3. [Stack technique](#stack-technique)
4. [Structure du projet](#structure-du-projet)
5. [Données sources](#données-sources)
6. [Phases du pipeline](#phases-du-pipeline)
7. [Sorties produites](#sorties-produites)
8. [Installation & exécution](#installation--exécution)
9. [KPIs globaux](#kpis-globaux)

---

## Vue d'ensemble

Le projet simule une architecture Big Data d'entreprise complète, exécutable en local sans cluster. Chaque composant (Sqoop, NiFi, HBase, Kafka, Hive, Spark, Drill) est implémenté en Python de façon structurellement fidèle aux vraies API, avec une adaptation possible vers un cluster réel.

**Point d'entrée** : `main.py` orchestre les 12 phases en séquence, affiche des bandeaux de progression et produit un tableau récapitulatif des temps d'exécution.

**Portail de résultats** : `INDEX.html` — hub de documentation avec liens vers tous les rapports générés, KPIs et badges technologiques.

---

## Architecture du pipeline

```
┌──────────────────────────────────────────────────────────────┐
│                    SOURCES (CSV/)                            │
│  ESSAI · RESULTAT_ESSAIS · LK_CRISP_MATERIAL                 │
│  PARCELLE_SPECIFICATION · REF_ESPECES · TRIAL_QUALIFICATION  │
└─────────────────────────┬────────────────────────────────────┘
                          │
              Phase 1 — Sqoop (simulation JDBC→HDFS)
                          │
                          ▼
              data/raw/*.parquet       ← Couche RAW (HDFS simulé)
                          │
              Phase 2 — NiFi (routing, validation, conversion)
                          │
                          ▼
              data/transformed/*.parquet  ← Tables nettoyées
                          │
              Phase 3 — Talend ETL (jointures, enrichissement)
                          │
                          ▼
              data/enriched/fact_table   ← 136 358 lignes × 47 cols
                          │
          ┌───────────────┼──────────────────┬──────────────┐
          ▼               ▼                  ▼              ▼
       HBase           Kafka              Hive/DuckDB     Spark
  (SQLite sim.)   (threading/queue)    hive/*.csv     enriched/spark/
                          │
              Phase 9 — Drill/DuckDB (SQL ad-hoc sur fichiers)
                          │
                          ▼
              drill/*.csv
                          │
              Phase 10 — Analyse statistique (Python + R)
                          │
                          ▼
              reports/kpi_globaux.json · correlations.json · anova_region.csv
                          │
              Phase 11 — Visualisations (Matplotlib/Seaborn/Folium)
                          │
                          ▼
              reports/images/*.png · carte_essais.html
                          │
              Phase 12 — Dashboard HTML (Bootstrap/Jinja)
                          │
                          ▼
              reports/dashboard.html   ← Livrable final
```

---

## Stack technique

| Technologie | Implémentation locale | Rôle dans le pipeline |
|---|---|---|
| **Apache Sqoop** | Classe Python `SqoopJob` | Ingestion CSV → Parquet (simulation JDBC) |
| **Apache NiFi** | OOP `NiFiProcessor` chain | Orchestration de flux, routing, validation |
| **Talend ETL** | Pipelines Pandas | Nettoyage, normalisation, jointures → table de faits |
| **Apache HBase** | SQLite (`hbase/semences_hbase.db`) | Stockage NoSQL column-family (`cf:qualifier`) |
| **Apache Kafka** | Python `threading` + `queue` | Bus de messages, producteur/consommateur, alertes qualité |
| **Apache Hive** | DuckDB exécutant HiveQL | Entrepôt SQL analytique sur Parquet |
| **Apache Spark** | PySpark (fallback Pandas) | Agrégations distribuées, fonctions fenêtre |
| **Apache Drill** | DuckDB (syntaxe `dfs.*`) | SQL schema-free sur fichiers |
| **R** | `R/analyse_statistique.R` | ANOVA, Tukey HSD, ggplot2 |
| **Python** | pandas · numpy · scipy · matplotlib · seaborn · folium | Stats, graphiques, carte interactive |
| **HTML/Bootstrap** | Rapports auto-contenus | Dashboard style Tableau/Spotfire |

> **Note** : Kafka, Hive, HBase, Drill, NiFi et Sqoop sont **simulés en Python** pour fonctionner sans cluster. Le code est structuré pour être portable vers un vrai cluster.

---

## Structure du projet

```
Semance/
├── main.py                      # Orchestrateur — exécute les 12 phases en séquence
├── INDEX.html                   # Portail de documentation et de résultats
├── pipeline_output.txt          # Capture de sortie d'une exécution complète
│
├── CSV/                         # Données sources brutes (6 fichiers CSV, séparateur ;)
│   ├── ESSAI.csv
│   ├── RESULTAT_ESSAIS.csv
│   ├── LK_CRISP_MATERIAL_20190108.csv
│   ├── PARCELLE_SPECIFICATION_20190108.csv
│   ├── REF_ESPECES_20190108.csv
│   └── TRIAL_QUALIFICATION_20190108.csv
│
├── src/                         # Modules du pipeline (une phase = un fichier)
│   ├── 01_profiling.py          # Phase 2  — Gouvernance des données
│   ├── 02_etl.py                # Phase 4  — ETL Talend (table de faits)
│   ├── 03_analyse.py            # Phase 10 — Statistiques + R
│   ├── 04_visualisation.py      # Phase 11 — Graphiques + carte Folium
│   ├── 05_dashboard.py          # Phase 12 — Dashboard HTML final
│   ├── 06_sqoop_import.py       # Phase 1  — Ingestion Sqoop
│   ├── 07_nifi_flow.py          # Phase 3  — Flux NiFi
│   ├── 08_hbase_store.py        # Phase 5  — Stockage HBase
│   ├── 09_kafka_streaming.py    # Phase 6  — Streaming Kafka
│   ├── 10_hive_queries.py       # Phase 7  — Requêtes Hive/DuckDB
│   ├── 11_spark_analysis.py     # Phase 8  — Analyses Spark
│   └── 12_drill_queries.py      # Phase 9  — SQL Drill/DuckDB
│
├── data/
│   ├── raw/                     # Parquet bruts post-Sqoop
│   ├── transformed/             # Tables nettoyées post-NiFi/Talend
│   └── enriched/                # Table de faits + agrégats Spark
│       ├── fact_table.csv/.parquet
│       ├── anova_region.csv
│       ├── top_materiels.csv
│       ├── evolution_annuelle.csv
│       ├── stats_espece_trait.csv
│       ├── essais_par_region.csv
│       └── spark/               # Résultats Parquet Spark
│
├── hive/                        # Résultats des 5 requêtes HiveQL
├── hbase/                       # Base SQLite simulant HBase
├── kafka/                       # Messages consommés + alertes qualité + flux géo
├── drill/                       # Résultats des 6 requêtes Drill
│
├── R/
│   └── analyse_statistique.R    # ANOVA + Tukey HSD + ggplot2
│
└── reports/                     # Tous les rapports générés
    ├── dashboard.html            # ★ Livrable principal
    ├── carte_essais.html         # Carte interactive Folium
    ├── RAPPORT_TECHNIQUE.html    # Rapport d'architecture
    ├── kpi_globaux.json
    ├── profiling.json
    ├── correlations.json
    ├── spark_report.json
    ├── hive_report.json
    ├── kafka_report.json
    ├── hbase_summary.json
    ├── drill_report.json
    ├── nifi_provenance.json
    ├── sqoop_jobs.json
    └── images/                  # Graphiques PNG générés
```

---

## Données sources

Tous les fichiers CSV sont encodés en UTF-8, séparateur `;`, situés dans `CSV/`.

| Fichier | Lignes | Description |
|---|---|---|
| `ESSAI.csv` | ~492 | Expériences : ID essai, espèce, année, coordonnées GPS, région, département, indicateurs de fiabilité |
| `RESULTAT_ESSAIS.csv` | ~136 000 | Mesures de traits (`%MOIS`, `YD15QH`, `YD16QH`, `YDQH`, `YD`) par essai/réplication/entrée variétale |
| `LK_CRISP_MATERIAL_20190108.csv` | ~28 000 | Catalogue de matériel génétique : nom variété, pédigrée, structure, parents |
| `PARCELLE_SPECIFICATION_20190108.csv` | — | Spécifications parcellaires |
| `REF_ESPECES_20190108.csv` | — | Référentiel espèces/traits (codes espèce → noms français) |
| `TRIAL_QUALIFICATION_20190108.csv` | — | Métadonnées de qualification des essais |

**Espèces couvertes** (code → nom) :

| Code | Espèce | Part des données |
|---|---|---|
| `B` | Blé tendre | ~43 % |
| `C` | Colza | — |
| `T` | Triticale | — |
| `W` | Blé dur | — |
| `O` | Orge | — |
| `S` | Tournesol | — |
| `M` | Maïs | — |
| `L` / `P` | Autres | — |

---

## Phases du pipeline

### Phase 1 — Ingestion Sqoop (`06_sqoop_import.py`)
Lit les 6 CSV sources et simule un import `sqoop import --connect jdbc:... --target-dir /data/raw/`. Convertit en Parquet avec compression. Produit `data/raw/*.parquet` et `reports/sqoop_jobs.json`.

### Phase 2 — Profilage des données (`01_profiling.py`)
Gouvernance des données : pour chaque table, calcule le nombre de lignes/colonnes, types, taux de nullité par colonne, valeurs uniques, min/max/moyenne. Produit `reports/profiling.json`.

### Phase 3 — Flux NiFi (`07_nifi_flow.py`)
Simule une chaîne de processeurs NiFi :
`GetFile → ValidateRecord → RouteOnAttribute → TransformRecord → PutHDFS(raw) → ConvertAvroToParquet → UpdateAttribute → PutHDFS(enriched) → LogMessage`
Produit `reports/nifi_provenance.json`.

### Phase 4 — ETL Talend (`02_etl.py`)
Transformation centrale : nettoyage, typage, normalisation des 6 tables. Jointure expériences × résultats × matériaux × parcelles → **table de faits** (136 358 lignes × 47 colonnes). Sauvegarde en Parquet dans `data/transformed/` et `data/enriched/`.

### Phase 5 — Stockage HBase (`08_hbase_store.py`)
Simule HBase via SQLite avec 3 tables et familles de colonnes :
- `experiments` (CF : `info`, `geo`, `quality`)
- `results` (CF : `measurement`, `metadata`)
- `materials` (CF : `identity`, `genetics`, `taxonomy`)

Clés de ligne au format HBase : `ANNÉE#ID_ESSAI`. Produit `hbase/semences_hbase.db` et `reports/hbase_summary.json`.

### Phase 6 — Streaming Kafka (`09_kafka_streaming.py`)
Simule un bus Kafka avec 4 topics (`experimental-results`, `material-updates`, `quality-alerts`, `geo-stream`). Producteur publie les résultats enrichis ; consommateur détecte les valeurs aberrantes (ex. `YD15QH = 133.8 q/ha` → WARNING). Produit `kafka/consumed_results.json`, `kafka/quality_alerts.json`, `kafka/geo_stream.csv`.

### Phase 7 — Requêtes Hive (`10_hive_queries.py`)
Exécute 5 requêtes HiveQL analytiques via DuckDB sur les fichiers Parquet :
1. Rendement moyen par espèce × année
2. Top 10 matériaux par rendement
3. Analyse régionale
4. Tendance d'évolution annuelle
5. Statistiques des essais de qualification

Produit `hive/Q1_*.csv` à `hive/Q5_*.csv` et `reports/hive_report.json`.

### Phase 8 — Analyses Spark (`11_spark_analysis.py`)
Agrégations distribuées avec PySpark (fallback Pandas automatique) :
- Statistiques (moyenne, écart-type) par espèce × trait
- Statistiques régionales
- Évolution annuelle

Produit `data/enriched/spark/*.parquet` et `reports/spark_report.json`.

### Phase 9 — Requêtes Drill (`12_drill_queries.py`)
SQL schema-free via DuckDB avec la convention de nommage `dfs.*` de Drill. 6 requêtes :
1. Découverte du schéma (`DQ1`)
2. Exploration rapide (`DQ2`)
3. Détection des outliers (`DQ4`)
4. Top-N par région (`DQ5`)
5. Métadonnées Parquet (`DQ6`)

Produit `drill/DQ*.csv` et `reports/drill_report.json`.

### Phase 10 — Analyse statistique (`03_analyse.py`)
- KPIs globaux (2 116 essais, 28 697 matériaux, 8 espèces, 17 régions)
- Statistiques descriptives par espèce × trait
- ANOVA à un facteur par région (`scipy.stats`) — effets régionaux significatifs (p ≈ 0)
- Corrélations de Pearson entre traits de rendement
- Appel du script R `R/analyse_statistique.R` pour les tests post-hoc Tukey HSD

Produit `reports/kpi_globaux.json`, `reports/correlations.json`, `data/enriched/anova_region.csv`.

### Phase 11 — Visualisations (`04_visualisation.py`)
Génère tous les graphiques PNG (Matplotlib/Seaborn) :
- Distribution des essais par espèce
- Boxplots de rendement
- Courbes d'évolution temporelle
- Heatmaps de corrélation
- Graphiques de pédigrée

Construit `reports/carte_essais.html` : carte Folium interactive avec marqueurs GPS clusterisés de tous les sites d'essai.

### Phase 12 — Dashboard HTML (`05_dashboard.py`)
Consolide tout en `reports/dashboard.html` : KPIs JSON, tableaux ANOVA, top matériaux, graphiques PNG encodés en base64 inline, iframe de la carte Folium. Rapport final auto-contenu, style Tableau/Spotfire.

---

## Sorties produites

### `reports/`

| Fichier | Description |
|---|---|
| `dashboard.html` | ★ **Livrable principal** — rapport interactif consolidé |
| `carte_essais.html` | Carte Folium avec marqueurs GPS clusterisés |
| `RAPPORT_TECHNIQUE.html` | Rapport d'architecture technique |
| `kpi_globaux.json` | KPIs : 2 116 essais, 28 697 matériaux, 136 358 mesures |
| `profiling.json` | Profil qualité des 6 tables sources |
| `correlations.json` | Matrice de corrélations Pearson entre traits |
| `*_report.json` | Rapports machine par technologie (spark, hive, kafka, hbase, drill, nifi, sqoop) |
| `images/` | Tous les graphiques PNG |

### `data/enriched/`

| Fichier | Description |
|---|---|
| `fact_table.parquet/.csv` | Table de faits centrale (136 358 × 47) |
| `anova_region.csv` | Résultats ANOVA par espèce × trait |
| `top_materiels.csv` | Meilleures variétés par rendement (ex. `RGT_KNIGHTSBRIDGE`, Blé tendre, ~124 q/ha) |
| `evolution_annuelle.csv` | Tendances de rendement 2015–2018 par espèce |
| `stats_espece_trait.csv` | Stats descriptives (moy, écart-type, min, max) par espèce × trait |
| `essais_par_region.csv` | Nombre d'essais par région |

---

## Installation & exécution

### Prérequis

- Python 3.8+
- (Optionnel) R + packages `anova`, `TukeyHSD`, `ggplot2`
- (Optionnel) PySpark pour les analyses Spark natives

### Installation des dépendances Python

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install pandas numpy scipy matplotlib seaborn folium duckdb pyarrow
```

### Exécution complète du pipeline

```bash
python main.py
```

Le pipeline exécute les 12 phases en séquence et affiche un tableau récapitulatif des temps et statuts.

### Consultation des résultats

Ouvrir `reports/dashboard.html` dans un navigateur pour le rapport final, ou `INDEX.html` pour le portail de navigation complet.

---

## KPIs globaux

| Indicateur | Valeur |
|---|---|
| Essais au champ | **2 116** |
| Matériaux génétiques | **28 697** |
| Mesures totales | **136 358** |
| Espèces analysées | **8** |
| Régions françaises | **17** |
| Période couverte | **2015 – 2018** |
| Taille table de faits | **136 358 lignes × 47 colonnes** |
| Meilleur rendement détecté | **~133.8 q/ha** (alerte Kafka WARNING) |
| Meilleure variété Blé tendre | **RGT_KNIGHTSBRIDGE** (~124 q/ha) |
