"""
Apache HBase — Stockage NoSQL (simulation SQLite)
=================================================
HBase est une base de données NoSQL orientée colonnes sur HDFS.
Structure : Table → Row Key → Column Families → Qualifiers → Values

Tables HBase créées :
  experiments  : CF info | CF geo | CF quality
  results      : CF measurement | CF metadata
  materials    : CF identity | CF genetics | CF taxonomy

Simulé avec SQLite en respectant la convention HBase :
  colonne = "cf:qualifier"
"""

import os
import sqlite3
import json
import pandas as pd
from datetime import datetime

BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENRICH_DIR = os.path.join(BASE_DIR, "data", "enriched")
HBASE_DIR  = os.path.join(BASE_DIR, "hbase")
REPORT_DIR = os.path.join(BASE_DIR, "reports")
DB_PATH    = os.path.join(HBASE_DIR, "semences_hbase.db")


def get_con() -> sqlite3.Connection:
    os.makedirs(HBASE_DIR, exist_ok=True)
    return sqlite3.connect(DB_PATH)


# ─────────────────────────────────────────────────────────────
# Création des tables (équivalent HBase DDL)
# ─────────────────────────────────────────────────────────────

DDL = {
    "experiments": """
        CREATE TABLE IF NOT EXISTS experiments (
            row_key             TEXT PRIMARY KEY,  -- YEAR#EXPERIMENT_ID
            "info:species"      TEXT,
            "info:espece_fr"    TEXT,
            "info:year"         INTEGER,
            "info:sl_trial"     TEXT,
            "info:responsibility" TEXT,
            "info:culture_unit" TEXT,
            "geo:region"        TEXT,
            "geo:department"    TEXT,
            "geo:lat"           REAL,
            "geo:lon"           REAL,
            "quality:fiab_exp"  REAL,
            "quality:fiab_breed" REAL,
            "meta:insert_ts"    TEXT
        )
    """,
    "results": """
        CREATE TABLE IF NOT EXISTS results (
            row_key                    TEXT PRIMARY KEY,  -- EXP_ID#SL_TRIAL#ENTRY#TRAIT
            "measurement:value"        REAL,
            "measurement:raw_value"    TEXT,
            "measurement:trait"        TEXT,
            "measurement:unit"         TEXT,
            "metadata:year"            INTEGER,
            "metadata:replication_num" INTEGER,
            "metadata:entry_num"       INTEGER,
            "metadata:transfer_appy"   INTEGER,
            "meta:insert_ts"           TEXT
        )
    """,
    "materials": """
        CREATE TABLE IF NOT EXISTS materials (
            row_key              TEXT PRIMARY KEY,  -- LK_STOCK_S1_DATA_ID
            "identity:main_name" TEXT,
            "identity:pedigree"  TEXT,
            "identity:structure" TEXT,
            "genetics:p1"        TEXT,
            "genetics:p2"        TEXT,
            "genetics:self_nb"   INTEGER,
            "genetics:next_stage" TEXT,
            "taxonomy:species"   TEXT,
            "taxonomy:espece_fr" TEXT,
            "taxonomy:responsibility" TEXT,
            "meta:insert_ts"     TEXT
        )
    """,
}

HBASE_SHELL_CMDS = {
    "experiments": "create 'experiments', 'info', 'geo', 'quality', 'meta'",
    "results":     "create 'results', 'measurement', 'metadata', 'meta'",
    "materials":   "create 'materials', 'identity', 'genetics', 'taxonomy', 'meta'",
}


def create_tables(con: sqlite3.Connection):
    print("\n  HBase Shell :")
    for tbl, cmd in HBASE_SHELL_CMDS.items():
        print(f"    hbase> {cmd}")
    cur = con.cursor()
    # Rebuild the local adaptation so counts cannot include stale rows.
    for table in DDL:
        cur.execute(f'DROP TABLE IF EXISTS "{table}"')
    for stmt in DDL.values():
        cur.execute(stmt)
    con.commit()
    print("  Tables created. => OK")


# ─────────────────────────────────────────────────────────────
# Chargement des données
# ─────────────────────────────────────────────────────────────

ESPECES_FR = {
    "C": "Colza", "O": "Colza", "S": "Soja", "W": "Blé tendre",
    "T": "Triticale", "B": "Blé dur/Orge", "M": "Maïs",
}


def load_experiments(con: sqlite3.Connection, fact: pd.DataFrame):
    print("\n  hbase> put 'experiments' ...")
    essais_u = fact.drop_duplicates("LK_EXPERIMENT_EXPERIMENT_ID")
    ts = datetime.now().isoformat()
    rows = []
    for _, r in essais_u.iterrows():
        rk = f"{r.get('YEAR', 0)}#{r['LK_EXPERIMENT_EXPERIMENT_ID']}"
        rows.append((
            rk,
            str(r.get("SPECIES", "")),
            str(r.get("ESPECE_FR", "")),
            int(r["YEAR"]) if pd.notna(r.get("YEAR")) else None,
            str(r.get("SL_TRIAL", "")),
            str(r.get("RESPONSIBILITY", "")),
            str(r.get("CULTURE_UNIT", "")),
            str(r.get("REGION", "")),
            str(r.get("DEPARTMENT", "")),
            float(r["LAT"]) if pd.notna(r.get("LAT")) else None,
            float(r["LON"]) if pd.notna(r.get("LON")) else None,
            float(r["FIABILITY_EXPERIMENTAL"]) if pd.notna(r.get("FIABILITY_EXPERIMENTAL")) else None,
            float(r["FIABILITY_BREEDER"]) if pd.notna(r.get("FIABILITY_BREEDER")) else None,
            ts,
        ))
    con.executemany(
        """INSERT OR REPLACE INTO experiments VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        rows
    )
    con.commit()
    print(f"  ✔  experiments : {len(rows):,} rows written")
    return len(rows)


def load_results(con: sqlite3.Connection, fact: pd.DataFrame):
    print("\n  hbase> put 'results' ...")
    ts   = datetime.now().isoformat()
    rows = []
    rejected = 0
    sample = fact[fact["RESULT_NUM"].notna()].head(50000)
    for source_index, r in sample.iterrows():
        if pd.isna(r.get("LK_EXPERIMENT_EXPERIMENT_ID")) or pd.isna(r.get("TRAIT")):
            rejected += 1
            continue
        source_id = r.get("LK_SL_TRIAL_L2_DATA_ID", source_index)
        source_id = source_index if pd.isna(source_id) else source_id
        rk = (f"{source_id}#"
              f"{r['LK_EXPERIMENT_EXPERIMENT_ID']}#"
              f"{r.get('SL_TRIAL', '')}#"
              f"{r.get('REPLICATION_NUM', '')}#"
              f"{r.get('ENTRY_NUM', 0)}#"
              f"{r.get('TRAIT', '')}")
        rows.append((
            rk,
            float(r["RESULT_NUM"]),
            str(r.get("RESULT", "")),
            str(r.get("TRAIT", "")),
            "",  # unit
            int(r["YEAR"]) if pd.notna(r.get("YEAR")) else None,
            int(r["REPLICATION_NUM"]) if pd.notna(r.get("REPLICATION_NUM")) else None,
            int(r["ENTRY_NUM"]) if pd.notna(r.get("ENTRY_NUM")) else None,
            int(r["TRANSFER_APPY"]) if pd.notna(r.get("TRANSFER_APPY")) else None,
            ts,
        ))
    keys = [row[0] for row in rows]
    collisions = len(keys) - len(set(keys))
    if collisions:
        raise ValueError(f"HBase results row-key collisions detected: {collisions}")
    con.executemany("""INSERT INTO results VALUES (?,?,?,?,?,?,?,?,?,?)""", rows)
    con.commit()
    actual = con.execute("SELECT COUNT(*) FROM results").fetchone()[0]
    if actual != len(rows):
        raise AssertionError(f"HBase results count mismatch: expected {len(rows)}, got {actual}")
    stats = {
        "received": int(len(sample)),
        "inserted": int(actual),
        "updated": 0,
        "rejected": int(rejected),
        "collisions": int(collisions),
    }
    print(f"  results : {actual:,} inserted | {rejected:,} rejected | {collisions:,} collisions")
    return stats


def load_materials(con: sqlite3.Connection):
    print("\n  hbase> put 'materials' ...")
    mat_p = os.path.join(BASE_DIR, "data", "transformed", "materiel.parquet")
    if not os.path.exists(mat_p):
        print("  Matériel non disponible, ignoré.")
        return 0
    mat = pd.read_parquet(mat_p)
    codes = mat["SPECIES"].fillna("").astype(str).str.strip().str.upper()
    mat["ESPECE_FR"] = codes.map(ESPECES_FR).fillna("INCONNU_CODE_" + codes.replace("", "VIDE"))
    ts = datetime.now().isoformat()
    rows = []
    for _, r in mat.head(20000).iterrows():
        rows.append((
            str(r["LK_STOCK_S1_DATA_ID"]),
            str(r.get("MAIN_NAME", "")),
            str(r.get("PEDIGREE", "")),
            str(r.get("STRUCTURE", "")),
            str(r.get("P1", "")) if pd.notna(r.get("P1")) else None,
            str(r.get("P2", "")) if pd.notna(r.get("P2")) else None,
            int(r["SELF_NB"]) if pd.notna(r.get("SELF_NB")) else None,
            str(r.get("NEXT_STAGE", "")) if pd.notna(r.get("NEXT_STAGE")) else None,
            str(r.get("SPECIES", "")),
            str(r.get("ESPECE_FR", "")),
            str(r.get("RESPONSIBILITY", "")) if pd.notna(r.get("RESPONSIBILITY")) else None,
            ts,
        ))
    con.executemany(
        """INSERT OR REPLACE INTO materials VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        rows
    )
    con.commit()
    print(f"  ✔  materials : {len(rows):,} rows written")
    return len(rows)


# ─────────────────────────────────────────────────────────────
# Requêtes HBase (get / scan / filter)
# ─────────────────────────────────────────────────────────────

def hbase_scan_examples(con: sqlite3.Connection):
    print("\n  ── Requêtes HBase (scan / get) ──")
    cur = con.cursor()

    # scan experiments filtré par région
    print("\n  hbase> scan 'experiments', {FILTER => \"SingleColumnValueFilter('geo', 'region', =, 'binary:CENTRE')\"}")
    cur.execute("""
        SELECT row_key, "info:espece_fr", "info:year", "geo:region", "geo:lat", "geo:lon"
        FROM experiments
        WHERE "geo:region" = 'CENTRE'
        LIMIT 5
    """)
    rows = cur.fetchall()
    print(f"  {'ROW_KEY':<35} {'ESPECE':<15} {'YEAR':<6} {'REGION':<20} {'LAT':>8} {'LON':>8}")
    print("  " + "─" * 95)
    for r in rows:
        print(f"  {str(r[0]):<35} {str(r[1]):<15} {str(r[2]):<6} {str(r[3]):<20} {str(r[4]):>8} {str(r[5]):>8}")

    # get moy rendement par espèce
    print("\n  hbase> scan 'results' (aggregation rendement par espèce via co-processor)")
    cur.execute("""
        SELECT e."info:espece_fr", r."measurement:trait",
               COUNT(*) as N,
               ROUND(AVG(r."measurement:value"), 2) as avg_val,
               ROUND(MIN(r."measurement:value"), 2) as min_val,
               ROUND(MAX(r."measurement:value"), 2) as max_val
        FROM results r
        JOIN experiments e
          ON r.row_key LIKE e."info:year" || '#' || SUBSTR(r.row_key, 1, INSTR(r.row_key,'#')-1) || '#%'
             OR r.row_key LIKE '%' || SUBSTR(e.row_key, INSTR(e.row_key,'#')+1) || '#%'
        WHERE r."measurement:value" IS NOT NULL
          AND r."measurement:trait" IN ('YD15QH','YD16QH','%MOIS')
        GROUP BY 1, 2
        ORDER BY avg_val DESC
        LIMIT 10
    """)
    rows2 = cur.fetchall()
    if not rows2:
        # Simplified query without join complexity
        cur.execute("""
            SELECT "measurement:trait", COUNT(*), ROUND(AVG("measurement:value"),2),
                   ROUND(MIN("measurement:value"),2), ROUND(MAX("measurement:value"),2)
            FROM results
            WHERE "measurement:value" IS NOT NULL
              AND "measurement:trait" IN ('YD15QH','YD16QH','%MOIS')
            GROUP BY "measurement:trait"
        """)
        rows2 = cur.fetchall()
        print(f"  {'TRAIT':<12} {'N':>8} {'AVG':>10} {'MIN':>10} {'MAX':>10}")
        print("  " + "─" * 52)
        for r in rows2:
            print(f"  {str(r[0]):<12} {r[1]:>8,} {r[2]:>10} {r[3]:>10} {r[4]:>10}")


def run():
    print("=" * 80)
    print("  APACHE HBase — Stockage NoSQL Column-Family")
    print(f"  DB locale : {DB_PATH}")
    print("=" * 80)

    fact_path = os.path.join(ENRICH_DIR, "fact_table.parquet")
    if not os.path.exists(fact_path):
        print("  ⚠ Table de faits non disponible. Lancer 02_etl.py d'abord.")
        return

    fact = pd.read_parquet(fact_path)

    con = get_con()
    create_tables(con)

    n_exp = load_experiments(con, fact)
    result_stats = load_results(con, fact)
    n_mat = load_materials(con)

    hbase_scan_examples(con)
    con.close()

    # Résumé
    summary = {
        "db": DB_PATH,
        "tables": {
            "experiments": {"rows": n_exp, "column_families": ["info", "geo", "quality", "meta"]},
            "results":     {
                "rows": result_stats["inserted"],
                "load": result_stats,
                "row_key": "SOURCE_ROW_ID#EXPERIMENT_ID#SL_TRIAL#REPLICATION#ENTRY#TRAIT",
                "column_families": ["measurement", "metadata", "meta"],
            },
            "materials":   {"rows": n_mat, "column_families": ["identity", "genetics", "taxonomy", "meta"]},
        },
        "timestamp": datetime.now().isoformat(),
    }
    os.makedirs(REPORT_DIR, exist_ok=True)
    with open(os.path.join(REPORT_DIR, "hbase_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n  HBase : {n_exp:,} essais | {result_stats['inserted']:,} mesures | {n_mat:,} matériels")
    print(f"  DB SQLite : {DB_PATH}")
    print(f"  Rapport   : reports/hbase_summary.json")


if __name__ == "__main__":
    run()
