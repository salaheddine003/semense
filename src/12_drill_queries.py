"""
Apache Drill — SQL ad-hoc sur fichiers (simulation DuckDB)
==========================================================
Apache Drill permet d'exécuter du SQL directement sur des fichiers
(Parquet, CSV, JSON) sans définir de schéma préalable.

Drill architecture simulée :
  dfs.*      → workspace 'distributed file system' = nos répertoires locaux
  dfs.raw.*  → data/raw/*.parquet
  dfs.enriched.* → data/enriched/*.parquet
  cp.*       → classpath (non utilisé ici)

L'API DuckDB est syntaxiquement quasi-identique au SQL Drill ;
les requêtes ci-dessous fonctionnent telles quelles dans Apache Drill
avec ajustement du préfixe de fichier.
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
DRILL_DIR  = os.path.join(BASE_DIR, "drill")
REPORT_DIR = os.path.join(BASE_DIR, "reports")

os.makedirs(DRILL_DIR, exist_ok=True)


# ─────────────────────────────────────────────────────────────
# Drill workspaces → chemins locaux
# ─────────────────────────────────────────────────────────────

def workspaces(raw: str, enriched: str) -> dict:
    raw      = raw.replace("\\", "/")
    enriched = enriched.replace("\\", "/")
    return {
        "dfs.raw.essai":            f"'{raw}/essai.parquet'",
        "dfs.raw.resultat":         f"'{raw}/resultats.parquet'",
        "dfs.raw.material":         f"'{raw}/materiel.parquet'",
        "dfs.raw.parcelle":         f"'{raw}/parcelle.parquet'",
        "dfs.enriched.fact_table":  f"'{enriched}/fact_table.parquet'",
        "dfs.enriched.spark_agg":   f"'{enriched}/spark/spark_agg_espece_trait.parquet'",
    }


# ─────────────────────────────────────────────────────────────
# Requêtes Apache Drill
# ─────────────────────────────────────────────────────────────

def build_queries(ws: dict) -> list:
    fact = ws["dfs.enriched.fact_table"]
    raw_essai = ws["dfs.raw.essai"]

    return [
        {
            "id":   "DQ1_schema_discovery",
            "desc": "Découverte automatique du schéma (DESCRIBE TABLE équivalent)",
            "drill_sql": f"""
-- Apache Drill — schema discovery
-- SELECT * FROM INFORMATION_SCHEMA.`COLUMNS` WHERE TABLE_NAME = 'fact_table'
SELECT column_name, column_type
FROM (DESCRIBE SELECT * FROM read_parquet({fact}) LIMIT 0)
""",
            "duckdb_sql": f"""
SELECT column_name, column_type
FROM (DESCRIBE SELECT * FROM read_parquet({fact}) LIMIT 0)
""",
        },
        {
            "id":   "DQ2_exploration_rapide",
            "desc": "Exploration rapide — distribution espèces (dfs.enriched)",
            "drill_sql": f"""
-- Apache Drill — SQL on file
SELECT ESPECE_FR, COUNT(*) AS nb, ROUND(AVG(RESULT_NUM), 2) AS avg_val
FROM dfs.enriched.`fact_table.parquet`
WHERE RESULT_NUM IS NOT NULL
GROUP BY ESPECE_FR
ORDER BY nb DESC
""",
            "duckdb_sql": f"""
SELECT ESPECE_FR, COUNT(*) AS nb, ROUND(AVG(RESULT_NUM), 2) AS avg_val
FROM read_parquet({fact})
WHERE RESULT_NUM IS NOT NULL
GROUP BY ESPECE_FR
ORDER BY nb DESC
""",
        },
        {
            "id":   "DQ3_cross_file_join",
            "desc": "Jointure cross-fichiers (Drill relie fichiers sans ETL préalable)",
            "drill_sql": f"""
-- Apache Drill — join between two autonomous files
SELECT e.SL_TRIAL, r.TRAIT, COUNT(*) AS nb_mesures
FROM dfs.raw.`essai.parquet` e
JOIN dfs.raw.`resultat_essais.parquet` r
  ON CAST(e.LK_EXPERIMENT_EXPERIMENT_ID AS BIGINT) =
     CAST(r.LK_EXPERIMENT_EXPERIMENT_ID AS BIGINT)
GROUP BY e.SL_TRIAL, r.TRAIT
HAVING nb_mesures > 10
ORDER BY nb_mesures DESC
LIMIT 15
""",
            "duckdb_sql": f"""
SELECT e.SL_TRIAL,
       r.TRAIT,
       COUNT(*) AS nb_mesures
FROM read_parquet({raw_essai}) e
JOIN read_parquet({ws["dfs.raw.resultat"]}) r
  ON TRY_CAST(e.LK_EXPERIMENT_EXPERIMENT_ID AS BIGINT) =
     TRY_CAST(r.LK_EXPERIMENT_EXPERIMENT_ID AS BIGINT)
GROUP BY e.SL_TRIAL, r.TRAIT
HAVING COUNT(*) > 10
ORDER BY nb_mesures DESC
LIMIT 15
""",
        },
        {
            "id":   "DQ4_outliers_detection",
            "desc": "Détection d'outliers ad-hoc via SQL pur",
            "drill_sql": f"""
-- Apache Drill — outlier detection without pre-processing
SELECT TRAIT, RESULT_NUM, ESPECE_FR, YEAR, REGION
FROM dfs.enriched.`fact_table.parquet`
WHERE RESULT_NUM IS NOT NULL
  AND TRAIT = 'YD15QH'
  AND (
    RESULT_NUM < (SELECT AVG(RESULT_NUM) - 3*STDDEV_POP(RESULT_NUM)
                  FROM dfs.enriched.`fact_table.parquet`
                  WHERE TRAIT = 'YD15QH')
    OR
    RESULT_NUM > (SELECT AVG(RESULT_NUM) + 3*STDDEV_POP(RESULT_NUM)
                  FROM dfs.enriched.`fact_table.parquet`
                  WHERE TRAIT = 'YD15QH')
  )
ORDER BY ABS(RESULT_NUM) DESC
LIMIT 20
""",
            "duckdb_sql": f"""
WITH stats AS (
    SELECT AVG(RESULT_NUM) AS mu, STDDEV_POP(RESULT_NUM) AS sigma
    FROM read_parquet({fact})
    WHERE TRAIT = 'YD15QH' AND RESULT_NUM IS NOT NULL
)
SELECT f.TRAIT, f.RESULT_NUM, f.ESPECE_FR, f.YEAR, f.REGION
FROM   read_parquet({fact}) f, stats s
WHERE  f.TRAIT = 'YD15QH'
  AND  f.RESULT_NUM IS NOT NULL
  AND  ABS(f.RESULT_NUM - s.mu) > 3 * s.sigma
ORDER BY ABS(f.RESULT_NUM) DESC
LIMIT 20
""",
        },
        {
            "id":   "DQ5_topN_by_region",
            "desc": "TOP 5 matériels par région (window function)",
            "drill_sql": f"""
-- Apache Drill — window functions
SELECT REGION, MAIN_NAME, ESPECE_FR, avg_yd, rk
FROM (
  SELECT REGION, MAIN_NAME, ESPECE_FR,
         ROUND(AVG(RESULT_NUM), 3) AS avg_yd,
         ROW_NUMBER() OVER (PARTITION BY REGION ORDER BY AVG(RESULT_NUM) DESC) AS rk
  FROM dfs.enriched.`fact_table.parquet`
  WHERE TRAIT = 'YD15QH' AND RESULT_NUM IS NOT NULL
  GROUP BY REGION, MAIN_NAME, ESPECE_FR
) t
WHERE rk <= 5
ORDER BY REGION, rk
""",
            "duckdb_sql": f"""
SELECT REGION, MAIN_NAME, ESPECE_FR, avg_yd, rk
FROM (
  SELECT REGION, MAIN_NAME, ESPECE_FR,
         ROUND(AVG(RESULT_NUM), 3) AS avg_yd,
         ROW_NUMBER() OVER (PARTITION BY REGION ORDER BY AVG(RESULT_NUM) DESC) AS rk
  FROM read_parquet({fact})
  WHERE TRAIT = 'YD15QH' AND RESULT_NUM IS NOT NULL
  GROUP BY REGION, MAIN_NAME, ESPECE_FR
) t
WHERE rk <= 5
ORDER BY REGION, rk
""",
        },
        {
            "id":   "DQ6_parquet_metadata",
            "desc": "Introspection fichiers Parquet (row groups, compression)",
            "drill_sql": f"""
-- Apache Drill — parquet_metadata function (Drill native)
SELECT file_path, total_row_count, total_columns
FROM dfs.enriched.`fact_table.parquet.metadata`
""",
            "duckdb_sql": f"""
SELECT COUNT(*) AS total_rows,
       COUNT(DISTINCT ESPECE_FR) AS nb_especes,
       COUNT(DISTINCT TRAIT)     AS nb_traits,
       COUNT(DISTINCT YEAR)      AS nb_annees,
       MIN(YEAR)                 AS annee_min,
       MAX(YEAR)                 AS annee_max
FROM read_parquet({fact})
""",
        },
    ]


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

def run():
    print("=" * 80)
    print("  APACHE DRILL — SQL ad-hoc sur fichiers (dfs workspace)")
    print("  Drillbit : localhost:31010  |  Storage plugin : dfs")
    print("=" * 80)

    fact_path = os.path.join(ENRICH_DIR, "fact_table.parquet")
    if not os.path.exists(fact_path):
        print("  ⚠ Table de faits introuvable.")
        return

    ws      = workspaces(RAW_DIR, ENRICH_DIR)
    queries = build_queries(ws)
    con     = duckdb.connect()
    log     = []

    print(f"\n  Workspaces Drill configurés :")
    for k, v in ws.items():
        exists = os.path.exists(v.strip("'").replace("/", os.sep))
        mark   = "✔" if exists else "✘"
        print(f"    {mark}  {k:<40}  {v}")

    print(f"\n  ── Exécution des requêtes Drill ──")

    for q in queries:
        print(f"\n  [{q['id']}]  {q['desc']}")
        # Affichage requête Drill
        for line in q["drill_sql"].strip().splitlines():
            print(f"  │ {line}")
        t0 = time.time()
        try:
            df      = con.execute(q["duckdb_sql"]).df()
            elapsed = round(time.time() - t0, 3)
            print(f"  ► {len(df)} lignes  ({elapsed}s)")
            if not df.empty:
                print(df.head(8).to_string(index=False))
            out = os.path.join(DRILL_DIR, f"{q['id']}.csv")
            df.to_csv(out, index=False, sep=";")
            log.append({"query": q["id"], "rows": len(df), "elapsed_s": elapsed, "status": "OK"})
        except Exception as e:
            elapsed = round(time.time() - t0, 3)
            print(f"  ✘ Erreur : {e}")
            log.append({"query": q["id"], "rows": 0, "elapsed_s": elapsed, "status": str(e)})

    con.close()

    # Résumé
    print("\n  ── Résumé Drill ──")
    ok = sum(1 for r in log if r["status"] == "OK")
    print(f"  Requêtes OK : {ok}/{len(log)}")
    for r in log:
        st = "✔" if r["status"] == "OK" else "✘"
        print(f"  {st}  {r['query']:<40}  {r['rows']:>6} lignes  {r['elapsed_s']}s")

    # Rapport
    os.makedirs(REPORT_DIR, exist_ok=True)
    report = {
        "drillbit":  "localhost:31010",
        "storage":   "dfs",
        "workspaces": list(ws.keys()),
        "queries":   log,
        "timestamp": datetime.now().isoformat(),
    }
    with open(os.path.join(REPORT_DIR, "drill_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n  Rapport Drill   : reports/drill_report.json")
    print(f"  Résultats CSV   : drill/*.csv")

    if ok != len(log):
        raise RuntimeError(f"{len(log) - ok} requête(s) Drill en échec")


if __name__ == "__main__":
    run()
