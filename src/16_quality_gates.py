"""Cross-source data quality gates with explicit quarantine outputs."""

import json
import os
from datetime import datetime

import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
QUARANTINE_DIR = os.path.join(BASE_DIR, "data", "quarantine")
REPORT_DIR = os.path.join(BASE_DIR, "reports")

CONTRACTS = {
    "essai": {
        "required_columns": ["LK_EXPERIMENT_EXPERIMENT_ID", "YEAR", "SPECIES"],
        "not_null": ["LK_EXPERIMENT_EXPERIMENT_ID", "YEAR"],
        "unique_key": ["LK_EXPERIMENT_EXPERIMENT_ID"],
    },
    "resultats": {
        "required_columns": [
            "LK_EXPERIMENT_EXPERIMENT_ID", "YEAR", "SPECIES", "TRAIT", "RESULT"
        ],
        "not_null": ["LK_EXPERIMENT_EXPERIMENT_ID", "YEAR", "TRAIT", "RESULT"],
        "unique_key": [
            "LK_SL_TRIAL_L2_DATA_ID", "TRAIT",
        ],
    },
    "materiel": {
        "required_columns": ["LK_STOCK_S1_DATA_ID", "SPECIES", "MAIN_NAME"],
        "not_null": ["LK_STOCK_S1_DATA_ID", "SPECIES"],
        "unique_key": ["LK_STOCK_S1_DATA_ID"],
    },
    "parcelle": {
        "required_columns": [
            "LK_SL_TRIAL_L4_DATA_ID", "LK_EXPERIMENT_EXPERIMENT_ID",
            "LK_STOCK_S1_DATA_ID",
        ],
        "not_null": ["LK_SL_TRIAL_L4_DATA_ID", "LK_EXPERIMENT_EXPERIMENT_ID"],
        "unique_key": ["LK_SL_TRIAL_L4_DATA_ID"],
    },
    "especes": {
        "required_columns": ["SPECIES_ID", "COMMON_NAME_FR"],
        "not_null": ["SPECIES_ID"],
        "unique_key": ["SPECIES_ID", "SPECIES_SPECIFICITY_ID"],
    },
    "qualification": {
        "required_columns": ["SL_TRIAL", "YEAR", "QUALIFICATION", "RESULT"],
        "not_null": ["SL_TRIAL", "YEAR", "QUALIFICATION"],
        "unique_key": ["SL_TRIAL", "YEAR", "QUALIFICATION"],
    },
}


def _invalid_result_mask(frame):
    numeric = (
        frame["RESULT"].astype(str).str.replace(",", ".", regex=False)
        .pipe(pd.to_numeric, errors="coerce")
    )
    yield_trait = frame["TRAIT"].isin(["YD15QH", "YD16QH", "YDQH", "YD"])
    return numeric.isna() | (yield_trait & ~numeric.between(0, 250))


def audit_table(name, contract):
    path = os.path.join(RAW_DIR, f"{name}.parquet")
    frame = pd.read_parquet(path)
    missing_columns = sorted(set(contract["required_columns"]) - set(frame.columns))
    if missing_columns:
        raise RuntimeError(f"{name}: colonnes obligatoires absentes: {missing_columns}")

    null_mask = frame[contract["not_null"]].isna().any(axis=1)
    duplicate_mask = frame.duplicated(contract["unique_key"], keep=False)
    invalid_mask = pd.Series(False, index=frame.index)
    if name == "resultats":
        invalid_mask |= _invalid_result_mask(frame)
    if "YEAR" in frame:
        year = pd.to_numeric(frame["YEAR"], errors="coerce")
        invalid_mask |= year.notna() & ~year.between(1900, 2100)

    quarantine_mask = null_mask | invalid_mask
    quarantine = frame.loc[quarantine_mask].copy()
    if not quarantine.empty:
        reasons = []
        for idx in quarantine.index:
            row_reasons = []
            if null_mask.loc[idx]:
                row_reasons.append("required_null")
            if invalid_mask.loc[idx]:
                row_reasons.append("invalid_value")
            reasons.append("|".join(row_reasons))
        quarantine["QUALITY_REASON"] = reasons
        quarantine.to_parquet(
            os.path.join(QUARANTINE_DIR, f"{name}_quarantine.parquet"), index=False
        )
        quarantine.to_csv(
            os.path.join(QUARANTINE_DIR, f"{name}_quarantine.csv"),
            index=False, sep=";", encoding="utf-8-sig",
        )

    return {
        "dataset": name,
        "rows": int(len(frame)),
        "columns": int(len(frame.columns)),
        "full_duplicates": int(frame.duplicated().sum()),
        "duplicate_key_rows": int(duplicate_mask.sum()),
        "required_null_rows": int(null_mask.sum()),
        "invalid_value_rows": int(invalid_mask.sum()),
        "quarantined_rows": int(quarantine_mask.sum()),
        "quarantine_rate": round(float(quarantine_mask.mean()), 6),
        "required_columns": contract["required_columns"],
        "unique_key": contract["unique_key"],
        "status": "PASS" if not missing_columns else "FAIL",
    }


def run():
    print("=" * 80)
    print("  QUALITE DES DONNEES - contrats, doublons et quarantaine")
    print("=" * 80)
    os.makedirs(QUARANTINE_DIR, exist_ok=True)
    os.makedirs(REPORT_DIR, exist_ok=True)
    tables = [audit_table(name, contract) for name, contract in CONTRACTS.items()]
    report = {
        "status": "OK" if all(row["status"] == "PASS" for row in tables) else "ERROR",
        "policy": {
            "source_immutability": True,
            "invalid_rows_are_quarantined": True,
            "duplicates_are_reported_not_silently_deleted": True,
        },
        "tables": tables,
        "totals": {
            "rows": sum(row["rows"] for row in tables),
            "full_duplicates": sum(row["full_duplicates"] for row in tables),
            "duplicate_key_rows": sum(row["duplicate_key_rows"] for row in tables),
            "quarantined_rows": sum(row["quarantined_rows"] for row in tables),
        },
        "timestamp": datetime.now().isoformat(),
    }
    with open(os.path.join(REPORT_DIR, "data_quality_report.json"), "w",
              encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
    for row in tables:
        print(
            f"  {row['dataset']:<15} rows={row['rows']:>7,} "
            f"duplicates={row['duplicate_key_rows']:>6,} "
            f"quarantine={row['quarantined_rows']:>5,}"
        )
    if report["status"] != "OK":
        raise RuntimeError("Un ou plusieurs contrats de données ont échoué")
    print("  Rapport: reports/data_quality_report.json")
    return report


if __name__ == "__main__":
    run()
