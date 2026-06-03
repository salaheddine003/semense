"""
main.py — Orchestrateur du projet Semences
Pipeline Big Data complet — 12 phases technologiques

Stack complète :
  Hadoop/HDFS · MapR/Cloudera/HortonWorks · Talend · Apache NiFi · Sqoop
  HBase · Cassandra/MapR-DB · Apache Kafka · MapR-Streams · Talend ESB
  Apache Drill · Apache Hive · R · Apache Spark · Spotfire · Tableau
"""

import os
import sys
import time
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR  = os.path.join(BASE_DIR, "src")
sys.path.insert(0, SRC_DIR)


PHASES = [
    # (num, label_court, module,            description)
    ( 1, "SQOOP",       "06_sqoop_import",   "Apache Sqoop    — Import CSV → HDFS (couche Raw)"),
    ( 2, "PROFILING",   "01_profiling",      "Gouvernance     — Qualité & Profiling des données"),
    ( 3, "NIFI",        "07_nifi_flow",      "Apache NiFi     — Orchestration des flux de données"),
    ( 4, "TALEND ETL",  "02_etl",            "Talend ETL      — Nettoyage, jointures, enrichissement"),
    ( 5, "HBASE",       "08_hbase_store",    "Apache HBase    — Stockage NoSQL (column families)"),
    ( 6, "KAFKA",       "09_kafka_streaming","Apache Kafka    — Bus de données / Streaming"),
    ( 7, "HIVE",        "10_hive_queries",   "Apache Hive     — Entrepôt analytique (HiveQL)"),
    ( 8, "SPARK",       "11_spark_analysis", "Apache Spark    — Calcul distribué (PySpark)"),
    ( 9, "DRILL",       "12_drill_queries",  "Apache Drill    — SQL ad-hoc sur fichiers (dfs)"),
    (10, "ANALYSE",     "03_analyse",        "Python + R      — Statistiques, ANOVA, corrélations"),
    (11, "VISU",        "04_visualisation",  "Tableau/Spotfire— Visualisations & Carte interactive"),
    (12, "DASHBOARD",   "05_dashboard",      "Reporting       — Dashboard HTML consolidé"),
]

TOTAL = len(PHASES)


def banner(phase: int, label: str, description: str):
    bar = "▓" * 72
    print(f"\n{bar}")
    print(f"  PHASE {phase:02d}/{TOTAL}  [{label}]")
    print(f"  {description}")
    print(f"{bar}\n")


def run_phase(phase_tuple: tuple) -> dict:
    num, label, module_name, description = phase_tuple
    banner(num, label, description)
    t0 = time.time()
    status = "OK"
    try:
        mod = __import__(module_name)
        if hasattr(mod, "run"):
            mod.run()
        else:
            print(f"  ⚠  Module {module_name} n'a pas de fonction run()")
        elapsed = round(time.time() - t0, 1)
        print(f"\n  ✔  Phase {num:02d} [{label}] terminée en {elapsed}s")
    except Exception as exc:
        elapsed = round(time.time() - t0, 1)
        status = f"ERREUR: {exc}"
        print(f"\n  ✘  Phase {num:02d} [{label}] — {exc}")
        import traceback
        traceback.print_exc()
    return {"phase": num, "label": label, "module": module_name,
            "elapsed_s": elapsed, "status": status}


def print_architecture():
    print("""
  ┌──────────────────────────────────────────────────────────────────────┐
  │           ARCHITECTURE BIG DATA — SEMENCES R&D                       │
  │                                                                        │
  │  [CSV Sources]                                                         │
  │       │                                                                │
  │       ▼                                                                │
  │  ┌─────────┐   ┌──────────┐   ┌───────────┐                          │
  │  │  Sqoop  │──▶│  HDFS    │──▶│   NiFi    │  (ingestion / routing)   │
  │  └─────────┘   │ (raw/)   │   └─────┬─────┘                          │
  │                └──────────┘         │                                  │
  │                                     ▼                                  │
  │                              ┌────────────┐                           │
  │                              │ Talend ETL │  (transform / enrich)     │
  │                              └─────┬──────┘                           │
  │                                    │                                   │
  │              ┌─────────────────────┼─────────────────────┐            │
  │              ▼                     ▼                       ▼           │
  │         ┌─────────┐         ┌──────────┐          ┌──────────┐       │
  │         │  HBase  │         │  Kafka   │          │   Hive   │       │
  │         │ (NoSQL) │         │(Streaming│          │  (HQL)   │       │
  │         └─────────┘         └──────────┘          └──────────┘       │
  │                                                                        │
  │         ┌─────────┐         ┌──────────┐                              │
  │         │  Spark  │         │  Drill   │  (SQL on files)              │
  │         │(PySpark)│         │ (ad-hoc) │                              │
  │         └─────────┘         └──────────┘                              │
  │                                    │                                   │
  │                                    ▼                                   │
  │                      ┌────────────────────────┐                       │
  │                      │  Dashboard HTML         │                      │
  │                      │  Tableau / Spotfire     │                      │
  │                      └────────────────────────┘                       │
  └──────────────────────────────────────────────────────────────────────┘
""")


def main():
    print("\n" + "╔" + "═" * 70 + "╗")
    print("║" + " " * 10 + "PROJET SEMENCES — PIPELINE BIG DATA COMPLET" + " " * 17 + "║")
    print("║" + " " * 8  + "Système d'Information Semencier — Pôle R&D (300+ experts)" + " " * 4 + "║")
    print("║" + " " * 12 + f"{TOTAL} phases technologiques  |  {datetime.now():%Y-%m-%d %H:%M}" + " " * 16 + "║")
    print("╚" + "═" * 70 + "╝")

    print_architecture()

    total_start = time.time()
    results     = []

    for phase_tuple in PHASES:
        r = run_phase(phase_tuple)
        results.append(r)

    total_elapsed = round(time.time() - total_start, 1)

    # ── Résumé final ──────────────────────────────────────────────────────
    print("\n" + "╔" + "═" * 70 + "╗")
    print("║" + " " * 18 + "RÉSUMÉ DU PIPELINE" + " " * 32 + "║")
    print("╠" + "═" * 70 + "╣")
    ok_count  = sum(1 for r in results if r["status"] == "OK")
    err_count = len(results) - ok_count
    for r in results:
        icon = "✔" if r["status"] == "OK" else "✘"
        phase_str = f"  Phase {r['phase']:02d}/{TOTAL}  [{r['label']:<12}]"
        time_str  = f"{r['elapsed_s']:>6}s"
        status_str = r['status'] if len(r['status']) <= 30 else r['status'][:27] + "..."
        line = f"║  {icon}  {phase_str}  {time_str}  {status_str}"
        print(line[:72].ljust(72) + "║")
    print("╠" + "═" * 70 + "╣")
    print(f"║  Phases réussies : {ok_count}/{TOTAL}   "
          f"Erreurs : {err_count}   "
          f"Durée totale : {total_elapsed}s".ljust(70) + "║")
    print("╚" + "═" * 70 + "╝")

    print("\n  Technologies utilisées :")
    tech_list = [
        "Hadoop/HDFS (data/raw, transformed, enriched)",
        "Apache Sqoop  (import CSV → HDFS Parquet)",
        "Apache NiFi   (orchestration flux, processor chain)",
        "Talend ETL    (nettoyage, jointures, fact table)",
        "Apache HBase  (NoSQL SQLite column-family simulation)",
        "Apache Kafka  (bus de données, producer/consumer)",
        "Apache Hive   (HiveQL analytique via DuckDB)",
        "Apache Spark  (PySpark local[*] ou pandas fallback)",
        "Apache Drill  (SQL on files, dfs workspace, DuckDB)",
        "R             (ANOVA, Tukey HSD, ggplot2)",
        "Tableau       (style export + visualisations)",
        "Spotfire      (dashboard HTML interactif)",
    ]
    for t in tech_list:
        print(f"  • {t}")

    print("\n  Fichiers produits :")
    outputs = [
        ("data/raw/",                    "6 fichiers Parquet (HDFS raw layer)"),
        ("data/transformed/",            "Tables nettoyées Parquet"),
        ("data/enriched/fact_table.*",   "136 K lignes × 47 colonnes"),
        ("data/enriched/spark/",         "Résultats Spark Parquet"),
        ("hbase/semences_hbase.db",      "Base HBase SQLite simulée"),
        ("kafka/",                       "Événements Kafka JSON/CSV"),
        ("hive/",                        "Résultats HiveQL CSV"),
        ("drill/",                       "Résultats Drill CSV"),
        ("reports/images/",              "Graphiques PNG (Python + R)"),
        ("reports/carte_essais.html",    "Carte géographique Folium"),
        ("reports/dashboard.html",       "Dashboard HTML complet"),
        ("reports/*_report.json",        "Rapports par technologie"),
    ]
    for path, desc in outputs:
        print(f"  • {path:<38} — {desc}")

    print()


if __name__ == "__main__":
    main()

