"""
Apache NiFi — Simulation d'orchestration des flux de données
=============================================================
NiFi orchestre les pipelines de données via des "processors" chaînés.
Chaque processor exécute une transformation/validation/routage.

Architecture du flow NiFi simulé :
  [GetFile] → [ValidateRecord] → [RouteOnAttribute] → [TransformRecord]
           → [PutHDFS raw] → [ConvertAvroToParquet] → [UpdateAttribute]
           → [PutHDFS enriched] → [LogMessage]
"""

import os
import json
import pandas as pd
import numpy as np
from datetime import datetime
from collections import defaultdict

BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR    = os.path.join(BASE_DIR, "data", "raw")
TRANS_DIR  = os.path.join(BASE_DIR, "data", "transformed")
REPORT_DIR = os.path.join(BASE_DIR, "reports")


# ─────────────────────────────────────────────────────────────
# Modèle NiFi : Processor abstrait
# ─────────────────────────────────────────────────────────────

class NiFiProcessor:
    """Processor NiFi de base."""
    def __init__(self, name: str, processor_type: str):
        self.name           = name
        self.processor_type = processor_type
        self.uuid           = f"proc-{abs(hash(name)):08x}"
        self.input_count    = 0
        self.success_count  = 0
        self.failure_count  = 0
        self.relationships  = ["success", "failure"]
        self._start         = None

    def process(self, flowfile: dict) -> tuple[str, dict]:
        """Retourne (relationship, updated_flowfile)."""
        raise NotImplementedError

    def run(self, flowfile: dict) -> tuple[str, dict]:
        self._start = datetime.now()
        self.input_count += 1
        rel, ff = self.process(flowfile)
        if rel == "success":
            self.success_count += 1
        else:
            self.failure_count += 1
        elapsed = (datetime.now() - self._start).total_seconds() * 1000
        return rel, ff

    def stats(self) -> dict:
        return {
            "uuid":   self.uuid,
            "name":   self.name,
            "type":   self.processor_type,
            "in":     self.input_count,
            "ok":     self.success_count,
            "err":    self.failure_count,
        }


class GetFileProcessor(NiFiProcessor):
    """Lit un fichier Parquet depuis le raw layer (simule GetFile/GetHDFS)."""
    def __init__(self, table: str):
        super().__init__(f"GetFile_{table}", "org.apache.nifi.processors.standard.GetFile")
        self.table = table

    def process(self, flowfile: dict) -> tuple[str, dict]:
        path = os.path.join(RAW_DIR, f"{self.table}.parquet")
        if not os.path.exists(path):
            return "failure", {**flowfile, "error": f"File not found: {path}"}
        df = pd.read_parquet(path)
        flowfile["content"]    = df
        flowfile["attributes"] = {
            **flowfile.get("attributes", {}),
            "filename":        f"{self.table}.parquet",
            "table.name":      self.table,
            "record.count":    str(len(df)),
            "file.size.bytes": str(os.path.getsize(path)),
            "mime.type":       "application/parquet",
        }
        return "success", flowfile


class ValidateRecordProcessor(NiFiProcessor):
    """Valide les enregistrements (nulls, types, plages)."""
    def __init__(self, table: str, required_cols: list):
        super().__init__(f"ValidateRecord_{table}", "org.apache.nifi.processors.standard.ValidateRecord")
        self.required_cols = required_cols

    def process(self, flowfile: dict) -> tuple[str, dict]:
        df: pd.DataFrame = flowfile["content"]
        issues = []
        missing = [c for c in self.required_cols if c not in df.columns]
        if missing:
            issues.append(f"Colonnes manquantes : {missing}")
        null_pcts = {c: round(df[c].isna().mean() * 100, 1)
                     for c in df.columns if df[c].isna().mean() > 0.95}
        if null_pcts:
            issues.append(f"Colonnes quasi-vides (>95%) : {list(null_pcts.keys())}")
        dups = int(df.duplicated().sum())
        flowfile["attributes"] = {
            **flowfile.get("attributes", {}),
            "validation.issues":    str(len(issues)),
            "validation.duplicate": str(dups),
            "validation.status":    "VALID" if not issues else "WARNING",
        }
        flowfile["validation"] = {"issues": issues, "duplicates": dups}
        return "success", flowfile


class RouteOnAttributeProcessor(NiFiProcessor):
    """Route le flux selon le type de table."""
    def __init__(self):
        super().__init__("RouteOnAttribute", "org.apache.nifi.processors.standard.RouteOnAttribute")
        self.relationships = ["essai", "resultats", "materiel", "parcelle", "reference", "unmatched"]

    def process(self, flowfile: dict) -> tuple[str, dict]:
        table = flowfile["attributes"].get("table.name", "")
        route_map = {
            "essai": "essai", "resultats": "resultats",
            "materiel": "materiel", "parcelle": "parcelle",
            "especes": "reference", "qualification": "reference",
        }
        rel = route_map.get(table, "unmatched")
        flowfile["attributes"]["route"] = rel
        return rel, flowfile


class TransformRecordProcessor(NiFiProcessor):
    """Applique des transformations légères (nettoyage colonnes, BOM, types)."""
    def __init__(self, table: str):
        super().__init__(f"TransformRecord_{table}", "org.apache.nifi.processors.record.TransformRecord")
        self.table = table

    def process(self, flowfile: dict) -> tuple[str, dict]:
        df: pd.DataFrame = flowfile["content"].copy()
        # Nettoyer noms de colonnes
        df.columns = [c.strip().upper() for c in df.columns]
        # Remplacer chaînes vides par NaN
        df.replace("", np.nan, inplace=True)
        # Convertir numériques évidents
        before_types = str(df.dtypes.to_dict())
        for col in df.select_dtypes(include="object").columns:
            converted = pd.to_numeric(df[col].astype(str).str.replace(",", ".", regex=False),
                                      errors="coerce")
            if converted.notna().sum() / max(len(df), 1) > 0.6:
                df[col] = converted
        flowfile["content"] = df
        flowfile["attributes"]["transform.applied"] = "true"
        flowfile["attributes"]["transform.rows"]    = str(len(df))
        return "success", flowfile


class PutHDFSProcessor(NiFiProcessor):
    """Écrit le FlowFile dans HDFS (notre couche Parquet locale)."""
    def __init__(self, layer: str, target_dir: str):
        super().__init__(f"PutHDFS_{layer}", "org.apache.nifi.processors.hadoop.PutHDFS")
        self.target_dir = target_dir
        self.layer = layer

    def process(self, flowfile: dict) -> tuple[str, dict]:
        df: pd.DataFrame = flowfile["content"]
        table = flowfile["attributes"].get("table.name", "unknown")
        os.makedirs(self.target_dir, exist_ok=True)
        out_path = os.path.join(self.target_dir, f"{table}_nifi.parquet")
        df.to_parquet(out_path, index=False)
        flowfile["attributes"]["hdfs.path"]     = os.path.relpath(out_path, BASE_DIR).replace(os.sep, "/")
        flowfile["attributes"]["hdfs.layer"]    = self.layer
        flowfile["attributes"]["output.size"]   = str(os.path.getsize(out_path))
        return "success", flowfile


class LogMessageProcessor(NiFiProcessor):
    """Log les attributs du FlowFile (audit trail)."""
    def __init__(self):
        super().__init__("LogMessage", "org.apache.nifi.processors.standard.LogMessage")

    def process(self, flowfile: dict) -> tuple[str, dict]:
        attrs = flowfile.get("attributes", {})
        table    = attrs.get("table.name", "?")
        count    = attrs.get("record.count", "?")
        status   = attrs.get("validation.status", "?")
        hdfs_out = attrs.get("hdfs.path", "?")
        print(f"  [NiFi LOG] {table:<15} | {count:>8} records | {status:<8} | → {hdfs_out}")
        flowfile["attributes"]["log.timestamp"] = datetime.now().isoformat()
        return "success", flowfile


# ─────────────────────────────────────────────────────────────
# Pipeline NiFi complet
# ─────────────────────────────────────────────────────────────

class NiFiPipeline:
    """Exécute une chaîne de processors NiFi sur une table."""

    REQUIRED_COLS = {
        "essai":        ["LK_EXPERIMENT_EXPERIMENT_ID", "SPECIES", "YEAR"],
        "resultats":    ["LK_EXPERIMENT_EXPERIMENT_ID", "TRAIT", "RESULT"],
        "materiel":     ["LK_STOCK_S1_DATA_ID", "MAIN_NAME"],
        "parcelle":     ["LK_EXPERIMENT_EXPERIMENT_ID", "LK_STOCK_S1_DATA_ID"],
        "especes":      ["SPECIES_ID"],
        "qualification":["SL_TRIAL", "QUALIFICATION"],
    }

    def __init__(self, table: str):
        self.table = table
        req = self.REQUIRED_COLS.get(table, [])
        self.processors = [
            GetFileProcessor(table),
            ValidateRecordProcessor(table, req),
            RouteOnAttributeProcessor(),
            TransformRecordProcessor(table),
            PutHDFSProcessor("transformed", TRANS_DIR),
            LogMessageProcessor(),
        ]
        self.provenance = []

    def execute(self) -> dict:
        flowfile = {
            "uuid":       f"ff-{abs(hash(self.table)):016x}",
            "content":    None,
            "attributes": {},
        }
        for proc in self.processors:
            rel, flowfile = proc.run(flowfile)
            self.provenance.append({
                "processor": proc.name,
                "relationship": rel,
                "timestamp": datetime.now().isoformat(),
            })
            if rel == "failure":
                print(f"  [NiFi ERROR] {proc.name} → failure: {flowfile.get('error', '?')}")
                break
        return flowfile


def run():
    print("=" * 80)
    print("  APACHE NiFi — Orchestration des flux de données")
    print("  Flow : GetFile → Validate → Route → Transform → PutHDFS → Log")
    print("=" * 80)

    all_stats = []
    tables = ["essai", "resultats", "materiel", "parcelle", "especes", "qualification"]

    for table in tables:
        print(f"\n  ► Flow '{table}'")
        pipeline = NiFiPipeline(table)
        ff = pipeline.execute()
        attrs = ff.get("attributes", {})
        proc_stats = [p.stats() for p in pipeline.processors]
        all_stats.append({
            "table":      table,
            "processors": proc_stats,
            "provenance": pipeline.provenance,
            "final_attrs": attrs,
        })

    # Rapport provenance
    os.makedirs(REPORT_DIR, exist_ok=True)
    with open(os.path.join(REPORT_DIR, "nifi_provenance.json"), "w", encoding="utf-8") as f:
        json.dump(all_stats, f, ensure_ascii=False, indent=2)

    print("\n" + "─" * 80)
    print("  Résumé NiFi :")
    for entry in all_stats:
        procs = entry["processors"]
        total_ok = sum(p["ok"] for p in procs)
        print(f"    {entry['table']:<15} {len(procs)} processors  {total_ok} succès")
    print(f"\n  Provenance NiFi exportée : reports/nifi_provenance.json")
    print(f"  Données transformées     : data/transformed/*_nifi.parquet")
    print("─" * 80)


if __name__ == "__main__":
    run()
