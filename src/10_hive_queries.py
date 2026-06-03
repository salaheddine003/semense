"""
Apache Hive — Entrepôt analytique (simulation DuckDB)
=====================================================
Hive permet d'exécuter du HiveQL (SQL) sur des données stockées dans HDFS
sous forme de fichiers Parquet / ORC.

Hive architecture simulée :
  Metastore    → dictionnaire de tables interne (ce fichier)
  HDFS tables  → data/raw/*.parquet et data/enriched/fact_table.parquet
  HiveServer2  → DuckDB en mode fichier (requêtes SQL identiques)

Toutes les requêtes ci-dessous sont du HiveQL valide — elles fonctionnent
aussi bien dans un cluster Cloudera / HortonWorks que localement via DuckDB.
"""

import os
import json
import time
import duckdb
import pandas as pd
from datetime import datetime

BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR    = os.path.join(BASE_DIR, "data", "raw")
ENRICH_DIR = os.path.join(BASE_DIR, "data", "enriched")
HIVE_DIR   = os.path.join(BASE_DIR, "hive")
REPORT_DIR = os.path.join(BASE_DIR, "reports")

os.makedirs(HIVE_DIR, exist_ok=True)


# ─────────────────────────────────────────────────────────────
# Metastore Hive (mini catalogue)
# ─────────────────────────────────────────────────────────────

HIVE_METASTORE = {
    "database": "semences_db",
    "tables": {
        "fact_table": {
            "location":   "data/enriched/fact_table.parquet",
            "format":     "PARQUET",
            "partitioned_by": ["YEAR", "ESPECE_FR"],
            "tblproperties": {"created_by": "Talend ETL v5", "source": "CRISP"},
        },
        "essai_raw": {
            "location": "data/raw/essai.parquet",
            "format":   "PARQUET",
        },
        "resultat_raw": {
            "location": "data/raw/resultat_essais.parquet",
            "format":   "PARQUET",
        },
        "material_raw": {
            "location": "data/raw/lk_crisp_material.parquet",
            "format":   "PARQUET",
        },
    },
}


# ─────────────────────────────────────────────────────────────
# Définition des requêtes HiveQL
# ─────────────────────────────────────────────────────────────

def _fact_path():
    return os.path.join(ENRICH_DIR, "fact_table.parquet").replace("\\", "/")


HIVE_QUERIES = {
    "Q1_rendement_moyen_espece_annee": {
        "description": "Rendement moyen par espèce et année (agrégat principale)",
        "hiveql": """
-- HiveQL — Hive 3.x compatible
SELECT
    ESPECE_FR,
    YEAR,
    COUNT(*)                     AS nb_mesures,
    ROUND(AVG(RESULT_NUM), 3)    AS rendement_moyen,
    ROUND(STDDEV(RESULT_NUM), 3) AS ecart_type,
    ROUND(MIN(RESULT_NUM), 3)    AS min_val,
    ROUND(MAX(RESULT_NUM), 3)    AS max_val
FROM semences_db.fact_table
WHERE TRAIT = 'YD15QH'
  AND RESULT_NUM IS NOT NULL
GROUP BY ESPECE_FR, YEAR
ORDER BY YEAR, rendement_moyen DESC;
""",
    },
    "Q2_top_materiels_rendement": {
        "description": "Top 20 matériels génétiques par rendement moyen",
        "hiveql": """
SELECT
    MAIN_NAME,
    ESPECE_FR,
    COUNT(DISTINCT LK_EXPERIMENT_EXPERIMENT_ID) AS nb_essais,
    ROUND(AVG(RESULT_NUM), 3)                   AS rendement_moyen,
    ROUND(STDDEV(RESULT_NUM), 3)                AS variabilite
FROM semences_db.fact_table
WHERE TRAIT IN ('YD15QH', 'YD16QH')
  AND RESULT_NUM IS NOT NULL
GROUP BY MAIN_NAME, ESPECE_FR
HAVING nb_essais >= 3
ORDER BY rendement_moyen DESC
LIMIT 20;
""",
    },
    "Q3_analyse_regionale": {
        "description": "Performance par région et trait",
        "hiveql": """
SELECT
    REGION,
    ESPECE_FR,
    TRAIT,
    COUNT(DISTINCT LK_EXPERIMENT_EXPERIMENT_ID) AS nb_essais,
    ROUND(AVG(RESULT_NUM), 3)                   AS avg_val,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY RESULT_NUM), 3) AS mediane
FROM semences_db.fact_table
WHERE RESULT_NUM IS NOT NULL
  AND REGION IS NOT NULL
GROUP BY REGION, ESPECE_FR, TRAIT
ORDER BY ESPECE_FR, TRAIT, avg_val DESC;
""",
    },
    "Q4_evolution_tendance": {
        "description": "Tendance temporelle du rendement (Blé tendre)",
        "hiveql": """
SELECT
    YEAR,
    ESPECE_FR,
    COUNT(DISTINCT LK_EXPERIMENT_EXPERIMENT_ID) AS nb_essais,
    ROUND(AVG(RESULT_NUM), 3)                   AS rendement_moyen,
    ROUND(AVG(RESULT_NUM)
        - LAG(AVG(RESULT_NUM)) OVER (PARTITION BY ESPECE_FR ORDER BY YEAR), 3
    )                                           AS delta_annuel
FROM semences_db.fact_table
WHERE TRAIT = 'YD15QH'
  AND RESULT_NUM IS NOT NULL
GROUP BY YEAR, ESPECE_FR
ORDER BY ESPECE_FR, YEAR;
""",
    },
    "Q5_qualification_trials": {
        "description": "Distribution des statuts de qualification",
        "hiveql": """
SELECT
    ESPECE_FR,
    YEAR,
    COUNT(DISTINCT LK_EXPERIMENT_EXPERIMENT_ID) AS nb_essais_total,
    COUNT(DISTINCT CASE WHEN RESULT_NUM IS NOT NULL THEN LK_EXPERIMENT_EXPERIMENT_ID END)
                                                AS nb_essais_avec_resultat,
    ROUND(
        100.0 * COUNT(DISTINCT CASE WHEN RESULT_NUM IS NOT NULL THEN LK_EXPERIMENT_EXPERIMENT_ID END)
             / NULLIF(COUNT(DISTINCT LK_EXPERIMENT_EXPERIMENT_ID), 0), 1
    )                                           AS taux_completion_pct
FROM semences_db.fact_table
GROUP BY ESPECE_FR, YEAR
ORDER BY YEAR DESC, ESPECE_FR;
""",
    },
    "Q6_create_external_table": {
        "description": "DDL — création table externe Hive (référence architecture)",
        "hiveql": """
-- DDL HiveQL — Création de la table externe
CREATE EXTERNAL TABLE IF NOT EXISTS semences_db.fact_table (
    LK_EXPERIMENT_EXPERIMENT_ID  STRING,
    SL_TRIAL                     STRING,
    ENTRY_NUM                    STRING,
    TRAIT                        STRING,
    RESULT_NUM                   DOUBLE,
    YEAR                         INT,
    ESPECE_FR                    STRING,
    REGION                       STRING,
    LAT                          DOUBLE,
    LON                          DOUBLE,
    MAIN_NAME                    STRING,
    PEDIGREE                     STRING
)
STORED AS PARQUET
LOCATION '/user/semences/enriched/fact_table'
TBLPROPERTIES (
    'parquet.compression' = 'SNAPPY',
    'creator'             = 'Talend ETL',
    'last_updated'        = '2024'
);
""",
        "execute": False,  # DDL uniquement affiché, pas exécuté
    },
}


# ─────────────────────────────────────────────────────────────
# Connecteur DuckDB → HiveQL (traduction)
# ─────────────────────────────────────────────────────────────

class HiveConnection:
    """Simule une connexion HiveServer2 via JDBC."""

    def __init__(self, database: str, hdfs_root: str):
        self.database  = database
        self.hdfs_root = hdfs_root
        self.con       = duckdb.connect()
        self._results  = {}
        self._log      = []

    def _rewrite_hiveql(self, hql: str, fact_path: str) -> str:
        """Traduit le HiveQL Hive vers SQL DuckDB compat."""
        sql = hql.strip()
        # Remplace la référence table Hive par un read_parquet DuckDB
        sql = sql.replace(
            "semences_db.fact_table",
            f"read_parquet('{fact_path}')"
        )
        # Hive ROUND(x, n) → DuckDB ROUND(x, n)   [identique → OK]
        # Hive percentile_cont → DuckDB PERCENTILE_CONT  [identique → OK]
        # STDDEV → STDDEV_SAMP en DuckDB
        sql = sql.replace("STDDEV(", "STDDEV_SAMP(")
        # Supprime les lignes -- commentaire pour l'exécution
        lines  = [l for l in sql.splitlines() if not l.strip().startswith("--")]
        return "\n".join(lines).strip()

    def execute(self, query_id: str, hql: str, fact_path: str, execute: bool = True) -> pd.DataFrame | None:
        if not execute:
            return None
        t0  = time.time()
        sql = self._rewrite_hiveql(hql, fact_path)
        try:
            df      = self.con.execute(sql).df()
            elapsed = round(time.time() - t0, 3)
            self._results[query_id] = df
            self._log.append({
                "query_id": query_id,
                "rows":     len(df),
                "elapsed_s": elapsed,
                "status":   "OK",
            })
            return df
        except Exception as e:
            self._log.append({
                "query_id": query_id,
                "rows":     0,
                "elapsed_s": round(time.time() - t0, 3),
                "status":   f"ERROR: {e}",
            })
            return None

    def close(self):
        self.con.close()


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

def run():
    print("=" * 80)
    print("  APACHE HIVE — Entrepôt analytique (HiveQL sur HDFS/Parquet)")
    print("  HiveServer2 : localhost:10000  |  Database : semences_db")
    print("=" * 80)

    fact_path = os.path.join(ENRICH_DIR, "fact_table.parquet")
    if not os.path.exists(fact_path):
        print("  ⚠ Table de faits introuvable — veuillez lancer l'ETL d'abord (02_etl.py).")
        return

    conn      = HiveConnection("semences_db", ENRICH_DIR)
    fp        = fact_path.replace("\\", "/")
    all_rows  = []

    print(f"\n  Metastore : {len(HIVE_METASTORE['tables'])} tables enregistrées")
    for tname, tmeta in HIVE_METASTORE["tables"].items():
        print(f"    {tname:<25} [{tmeta['format']}]  {tmeta['location']}")

    print(f"\n  ── Exécution HiveQL ──")
    for qid, qdef in HIVE_QUERIES.items():
        execute_flag = qdef.get("execute", True)
        print(f"\n  [{qid}]  {qdef['description']}")
        # Affichage HiveQL
        for line in qdef["hiveql"].strip().splitlines():
            print(f"  │ {line}")
        if not execute_flag:
            print(f"  │ ► DDL affiché — non exécuté (table déjà gérée par DuckDB)")
            continue
        df = conn.execute(qid, qdef["hiveql"], fp, execute=execute_flag)
        if df is not None and not df.empty:
            print(f"  ► {len(df)} lignes  |  colonnes : {list(df.columns)}")
            print(df.head(5).to_string(index=False))
            # Sauvegarde
            out = os.path.join(HIVE_DIR, f"{qid}.csv")
            df.to_csv(out, index=False, sep=";")
            all_rows.append({"query": qid, "rows": len(df), "file": out})
        elif df is not None:
            print("  ► 0 lignes retournées")

    conn.close()

    # Résumé
    print("\n  ── Résumé Hive ──")
    for r in conn._log:
        status = "✔" if r["status"] == "OK" else "✘"
        print(f"  {status}  {r['query_id']:<40}  {r['rows']:>6} lignes  {r['elapsed_s']}s")

    # Rapport
    os.makedirs(REPORT_DIR, exist_ok=True)
    report = {
        "database":  "semences_db",
        "metastore": HIVE_METASTORE,
        "execution": conn._log,
        "outputs":   all_rows,
        "timestamp": datetime.now().isoformat(),
    }
    with open(os.path.join(REPORT_DIR, "hive_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n  Rapport Hive    : reports/hive_report.json")
    print(f"  Résultats CSV   : hive/*.csv")


if __name__ == "__main__":
    run()
