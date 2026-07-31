"""Build a local metadata catalog and a searchable FTS index."""

import json
import os
import sqlite3
from datetime import datetime

import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG_DIR = os.path.join(BASE_DIR, "catalog")
DB_PATH = os.path.join(CATALOG_DIR, "semences_catalog.db")
REPORT_DIR = os.path.join(BASE_DIR, "reports")

DATASETS = {
    "essai": ("data/raw/essai.parquet", "Essais culturaux et géolocalisation", "R&D essais"),
    "resultats": ("data/raw/resultats.parquet", "Mesures agronomiques par essai", "R&D mesures"),
    "materiel": ("data/raw/materiel.parquet", "Matériels génétiques et pedigrees", "R&D génétique"),
    "parcelle": ("data/raw/parcelle.parquet", "Parcelles, réplications et entrées", "R&D essais"),
    "qualification": ("data/raw/qualification.parquet", "Qualification des essais", "Qualité"),
    "fact_table": ("data/enriched/fact_table.parquet", "Table de faits analytique", "Data Office"),
}


def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def search(query, limit=25):
    with connect() as con:
        return [dict(row) for row in con.execute(
            "SELECT entity_type, entity_id, title, description "
            "FROM search_index WHERE search_index MATCH ? LIMIT ?",
            (query, limit),
        )]


def run():
    print("=" * 80)
    print("  CATALOGUE, METADONNEES ET MOTEUR DE RECHERCHE")
    print("=" * 80)
    os.makedirs(CATALOG_DIR, exist_ok=True)
    os.makedirs(REPORT_DIR, exist_ok=True)
    with connect() as con:
        con.executescript("""
        DROP TABLE IF EXISTS datasets;
        DROP TABLE IF EXISTS columns_catalog;
        DROP TABLE IF EXISTS lineage;
        DROP TABLE IF EXISTS search_index;
        CREATE TABLE datasets (
          name TEXT PRIMARY KEY, path TEXT, description TEXT, owner TEXT,
          layer TEXT, format TEXT, row_count INTEGER, column_count INTEGER,
          updated_at TEXT
        );
        CREATE TABLE columns_catalog (
          dataset TEXT, column_name TEXT, data_type TEXT, nullable INTEGER,
          null_rate REAL, distinct_count INTEGER,
          PRIMARY KEY(dataset, column_name)
        );
        CREATE TABLE lineage (source TEXT, target TEXT, transformation TEXT);
        CREATE VIRTUAL TABLE search_index USING fts5(
          entity_type, entity_id UNINDEXED, title, description
        );
        """)
        now = datetime.now().isoformat()
        for name, (rel_path, description, owner) in DATASETS.items():
            path = os.path.join(BASE_DIR, *rel_path.split("/"))
            df = pd.read_parquet(path)
            layer = rel_path.split("/")[1]
            con.execute("INSERT INTO datasets VALUES (?,?,?,?,?,?,?,?,?)", (
                name, rel_path, description, owner, layer, "parquet",
                len(df), len(df.columns), now,
            ))
            for column in df.columns:
                con.execute("INSERT INTO columns_catalog VALUES (?,?,?,?,?,?)", (
                    name, column, str(df[column].dtype), int(df[column].isna().any()),
                    round(float(df[column].isna().mean()), 6), int(df[column].nunique(dropna=True)),
                ))
            con.execute("INSERT INTO search_index VALUES (?,?,?,?)",
                        ("dataset", name, name, description))

        fact = pd.read_parquet(os.path.join(BASE_DIR, "data", "enriched", "fact_table.parquet"))
        materials = fact[["LK_STOCK_S1_DATA_ID", "MAIN_NAME", "PEDIGREE", "ESPECE_FR"]].dropna(
            subset=["LK_STOCK_S1_DATA_ID"]
        ).drop_duplicates("LK_STOCK_S1_DATA_ID").head(50000)
        con.executemany("INSERT INTO search_index VALUES (?,?,?,?)", [
            ("materiel", str(r.LK_STOCK_S1_DATA_ID), str(r.MAIN_NAME),
             f"{r.ESPECE_FR} {r.PEDIGREE}")
            for r in materials.itertuples(index=False)
        ])
        con.executemany("INSERT INTO lineage VALUES (?,?,?)", [
            ("CSV/*", "data/raw/*", "Sqoop import et conversion Parquet"),
            ("data/raw/*", "data/transformed/*", "NiFi validation et normalisation"),
            ("data/transformed/*", "data/enriched/fact_table", "ETL jointures et enrichissement"),
            ("data/enriched/fact_table", "data/exposed/yield_predictions", "Modèle prédictif"),
            ("data/enriched/fact_table", "reports/dashboard.html", "Analyses et restitution"),
        ])

    example = search("Blé")
    report = {
        "status": "OK", "database": "catalog/semences_catalog.db",
        "datasets": len(DATASETS), "indexed_materials": int(len(materials)),
        "example_query": "Blé", "example_results": len(example),
        "timestamp": datetime.now().isoformat(),
    }
    with open(os.path.join(REPORT_DIR, "catalog_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"  {len(DATASETS)} jeux de données catalogués")
    print(f"  {len(materials):,} matériels indexés; recherche FTS opérationnelle")
    return report


if __name__ == "__main__":
    run()
