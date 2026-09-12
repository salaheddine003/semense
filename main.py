"""
main.py — Orchestrateur du projet Semences
Pipeline Big Data complet — 17 phases technologiques

Stack du prototype : Python/pandas, Parquet, SQLite, DuckDB, PySpark local,
Rscript, scikit-learn et dashboard HTML. Les technologies distribuées sont
représentées par des adaptations fonctionnelles locales documentées.
"""

import os
import sys
import time
import json
import argparse
import subprocess
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR  = os.path.join(BASE_DIR, "src")
sys.path.insert(0, SRC_DIR)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


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
    (11, "VISU",        "04_visualisation",  "Visualisation   — Graphiques locaux & carte Folium"),
    (12, "PREDICTION",  "13_prediction",     "Machine Learning— Prédiction rendement & métriques"),
    (13, "CATALOGUE",   "14_catalog_search", "Gouvernance     — Catalogue, lineage & recherche"),
    (14, "R",           "15_r_integration",  "R obligatoire   — ANOVA & statistiques via Rscript"),
    (15, "QUALITY",     "16_quality_gates",  "Qualité         — Contrats, doublons & quarantaine"),
    (16, "LIVRABLES",   "17_deliverables",   "Documentation   — Diagramme & présentation"),
    (17, "DASHBOARD",   "05_dashboard",      "Reporting       — Dashboard HTML consolidé"),
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
        if module_name == "11_spark_analysis":
            # Isolate the JVM and Spark signal handlers from later Python phases.
            subprocess.run(
                [sys.executable, "-X", "utf8", os.path.join(SRC_DIR, module_name + ".py")],
                cwd=BASE_DIR, check=True,
            )
        else:
            mod = __import__(module_name)
            if not callable(getattr(mod, "run", None)):
                raise RuntimeError(f"Module {module_name} sans fonction run()")
            mod.run()
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
  │                      │  Dashboard HTML local  │                      │
  │                      └────────────────────────┘                       │
  └──────────────────────────────────────────────────────────────────────┘
""")


def main():
    parser = argparse.ArgumentParser(description="Pipeline Big Data Semences")
    parser.add_argument(
        "--resume", action="store_true",
        help="ignorer les phases déjà réussies et reprendre au premier échec",
    )
    args = parser.parse_args()
    checkpoint_path = os.path.join(BASE_DIR, "reports", "pipeline_checkpoint.json")
    checkpoint = {"phases": {}}
    if args.resume and os.path.exists(checkpoint_path):
        with open(checkpoint_path, encoding="utf-8") as handle:
            checkpoint = json.load(handle)
    elif not args.resume:
        os.makedirs(os.path.dirname(checkpoint_path), exist_ok=True)
        with open(checkpoint_path, "w", encoding="utf-8") as handle:
            json.dump(checkpoint, handle, ensure_ascii=False, indent=2)

    print("\n" + "╔" + "═" * 70 + "╗")
    print("║" + " " * 10 + "PROJET SEMENCES — PIPELINE BIG DATA COMPLET" + " " * 17 + "║")
    print("║" + " " * 8  + "Système d'Information Semencier — Pôle R&D (300+ experts)" + " " * 4 + "║")
    print("║" + " " * 12 + f"{TOTAL} phases technologiques  |  {datetime.now():%Y-%m-%d %H:%M}" + " " * 16 + "║")
    print("╚" + "═" * 70 + "╝")

    print_architecture()

    total_start = time.time()
    results     = []

    for phase_tuple in PHASES:
        num, label, module_name, _ = phase_tuple
        previous = checkpoint.get("phases", {}).get(str(num), {})
        if args.resume and previous.get("status") == "OK" and previous.get("module") == module_name:
            print(f"\n  ↷  Phase {num:02d}/{TOTAL} [{label}] déjà réussie — checkpoint")
            r = {
                "phase": num, "label": label, "module": module_name,
                "elapsed_s": 0.0, "status": "OK", "resumed": True,
            }
        else:
            r = run_phase(phase_tuple)
        results.append(r)
        if r["status"] == "OK":
            checkpoint.setdefault("phases", {})[str(num)] = r
            checkpoint["updated_at"] = datetime.now().isoformat()
            checkpoint["pipeline_total"] = TOTAL
            os.makedirs(os.path.dirname(checkpoint_path), exist_ok=True)
            with open(checkpoint_path, "w", encoding="utf-8") as handle:
                json.dump(checkpoint, handle, ensure_ascii=False, indent=2)
        else:
            break

    total_elapsed = round(time.time() - total_start, 1)

    # Persist technical monitoring for the administration API and run history.
    run_report = {
        "started_at": datetime.fromtimestamp(total_start).isoformat(),
        "finished_at": datetime.now().isoformat(),
        "elapsed_s": total_elapsed,
        "status": "OK" if all(r["status"] == "OK" for r in results) else "ERROR",
        "phases": results,
    }
    report_dir = os.path.join(BASE_DIR, "reports")
    os.makedirs(report_dir, exist_ok=True)
    run_filename = "pipeline_resume_run.json" if args.resume else "pipeline_run.json"
    with open(os.path.join(report_dir, run_filename), "w", encoding="utf-8") as f:
        json.dump(run_report, f, ensure_ascii=False, indent=2)
    with open(os.path.join(report_dir, "pipeline_history.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(run_report, ensure_ascii=False) + "\n")

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
        "HDFS          (adaptation locale: data/raw, transformed, enriched)",
        "Apache Sqoop  (adaptation locale CSV vers Parquet)",
        "Apache NiFi   (adaptation locale de chaîne de processeurs)",
        "Talend ETL    (adaptation locale avec pandas)",
        "Apache HBase  (adaptation locale SQLite column-family)",
        "Apache Kafka  (adaptation locale queue producer/consumer)",
        "Apache Hive   (adaptation locale HiveQL via DuckDB)",
        "Apache Spark  (PySpark local[*] ou pandas fallback)",
        "Apache Drill  (adaptation locale SQL sur fichiers via DuckDB)",
        "R             (ANOVA, Tukey HSD, ggplot2)",
        "Dashboard HTML local (BI entreprise: cible optionnelle)",
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

    summary_lines = [
        "SEMENCES - RESULTAT DU DERNIER PIPELINE COMPLET",
        f"Statut: {run_report['status']}",
        f"Phases executees: {len(results)}/{TOTAL}",
        f"Phases reussies: {ok_count}/{TOTAL}",
        f"Duree: {total_elapsed} secondes",
        f"Debut: {run_report['started_at']}",
        f"Fin: {run_report['finished_at']}",
    ]
    if not args.resume:
        with open(os.path.join(BASE_DIR, "pipeline_output.txt"), "w", encoding="utf-8") as handle:
            handle.write("\n".join(summary_lines) + "\n")

    print()
    return 0 if run_report["status"] == "OK" and len(results) == TOTAL else 1


if __name__ == "__main__":
    raise SystemExit(main())

