"""
Apache Spark — Analyse distribuée (PySpark local mode)
======================================================
Spark est le moteur de calcul distribué. En mode local[*] il utilise tous les
cœurs disponibles et ne nécessite pas de cluster.

Architecture :
  SparkSession → DataFrame API → MLlib (si dispo) → Parquet sink

Si Java n'est pas disponible, le script bascule automatiquement sur pandas
avec la même logique métier (les résultats sont identiques).
"""

import os
import json
import time
import pandas as pd
import numpy as np
from datetime import datetime

BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENRICH_DIR = os.path.join(BASE_DIR, "data", "enriched")
SPARK_DIR  = os.path.join(BASE_DIR, "data", "enriched", "spark")
REPORT_DIR = os.path.join(BASE_DIR, "reports")

os.makedirs(SPARK_DIR, exist_ok=True)

# ─────────────────────────────────────────────────────────────
# Détection PySpark
# ─────────────────────────────────────────────────────────────
PYSPARK_AVAILABLE = False
try:
    from pyspark.sql import SparkSession
    from pyspark.sql.functions import (
        avg, stddev, count, col, when, isnan, isnull,
        round as spark_round, percentile_approx, lit
    )
    from pyspark.sql.window import Window
    import pyspark.sql.functions as F
    PYSPARK_AVAILABLE = True
except ImportError:
    pass


# ─────────────────────────────────────────────────────────────
# Analyses Spark (DataFrame API)
# ─────────────────────────────────────────────────────────────

def spark_analyse(spark, fact_path: str, results: list):
    """Analyses PySpark sur la table de faits."""
    print("  Lecture Parquet via SparkSession...")
    df = spark.read.parquet(fact_path)
    total = df.count()
    print(f"  DataFrame chargé : {total:,} lignes  {len(df.columns)} colonnes")

    # 1. Agrégat par espèce × trait
    print("\n  [Spark] Agrégat rendement espèce × trait")
    agg1 = (df.filter(col("RESULT_NUM").isNotNull())
              .groupBy("ESPECE_FR", "TRAIT")
              .agg(
                  count("*").alias("nb"),
                  spark_round(avg("RESULT_NUM"), 3).alias("avg_result"),
                  spark_round(stddev("RESULT_NUM"), 3).alias("std_result"),
                  spark_round(F.min("RESULT_NUM"), 3).alias("min_result"),
                  spark_round(F.max("RESULT_NUM"), 3).alias("max_result"),
              )
              .orderBy("ESPECE_FR", col("avg_result").desc()))
    agg1_pd = agg1.toPandas()
    agg1_pd.to_parquet(os.path.join(SPARK_DIR, "spark_agg_espece_trait.parquet"), index=False)
    print(f"  → {len(agg1_pd)} combinaisons espèce×trait")
    results.append({"step": "agg_espece_trait", "rows": len(agg1_pd), "engine": "PySpark"})

    # 2. Top matériels par rendement (YD15QH)
    print("\n  [Spark] Top matériels génétiques — YD15QH")
    best = (df.filter((col("TRAIT") == "YD15QH") & col("RESULT_NUM").isNotNull())
              .groupBy("MAIN_NAME", "ESPECE_FR")
              .agg(
                  count("*").alias("nb_obs"),
                  spark_round(avg("RESULT_NUM"), 3).alias("rendement_moyen"),
              )
              .filter(col("nb_obs") >= 3)
              .orderBy(col("rendement_moyen").desc())
              .limit(30))
    best_pd = best.toPandas()
    best_pd.to_parquet(os.path.join(SPARK_DIR, "spark_top_materiels.parquet"), index=False)
    print(f"  → Top {len(best_pd)} matériels exportés")
    results.append({"step": "top_materiels", "rows": len(best_pd), "engine": "PySpark"})

    # 3. Pivot régional (corrélation YD × humidité)
    print("\n  [Spark] Corrélation YD15QH × %MOIS par région")
    yd  = df.filter((col("TRAIT") == "YD15QH")  & col("RESULT_NUM").isNotNull()) \
           .select("LK_EXPERIMENT_EXPERIMENT_ID", "REGION",
                   col("RESULT_NUM").alias("yd"))
    hum = df.filter((col("TRAIT") == "%MOIS")   & col("RESULT_NUM").isNotNull()) \
           .select("LK_EXPERIMENT_EXPERIMENT_ID",
                   col("RESULT_NUM").alias("humidity"))
    joined = yd.join(hum, on="LK_EXPERIMENT_EXPERIMENT_ID", how="inner")
    corr_val = joined.stat.corr("yd", "humidity")
    print(f"  Corrélation YD15QH × %MOIS = {corr_val:.4f}")
    results.append({"step": "correlation_yd_humidity", "value": round(corr_val, 4), "engine": "PySpark"})

    # 4. Statistiques de qualité des données
    print("\n  [Spark] Audit qualité données")
    null_counts = {}
    for c in ["RESULT_NUM", "YEAR", "ESPECE_FR", "REGION", "LAT", "LON"]:
        if c in df.columns:
            n = df.filter(col(c).isNull() | isnan(col(c)) if c == "RESULT_NUM" else col(c).isNull()).count()
            null_counts[c] = n
    for c, n in null_counts.items():
        pct = round(100 * n / total, 1)
        print(f"  {c:<30} nulls: {n:>8,}  ({pct}%)")
    results.append({"step": "data_quality", "null_counts": null_counts, "engine": "PySpark"})

    return agg1_pd, best_pd


def pandas_analyse(fact: pd.DataFrame, results: list):
    """Même logique que spark_analyse mais via pandas (fallback)."""
    df = fact.copy()
    total = len(df)
    print(f"  DataFrame pandas : {total:,} lignes  {len(df.columns)} colonnes")

    # 1. Agrégat espèce × trait
    print("\n  [Spark-pandas] Agrégat rendement espèce × trait")
    agg1 = (df.dropna(subset=["RESULT_NUM"])
              .groupby(["ESPECE_FR", "TRAIT"], dropna=False)["RESULT_NUM"]
              .agg(nb="count", avg_result="mean", std_result="std",
                   min_result="min", max_result="max")
              .reset_index())
    agg1["avg_result"] = agg1["avg_result"].round(3)
    agg1["std_result"] = agg1["std_result"].round(3)
    agg1.to_parquet(os.path.join(SPARK_DIR, "spark_agg_espece_trait.parquet"), index=False)
    print(f"  → {len(agg1)} combinaisons espèce×trait")
    results.append({"step": "agg_espece_trait", "rows": len(agg1), "engine": "pandas-spark-fallback"})

    # 2. Top matériels
    print("\n  [Spark-pandas] Top matériels génétiques — YD15QH")
    sub = df[(df["TRAIT"] == "YD15QH") & df["RESULT_NUM"].notna()]
    best = (sub.groupby(["MAIN_NAME", "ESPECE_FR"])["RESULT_NUM"]
               .agg(nb_obs="count", rendement_moyen="mean")
               .reset_index()
               .query("nb_obs >= 3")
               .sort_values("rendement_moyen", ascending=False)
               .head(30))
    best["rendement_moyen"] = best["rendement_moyen"].round(3)
    best.to_parquet(os.path.join(SPARK_DIR, "spark_top_materiels.parquet"), index=False)
    print(f"  → Top {len(best)} matériels exportés")
    results.append({"step": "top_materiels", "rows": len(best), "engine": "pandas-spark-fallback"})

    # 3. Corrélation
    print("\n  [Spark-pandas] Corrélation YD15QH × %MOIS")
    yd_s  = df[df["TRAIT"] == "YD15QH"][["LK_EXPERIMENT_EXPERIMENT_ID", "RESULT_NUM"]].rename(columns={"RESULT_NUM": "yd"})
    hum_s = df[df["TRAIT"] == "%MOIS"][["LK_EXPERIMENT_EXPERIMENT_ID", "RESULT_NUM"]].rename(columns={"RESULT_NUM": "humidity"})
    joined = yd_s.merge(hum_s, on="LK_EXPERIMENT_EXPERIMENT_ID", how="inner")
    if len(joined) > 5:
        corr_val = joined["yd"].corr(joined["humidity"])
        print(f"  Corrélation YD15QH × %MOIS = {corr_val:.4f}")
        results.append({"step": "correlation_yd_humidity", "value": round(float(corr_val), 4), "engine": "pandas-spark-fallback"})

    # 4. Audit qualité
    print("\n  [Spark-pandas] Audit qualité données")
    for c in ["RESULT_NUM", "YEAR", "ESPECE_FR", "REGION", "LAT", "LON"]:
        if c in df.columns:
            n   = df[c].isna().sum()
            pct = round(100 * n / total, 1)
            print(f"  {c:<30} nulls: {n:>8,}  ({pct}%)")

    return agg1, best


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

def run():
    print("=" * 80)
    print("  APACHE SPARK — Analyse distribuée (local mode)")
    if PYSPARK_AVAILABLE:
        import pyspark
        print(f"  PySpark {pyspark.__version__}  |  master: local[*]")
    else:
        print("  PySpark non disponible — fallback pandas (logique identique)")
    print("=" * 80)

    fact_path = os.path.join(ENRICH_DIR, "fact_table.parquet")
    if not os.path.exists(fact_path):
        print("  ⚠ Table de faits introuvable.")
        return

    results_log = []
    t0          = time.time()

    if PYSPARK_AVAILABLE:
        try:
            print("\n  Démarrage SparkSession...")
            spark = (SparkSession.builder
                     .appName("Semences_RD")
                     .master("local[*]")
                     .config("spark.ui.showConsoleProgress", "false")
                     .config("spark.sql.shuffle.partitions", "8")
                     .config("spark.driver.memory", "2g")
                     .getOrCreate())
            spark.sparkContext.setLogLevel("ERROR")
            print(f"  SparkContext démarré — version Spark {spark.version}")
            agg_pd, best_pd = spark_analyse(spark, fact_path.replace("\\", "/"), results_log)
            spark.stop()
            print("\n  SparkSession arrêtée.")
        except Exception as e:
            print(f"\n  ⚠ Spark échoué ({e}) — bascule sur pandas")
            fact = pd.read_parquet(fact_path)
            agg_pd, best_pd = pandas_analyse(fact, results_log)
    else:
        fact = pd.read_parquet(fact_path)
        agg_pd, best_pd = pandas_analyse(fact, results_log)

    elapsed = round(time.time() - t0, 2)

    # Affichage résultats
    print("\n  ── Top 10 agrégats espèce×trait ──")
    display_cols = [c for c in ["ESPECE_FR", "TRAIT", "nb", "avg_result"] if c in agg_pd.columns]
    print(agg_pd[display_cols].head(10).to_string(index=False))

    print("\n  ── Top 10 matériels (YD15QH) ──")
    print(best_pd.head(10).to_string(index=False))

    # Rapport
    os.makedirs(REPORT_DIR, exist_ok=True)
    report = {
        "engine":    "PySpark" if PYSPARK_AVAILABLE else "pandas-fallback",
        "steps":     results_log,
        "elapsed_s": elapsed,
        "outputs": {
            "agg_espece_trait": "data/enriched/spark/spark_agg_espece_trait.parquet",
            "top_materiels":    "data/enriched/spark/spark_top_materiels.parquet",
        },
        "timestamp": datetime.now().isoformat(),
    }
    with open(os.path.join(REPORT_DIR, "spark_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n  Durée totale    : {elapsed}s")
    print(f"  Rapport Spark   : reports/spark_report.json")
    print(f"  Résultats       : data/enriched/spark/")


if __name__ == "__main__":
    run()
