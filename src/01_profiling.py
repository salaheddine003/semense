"""
Phase 1 — Profiling des données sources
Analyse la qualité, la structure et le contenu de chaque fichier CSV.
"""

import pandas as pd
import numpy as np
import os
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_DIR = os.path.join(BASE_DIR, "CSV")
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
REPORT_DIR = os.path.join(BASE_DIR, "reports")

FILES = {
    "essai":               "ESSAI.csv",
    "materiel":            "LK_CRISP_MATERIAL_20190108.csv",
    "parcelle":            "PARCELLE_SPECIFICATION_20190108.csv",
    "especes":             "REF_ESPECES_20190108.csv",
    "resultats":           "RESULTAT_ESSAIS.csv",
    "qualification":       "TRIAL_QUALIFICATION_20190108.csv",
}


def load_csv(filename: str) -> pd.DataFrame:
    path = os.path.join(CSV_DIR, filename)
    df = pd.read_csv(path, sep=";", encoding="utf-8", encoding_errors="replace", low_memory=False)
    # Nettoyer les noms de colonnes (BOM possible)
    df.columns = [c.lstrip("\ufeff").strip() for c in df.columns]
    return df


def profile_dataframe(name: str, df: pd.DataFrame) -> dict:
    report = {
        "nom": name,
        "nb_lignes": len(df),
        "nb_colonnes": len(df.columns),
        "colonnes": {},
    }
    for col in df.columns:
        series = df[col]
        nulls = int(series.isna().sum()) + int((series == "").sum())
        pct_null = round(nulls / len(df) * 100, 2) if len(df) > 0 else 0
        uniques = int(series.nunique())
        info = {
            "dtype": str(series.dtype),
            "nulls": nulls,
            "pct_null": pct_null,
            "uniques": uniques,
        }
        if pd.api.types.is_numeric_dtype(series):
            info["min"] = float(series.min()) if not series.empty else None
            info["max"] = float(series.max()) if not series.empty else None
            info["mean"] = round(float(series.mean()), 4) if not series.empty else None
        else:
            top = series.value_counts().head(5).to_dict()
            info["top_values"] = {str(k): int(v) for k, v in top.items()}
        report["colonnes"][col] = info
    return report


def print_report(report: dict):
    sep = "─" * 80
    print(f"\n{sep}")
    print(f"  TABLE : {report['nom'].upper()}")
    print(f"  {report['nb_lignes']:,} lignes  |  {report['nb_colonnes']} colonnes")
    print(sep)
    for col, info in report["colonnes"].items():
        null_str = f"{info['pct_null']}% null" if info['pct_null'] > 0 else "complet"
        if "mean" in info:
            detail = f"[{info['min']:.2f} – {info['max']:.2f}], moy={info['mean']:.2f}"
        else:
            top_keys = list(info.get("top_values", {}).keys())[:3]
            detail = "top: " + ", ".join(str(k) for k in top_keys)
        print(f"  {col:<45} {null_str:<15} {info['uniques']:>6} uniques  {detail}")


def check_referential_integrity(dfs: dict):
    print("\n" + "═" * 80)
    print("  VÉRIFICATION INTÉGRITÉ RÉFÉRENTIELLE")
    print("═" * 80)

    # ESSAI → PARCELLE via LK_EXPERIMENT_EXPERIMENT_ID
    essai_ids = set(dfs["essai"]["LK_EXPERIMENT_EXPERIMENT_ID"].astype(str))
    parcelle_ids = set(dfs["parcelle"]["LK_EXPERIMENT_EXPERIMENT_ID"].astype(str))
    orphelins = parcelle_ids - essai_ids
    print(f"  PARCELLE → ESSAI (LK_EXPERIMENT_EXPERIMENT_ID):  {len(orphelins)} orphelins / {len(parcelle_ids)} parcelles")

    # PARCELLE → MATERIEL via LK_STOCK_S1_DATA_ID
    mat_ids = set(dfs["materiel"]["LK_STOCK_S1_DATA_ID"].astype(str))
    parcelle_mat = set(dfs["parcelle"]["LK_STOCK_S1_DATA_ID"].astype(str))
    orphelins2 = parcelle_mat - mat_ids
    print(f"  PARCELLE → MATERIEL (LK_STOCK_S1_DATA_ID):       {len(orphelins2)} orphelins / {len(parcelle_mat)} parcelles")

    # RESULTAT → ESSAI
    res_ids = set(dfs["resultats"]["LK_EXPERIMENT_EXPERIMENT_ID"].astype(str))
    orphelins3 = res_ids - essai_ids
    print(f"  RESULTATS → ESSAI (LK_EXPERIMENT_EXPERIMENT_ID): {len(orphelins3)} orphelins / {len(res_ids)} résultats")

    # ESSAI → ESPECES via SPECIES_ID + SPECIES_SPECIFICITY_ID
    esp_keys = set(
        zip(
            dfs["especes"]["SPECIES_ID"].astype(str),
            dfs["especes"]["SPECIES_SPECIFICITY_ID"].astype(str),
        )
    )
    essai_keys = set(
        zip(
            dfs["essai"]["SPECIES_ID"].astype(str),
            dfs["essai"]["SPECIES_SPECIFICITY_ID"].astype(str),
        )
    )
    orphelins4 = essai_keys - esp_keys
    print(f"  ESSAI → ESPECES (SPECIES_ID+SPECIFICITY_ID):      {len(orphelins4)} combinaisons non trouvées dans ref espèces")


def save_raw_copies(dfs: dict):
    os.makedirs(RAW_DIR, exist_ok=True)
    for name, df in dfs.items():
        out = os.path.join(RAW_DIR, f"{name}.parquet")
        df.to_parquet(out, index=False)
    print(f"\n  Copies raw sauvegardées dans {RAW_DIR}")


def run():
    print("=" * 80)
    print("  PHASE 1 — PROFILING DES DONNÉES SOURCES")
    print("=" * 80)

    dfs = {}
    profiles = {}
    for name, filename in FILES.items():
        print(f"\nChargement : {filename}...", end=" ")
        df = load_csv(filename)
        dfs[name] = df
        print(f"{len(df):,} lignes OK")
        profiles[name] = profile_dataframe(name, df)
        print_report(profiles[name])

    check_referential_integrity(dfs)
    save_raw_copies(dfs)

    # Sauvegarde JSON du profiling
    os.makedirs(REPORT_DIR, exist_ok=True)
    with open(os.path.join(REPORT_DIR, "profiling.json"), "w", encoding="utf-8") as f:
        json.dump(profiles, f, ensure_ascii=False, indent=2)
    print(f"\n  Rapport de profiling exporté : reports/profiling.json")


if __name__ == "__main__":
    run()
