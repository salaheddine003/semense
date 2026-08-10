"""
Apache Sqoop — Simulation d'import de données
=============================================
Sqoop transfère des données depuis des systèmes relationnels (RDBMS) vers HDFS.
Ici : CSV (= tables SQL sources) → HDFS Raw Layer (Parquet).

Commande Sqoop équivalente :
  sqoop import \
    --connect jdbc:mysql://semences-db:3306/rd_semences \
    --table ESSAI \
    --target-dir hdfs://namenode:9000/user/semences/raw/ \
    --as-parquetfile \
    --num-mappers 4 \
    --compress \
    --compression-codec snappy
"""

import os
import json
import pandas as pd
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_DIR   = os.path.join(BASE_DIR, "CSV")
RAW_DIR   = os.path.join(BASE_DIR, "data", "raw")
REPORT_DIR = os.path.join(BASE_DIR, "reports")

FILES = {
    "essai":        "ESSAI.csv",
    "materiel":     "LK_CRISP_MATERIAL_20190108.csv",
    "parcelle":     "PARCELLE_SPECIFICATION_20190108.csv",
    "especes":      "REF_ESPECES_20190108.csv",
    "resultats":    "RESULTAT_ESSAIS.csv",
    "qualification":"TRIAL_QUALIFICATION_20190108.csv",
}

HDFS_ROOT = "hdfs://namenode:9000/user/semences"


class SqoopJob:
    """Simule un job Apache Sqoop import avec output fidèle au vrai Sqoop."""

    def __init__(self, table: str, source_csv: str, hdfs_target: str, num_mappers: int = 4):
        self.table        = table
        self.source_csv   = source_csv
        self.hdfs_target  = hdfs_target
        self.num_mappers  = num_mappers
        self.rows         = 0
        self.status       = "PENDING"
        self.start        = None
        self.end          = None

    def print_sqoop_cmd(self):
        print(f"""
  $ sqoop import \\
      --connect 'jdbc:mysql://semences-db:3306/rd_semences' \\
      --username rd_user --password **** \\
      --table {self.table.upper()} \\
      --target-dir {self.hdfs_target} \\
      --as-parquetfile \\
      --num-mappers {self.num_mappers} \\
      --compress --compression-codec snappy""")

    def execute(self):
        self.print_sqoop_cmd()
        self.start  = datetime.now()
        self.status = "RUNNING"
        df = pd.read_csv(
            self.source_csv, sep=";", encoding="utf-8",
            encoding_errors="replace", low_memory=False
        )
        df.columns = [c.lstrip("\ufeff").strip() for c in df.columns]
        os.makedirs(RAW_DIR, exist_ok=True)
        out = os.path.join(RAW_DIR, f"{self.table}.parquet")
        df.to_parquet(out, index=False)
        self.rows   = len(df)
        self.status = "SUCCESS"
        self.end    = datetime.now()
        elapsed = (self.end - self.start).total_seconds()
        nb_maps = min(self.num_mappers, self.rows)
        chunk   = self.rows // max(nb_maps, 1)
        print(f"  INFO mapreduce.Job: map 100%  reduce 0%")
        print(f"  INFO mapreduce.ImportJobBase: Retrieved {self.rows:,} records.")
        print(f"  INFO tool.ImportTool: Transferred {self.rows * 500 // 1024} KB in {elapsed:.3f}s "
              f"({self.rows * 500 / max(elapsed, 0.001) / 1024:.0f} KB/s)")
        print(f"  ✔  {self.table:<15} → {out}  [{self.rows:,} lignes, {elapsed:.2f}s]")
        return self

    def to_dict(self):
        return {
            "job_id":   f"sqoop_job_{self.table}_{self.start.strftime('%Y%m%d%H%M%S')}",
            "table":    self.table,
            "source":   os.path.relpath(self.source_csv, BASE_DIR).replace(os.sep, "/"),
            "hdfs_target": self.hdfs_target,
            "rows":     self.rows,
            "status":   self.status,
            "duration_s": round((self.end - self.start).total_seconds(), 3),
            "timestamp": self.start.isoformat(),
        }


def run():
    os.makedirs(REPORT_DIR, exist_ok=True)
    print("=" * 80)
    print("  APACHE SQOOP — Import RDBMS → HDFS (Raw Parquet Layer)")
    print(f"  HDFS Target Root : {HDFS_ROOT}/raw/")
    print("=" * 80)

    logs = []
    total_rows = 0

    for name, filename in FILES.items():
        src = os.path.join(CSV_DIR, filename)
        hdfs_tgt = f"{HDFS_ROOT}/raw/{name}"
        job = SqoopJob(name, src, hdfs_tgt)
        job.execute()
        logs.append(job.to_dict())
        total_rows += job.rows

    print("\n" + "─" * 80)
    print(f"  Sqoop terminé : {len(logs)} tables importées | {total_rows:,} lignes | "
          f"Dest: data/raw/ (Parquet/Snappy)")
    print("─" * 80)

    with open(os.path.join(REPORT_DIR, "sqoop_jobs.json"), "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)
    print("  Logs sauvegardés : reports/sqoop_jobs.json")


if __name__ == "__main__":
    run()
