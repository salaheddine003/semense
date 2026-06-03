"""
Phase 2 — Pipeline ETL
Nettoyage, typage, normalisation et jointures des 6 tables sources.
Produit :
  data/transformed/  — tables individuelles nettoyées (parquet)
  data/enriched/     — table de faits consolidée (parquet + csv)
"""

import pandas as pd
import numpy as np
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
TRANS_DIR = os.path.join(BASE_DIR, "data", "transformed")
ENRICH_DIR = os.path.join(BASE_DIR, "data", "enriched")

ESPECES_FR = {
    "C": "Colza",
    "O": "Colza",
    "S": "Tournesol",
    "W": "Blé tendre",
    "T": "Triticale",
    "B": "Blé dur/Orge",
    "M": "Maïs",
    "L": "Lin",
    "P": "Pois",
}


# ─────────────────────────────────────────────
# 1. CHARGEMENT DES RAW PARQUET
# ─────────────────────────────────────────────

def load_raw(name: str) -> pd.DataFrame:
    return pd.read_parquet(os.path.join(RAW_DIR, f"{name}.parquet"))


# ─────────────────────────────────────────────
# 2. NETTOYAGE PAR TABLE
# ─────────────────────────────────────────────

def _to_id_str(series: pd.Series) -> pd.Series:
    """Convertit une colonne ID numérique en string sans '.0'."""
    num = pd.to_numeric(series, errors="coerce")
    filled = num.fillna(-1).astype(int).astype(str)
    # Remettre NaN là où c'était NaN
    filled[num.isna()] = ""
    return filled


def clean_essai(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Typage
    df["LK_EXPERIMENT_EXPERIMENT_ID"] = _to_id_str(df["LK_EXPERIMENT_EXPERIMENT_ID"])
    df["YEAR"] = pd.to_numeric(df["YEAR"], errors="coerce").astype("Int64")
    for col in ["CULTURE_UNIT_LATITUDE", "CULTURE_UNIT_LONGITUDE",
                "CULTURE_PLACE_LATITUDE", "CULTURE_PLACE_LONGITUDE",
                "LATITUDE", "LONGITUDE"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    # Coordonnées dé-normalisées : prendre la meilleure disponible
    df["LAT"] = df["LATITUDE"].fillna(df["CULTURE_UNIT_LATITUDE"]).fillna(df["CULTURE_PLACE_LATITUDE"])
    df["LON"] = df["LONGITUDE"].fillna(df["CULTURE_UNIT_LONGITUDE"]).fillna(df["CULTURE_PLACE_LONGITUDE"])
    # Mettre lat/lon invalides (0,0) à NaN
    df.loc[(df["LAT"] == 0) & (df["LON"] == 0), ["LAT", "LON"]] = np.nan
    df["SPECIES"] = df["SPECIES"].astype(str).str.strip()
    df["ESPECE_FR"] = df["SPECIES"].map(ESPECES_FR).fillna(df["SPECIES"])
    df["FIABILITY_EXPERIMENTAL"] = pd.to_numeric(df["FIABILITY_EXPERIMENTAL"], errors="coerce")
    df["FIABILITY_BREEDER"] = pd.to_numeric(df["FIABILITY_BREEDER"], errors="coerce")
    # Supprimer les essais sans ID valide
    df = df[df["LK_EXPERIMENT_EXPERIMENT_ID"].notna() & (df["LK_EXPERIMENT_EXPERIMENT_ID"] != "")]
    return df


def clean_resultats(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["LK_EXPERIMENT_EXPERIMENT_ID"] = _to_id_str(df["LK_EXPERIMENT_EXPERIMENT_ID"])
    df["YEAR"] = pd.to_numeric(df["YEAR"], errors="coerce").astype("Int64")
    df["SL_TRIAL"] = df["SL_TRIAL"].astype(str).str.strip()
    df["ESPECE_FR"] = df["SPECIES"].astype(str).str.strip().map(ESPECES_FR).fillna(df["SPECIES"].astype(str).str.strip())
    df["TRAIT"] = df["TRAIT"].astype(str).str.strip()
    # La valeur RESULT est au format français (virgule décimale)
    df["RESULT_NUM"] = (
        df["RESULT"]
        .astype(str)
        .str.replace(",", ".", regex=False)
        .pipe(pd.to_numeric, errors="coerce")
    )
    return df


def clean_parcelle(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["LK_EXPERIMENT_EXPERIMENT_ID"] = _to_id_str(df["LK_EXPERIMENT_EXPERIMENT_ID"])
    df["LK_SL_TRIAL_L4_DATA_ID"] = _to_id_str(df["LK_SL_TRIAL_L4_DATA_ID"])
    df["LK_STOCK_S1_DATA_ID"] = _to_id_str(df["LK_STOCK_S1_DATA_ID"])
    df["SL_TRIAL"] = df["SL_TRIAL"].astype(str).str.strip()
    df["YEAR"] = pd.to_numeric(df["YEAR"], errors="coerce").astype("Int64")
    df["REPLICATION_NUM"] = pd.to_numeric(df["REPLICATION_NUM"], errors="coerce").astype("Int64")
    df["ENTRY_NUM"] = pd.to_numeric(df["ENTRY_NUM"], errors="coerce").astype("Int64")
    return df


def clean_materiel(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["LK_STOCK_S1_DATA_ID"] = _to_id_str(df["LK_STOCK_S1_DATA_ID"])
    df["SPECIES"] = df["SPECIES"].astype(str).str.strip()
    df["ESPECE_FR"] = df["SPECIES"].map(ESPECES_FR).fillna(df["SPECIES"])
    df["MAIN_NAME"] = df["MAIN_NAME"].astype(str).str.strip()
    df["PEDIGREE"] = df["PEDIGREE"].astype(str).str.strip()
    df["STRUCTURE"] = df["STRUCTURE"].astype(str).str.strip()
    return df


def clean_especes(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["SPECIES_ID"] = df["SPECIES_ID"].astype(str).str.strip()
    df["SPECIES_SPECIFICITY_ID"] = df["SPECIES_SPECIFICITY_ID"].astype(str).str.strip()
    df["COMMON_NAME_FR"] = df["COMMON_NAME_FR"].astype(str).str.strip()
    return df


def clean_qualification(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["SL_TRIAL"] = df["SL_TRIAL"].astype(str).str.strip()
    df["YEAR"] = pd.to_numeric(df["YEAR"], errors="coerce").astype("Int64")
    df["QUALIFICATION"] = df["QUALIFICATION"].astype(str).str.strip()
    df["RESULT"] = df["RESULT"].astype(str).str.strip()
    # Pivoter pour avoir une qualification par essai par attribut
    df_pivot = df.pivot_table(
        index=["SL_TRIAL", "YEAR"],
        columns="QUALIFICATION",
        values="RESULT",
        aggfunc="first",
    ).reset_index()
    df_pivot.columns.name = None
    return df_pivot


# ─────────────────────────────────────────────
# 3. CONSTRUCTION DE LA TABLE DE FAITS
# ─────────────────────────────────────────────

def build_fact_table(essai, resultats, parcelle, materiel, especes, qual_pivot) -> pd.DataFrame:
    print("  Jointure RESULTATS ← ESSAI...")
    fact = resultats.merge(
        essai[[
            "LK_EXPERIMENT_EXPERIMENT_ID",
            "REGION", "DEPARTMENT", "COMMUNE", "LAT", "LON",
            "RESPONSIBILITY", "TEAM", "CULTURE_UNIT",
            "FIABILITY_EXPERIMENTAL", "FIABILITY_BREEDER",
        ]],
        on=["LK_EXPERIMENT_EXPERIMENT_ID"],
        how="left",
    )
    # ESPECE_FR is already on resultats from clean_resultats; backfill from ESSAI if missing
    if "ESPECE_FR" not in fact.columns:
        fact["ESPECE_FR"] = fact["SPECIES"].astype(str).map(ESPECES_FR)

    print("  Jointure ← PARCELLE (LK_STOCK_S1_DATA_ID)...")
    parcelle_key = parcelle[["LK_EXPERIMENT_EXPERIMENT_ID", "SL_TRIAL", "REPLICATION_NUM",
                              "ENTRY_NUM", "LK_STOCK_S1_DATA_ID"]].drop_duplicates()
    fact = fact.merge(
        parcelle_key,
        on=["LK_EXPERIMENT_EXPERIMENT_ID", "SL_TRIAL", "REPLICATION_NUM", "ENTRY_NUM"],
        how="left",
    )

    print("  Jointure ← MATERIEL...")
    mat_cols = ["LK_STOCK_S1_DATA_ID", "MAIN_NAME", "PEDIGREE", "STRUCTURE",
                "P1", "P2", "NEXT_STAGE", "SELF_NB"]
    fact = fact.merge(
        materiel[mat_cols].drop_duplicates("LK_STOCK_S1_DATA_ID"),
        on="LK_STOCK_S1_DATA_ID",
        how="left",
    )

    print("  Jointure ← QUALIFICATIONS...")
    fact = fact.merge(qual_pivot, on=["SL_TRIAL", "YEAR"], how="left")

    print(f"  Table de faits : {len(fact):,} lignes × {len(fact.columns)} colonnes")
    return fact


# ─────────────────────────────────────────────
# 4. SAUVEGARDE
# ─────────────────────────────────────────────

def save(df: pd.DataFrame, folder: str, name: str):
    os.makedirs(folder, exist_ok=True)
    df.to_parquet(os.path.join(folder, f"{name}.parquet"), index=False)
    print(f"  Sauvegardé : {folder}/{name}.parquet")


def run():
    os.makedirs(TRANS_DIR, exist_ok=True)
    os.makedirs(ENRICH_DIR, exist_ok=True)

    print("=" * 80)
    print("  PHASE 2 — PIPELINE ETL")
    print("=" * 80)

    print("\n[1/6] Nettoyage ESSAI...")
    essai = clean_essai(load_raw("essai"))
    save(essai, TRANS_DIR, "essai")

    print("\n[2/6] Nettoyage RÉSULTATS...")
    resultats = clean_resultats(load_raw("resultats"))
    save(resultats, TRANS_DIR, "resultats")

    print("\n[3/6] Nettoyage PARCELLES...")
    parcelle = clean_parcelle(load_raw("parcelle"))
    save(parcelle, TRANS_DIR, "parcelle")

    print("\n[4/6] Nettoyage MATÉRIEL...")
    materiel = clean_materiel(load_raw("materiel"))
    save(materiel, TRANS_DIR, "materiel")

    print("\n[5/6] Nettoyage ESPÈCES...")
    especes = clean_especes(load_raw("especes"))
    save(especes, TRANS_DIR, "especes")

    print("\n[6/6] Nettoyage + pivot QUALIFICATIONS...")
    qual_pivot = clean_qualification(load_raw("qualification"))
    save(qual_pivot, TRANS_DIR, "qualification_pivot")

    print("\n[7/7] Construction de la table de faits enrichie...")
    fact = build_fact_table(essai, resultats, parcelle, materiel, especes, qual_pivot)
    save(fact, ENRICH_DIR, "fact_table")
    # Export CSV pour accès R
    fact.to_csv(os.path.join(ENRICH_DIR, "fact_table.csv"), index=False, sep=";", encoding="utf-8-sig")
    print(f"  Export CSV : data/enriched/fact_table.csv")

    print("\n  ETL terminé avec succès.")
    return fact


if __name__ == "__main__":
    run()
