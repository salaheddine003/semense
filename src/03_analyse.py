"""
Phase 3 — Analyse statistique
Calcul des KPIs et statistiques descriptives par espèce, région, année, trait.
Exporte les résultats dans data/enriched/ pour le dashboard.
"""

import pandas as pd
import numpy as np
from scipy import stats
import os
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENRICH_DIR = os.path.join(BASE_DIR, "data", "enriched")
REPORT_DIR = os.path.join(BASE_DIR, "reports")

TRAITS_LABELS = {
    "%MOIS": "Humidité (%)",
    "YD15QH": "Rendement Q/Ha (2015 base)",
    "YD16QH": "Rendement Q/Ha (2016 base)",
    "YDQH":   "Rendement Q/Ha",
    "YD":     "Rendement",
}


def load_fact() -> pd.DataFrame:
    return pd.read_parquet(os.path.join(ENRICH_DIR, "fact_table.parquet"))


# ─────────────────────────────────────────────
# KPI GLOBAUX
# ─────────────────────────────────────────────

def kpi_globaux(fact: pd.DataFrame) -> dict:
    kpi = {
        "nb_essais":        int(fact["LK_EXPERIMENT_EXPERIMENT_ID"].nunique()),
        "nb_materiels":     int(fact["LK_STOCK_S1_DATA_ID"].nunique()),
        "nb_mesures":       int(len(fact)),
        "nb_traits":        int(fact["TRAIT"].nunique()),
        "nb_especes":       int(fact["ESPECE_FR"].nunique()),
        "nb_regions":       int(fact["REGION"].nunique()),
        "annees_couvertes": sorted(fact["YEAR"].dropna().astype(int).unique().tolist()),
        "especes":          fact["ESPECE_FR"].dropna().value_counts().to_dict(),
        "traits_top20":     fact["TRAIT"].value_counts().head(20).to_dict(),
    }
    return kpi


# ─────────────────────────────────────────────
# STATS PAR ESPÈCE × TRAIT
# ─────────────────────────────────────────────

def stats_espece_trait(fact: pd.DataFrame) -> pd.DataFrame:
    subset = fact[fact["RESULT_NUM"].notna()].copy()
    grp = subset.groupby(["ESPECE_FR", "TRAIT"])["RESULT_NUM"].agg(
        count="count",
        mean="mean",
        median="median",
        std="std",
        min="min",
        max="max",
        q25=lambda x: x.quantile(0.25),
        q75=lambda x: x.quantile(0.75),
    ).reset_index()
    grp = grp[grp["count"] >= 10]  # au moins 10 observations
    grp = grp.round(4)
    return grp


# ─────────────────────────────────────────────
# ÉVOLUTION ANNUELLE PAR ESPÈCE (rendement)
# ─────────────────────────────────────────────

YIELD_TRAITS = ["%MOIS", "YD15QH", "YD16QH", "YDQH", "YD"]

def evolution_annuelle(fact: pd.DataFrame) -> pd.DataFrame:
    subset = fact[
        fact["TRAIT"].isin(YIELD_TRAITS) & fact["RESULT_NUM"].notna()
    ].copy()
    grp = subset.groupby(["YEAR", "ESPECE_FR", "TRAIT"])["RESULT_NUM"].agg(
        count="count",
        mean="mean",
        std="std",
    ).reset_index()
    grp = grp[grp["count"] >= 5]
    grp = grp.round(4)
    return grp


# ─────────────────────────────────────────────
# TOP PERFORMANCES PAR MATÉRIEL
# ─────────────────────────────────────────────

def top_materiels(fact: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    subset = fact[
        fact["TRAIT"].isin(YIELD_TRAITS) &
        fact["RESULT_NUM"].notna() &
        fact["MAIN_NAME"].notna()
    ].copy()
    grp = subset.groupby(["MAIN_NAME", "ESPECE_FR", "TRAIT"])["RESULT_NUM"].agg(
        count="count",
        mean="mean",
        std="std",
    ).reset_index()
    grp = grp[grp["count"] >= 3]
    grp = grp.sort_values("mean", ascending=False).head(top_n)
    return grp.round(4)


# ─────────────────────────────────────────────
# ANALYSE DE FIABILITÉ
# ─────────────────────────────────────────────

def stats_fiabilite(fact: pd.DataFrame) -> pd.DataFrame:
    cols = ["FIABILITY_EXPERIMENTAL", "FIABILITY_BREEDER"]
    essai_unique = fact.drop_duplicates("LK_EXPERIMENT_EXPERIMENT_ID")[
        ["LK_EXPERIMENT_EXPERIMENT_ID", "ESPECE_FR", "YEAR", "REGION"] + cols
    ].copy()
    for col in cols:
        essai_unique[col] = pd.to_numeric(essai_unique[col], errors="coerce")
    return essai_unique


# ─────────────────────────────────────────────
# DISTRIBUTION DES ESSAIS PAR RÉGION
# ─────────────────────────────────────────────

def essais_par_region(fact: pd.DataFrame) -> pd.DataFrame:
    grp = (
        fact.drop_duplicates("LK_EXPERIMENT_EXPERIMENT_ID")
        .groupby(["REGION", "ESPECE_FR"])
        .size()
        .reset_index(name="nb_essais")
        .sort_values("nb_essais", ascending=False)
    )
    return grp


# ─────────────────────────────────────────────
# CORRÉLATION TRAITS PAR ESPÈCE
# ─────────────────────────────────────────────

def correlations_traits(fact: pd.DataFrame) -> dict:
    results = {}
    for espece in fact["ESPECE_FR"].dropna().unique():
        sub = fact[(fact["ESPECE_FR"] == espece) & fact["RESULT_NUM"].notna()]
        pivot = sub.pivot_table(
            index=["LK_EXPERIMENT_EXPERIMENT_ID", "REPLICATION_NUM", "ENTRY_NUM"],
            columns="TRAIT",
            values="RESULT_NUM",
            aggfunc="mean",
        )
        pivot = pivot.dropna(thresh=2)
        cols_ok = [c for c in pivot.columns if pivot[c].notna().sum() >= 20]
        pivot = pivot[cols_ok]
        if len(pivot.columns) >= 2 and len(pivot) >= 20:
            corr = pivot.corr(method="pearson").round(3)
            results[espece] = corr.to_dict()
    return results


# ─────────────────────────────────────────────
# TEST ANOVA : rendement par région (par espèce)
# ─────────────────────────────────────────────

def anova_rendement_region(fact: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for espece in fact["ESPECE_FR"].dropna().unique():
        for trait in YIELD_TRAITS:
            sub = fact[
                (fact["ESPECE_FR"] == espece) &
                (fact["TRAIT"] == trait) &
                fact["RESULT_NUM"].notna() &
                fact["REGION"].notna()
            ]
            groupes = [g["RESULT_NUM"].values for _, g in sub.groupby("REGION") if len(g) >= 5]
            if len(groupes) >= 2:
                try:
                    f_stat, p_val = stats.f_oneway(*groupes)
                    rows.append({
                        "ESPECE_FR": espece,
                        "TRAIT": trait,
                        "nb_regions": len(groupes),
                        "F_stat": round(f_stat, 4),
                        "p_value": round(p_val, 6),
                        "significatif": p_val < 0.05,
                    })
                except Exception:
                    pass
    return pd.DataFrame(rows)


def run():
    os.makedirs(REPORT_DIR, exist_ok=True)

    print("=" * 80)
    print("  PHASE 3 — ANALYSE STATISTIQUE")
    print("=" * 80)

    print("\nChargement de la table de faits...")
    fact = load_fact()
    print(f"  {len(fact):,} lignes chargées")

    print("\n[1] KPIs globaux...")
    kpi = kpi_globaux(fact)
    with open(os.path.join(REPORT_DIR, "kpi_globaux.json"), "w", encoding="utf-8") as f:
        json.dump(kpi, f, ensure_ascii=False, indent=2, default=str)
    print(f"  Nb essais    : {kpi['nb_essais']:,}")
    print(f"  Nb matériels : {kpi['nb_materiels']:,}")
    print(f"  Nb mesures   : {kpi['nb_mesures']:,}")
    print(f"  Traits uniques: {kpi['nb_traits']}")
    print(f"  Espèces      : {', '.join(kpi['especes'].keys())}")

    print("\n[2] Stats espèce × trait...")
    stats_et = stats_espece_trait(fact)
    stats_et.to_parquet(os.path.join(ENRICH_DIR, "stats_espece_trait.parquet"), index=False)
    stats_et.to_csv(os.path.join(ENRICH_DIR, "stats_espece_trait.csv"), index=False, sep=";", encoding="utf-8-sig")
    print(f"  {len(stats_et)} combinaisons espèce×trait calculées")

    print("\n[3] Évolution annuelle...")
    evol = evolution_annuelle(fact)
    evol.to_parquet(os.path.join(ENRICH_DIR, "evolution_annuelle.parquet"), index=False)
    evol.to_csv(os.path.join(ENRICH_DIR, "evolution_annuelle.csv"), index=False, sep=";", encoding="utf-8-sig")
    print(f"  {len(evol)} points d'évolution calculés")

    print("\n[4] Top matériels performants...")
    top_mat = top_materiels(fact)
    top_mat.to_csv(os.path.join(ENRICH_DIR, "top_materiels.csv"), index=False, sep=";", encoding="utf-8-sig")
    print(top_mat[["MAIN_NAME", "ESPECE_FR", "TRAIT", "count", "mean"]].to_string(index=False))

    print("\n[5] Distribution essais par région...")
    reg = essais_par_region(fact)
    reg.to_csv(os.path.join(ENRICH_DIR, "essais_par_region.csv"), index=False, sep=";", encoding="utf-8-sig")
    print(reg.head(10).to_string(index=False))

    print("\n[6] Corrélations inter-traits par espèce...")
    corr = correlations_traits(fact)
    with open(os.path.join(REPORT_DIR, "correlations.json"), "w", encoding="utf-8") as f:
        json.dump(corr, f, ensure_ascii=False, indent=2, default=str)
    print(f"  Corrélations calculées pour {len(corr)} espèces")

    print("\n[7] ANOVA rendement × région...")
    anova = anova_rendement_region(fact)
    if not anova.empty:
        anova.to_csv(os.path.join(ENRICH_DIR, "anova_region.csv"), index=False, sep=";", encoding="utf-8-sig")
        sig = anova[anova["significatif"]]
        print(f"  {len(sig)}/{len(anova)} tests significatifs (p<0.05)")
        print(anova.to_string(index=False))

    print("\n  Analyse statistique terminée.")
    return fact


if __name__ == "__main__":
    run()
