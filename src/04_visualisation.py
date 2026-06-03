"""
Phase 4 — Visualisations
Génère tous les graphiques statiques (PNG) et la carte géographique interactive (HTML).
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
import folium
from folium.plugins import MarkerCluster
import os
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENRICH_DIR = os.path.join(BASE_DIR, "data", "enriched")
REPORT_DIR = os.path.join(BASE_DIR, "reports")
IMG_DIR = os.path.join(REPORT_DIR, "images")


PALETTE = {
    "Maïs":          "#F5A623",
    "Tournesol":     "#F8D64E",
    "Blé tendre":    "#7ED321",
    "Triticale":     "#4A90E2",
    "Colza":         "#BD10E0",
    "Blé dur/Orge":  "#9B9B9B",
}

YIELD_TRAITS = ["%MOIS", "YD15QH", "YD16QH", "YDQH", "YD"]

sns.set_theme(style="whitegrid", font_scale=1.05)


def setup_dirs():
    os.makedirs(IMG_DIR, exist_ok=True)


def save_fig(name: str, dpi: int = 150):
    path = os.path.join(IMG_DIR, f"{name}.png")
    plt.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close()
    print(f"  Graphique : reports/images/{name}.png")


# ─────────────────────────────────────────────
# 1. RÉPARTITION DES ESSAIS PAR ESPÈCE
# ─────────────────────────────────────────────

def plot_essais_especes(fact: pd.DataFrame):
    counts = (
        fact.drop_duplicates("LK_EXPERIMENT_EXPERIMENT_ID")["ESPECE_FR"]
        .value_counts()
    )
    colors = [PALETTE.get(sp, "#999") for sp in counts.index]
    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.barh(counts.index, counts.values, color=colors, edgecolor="white")
    for bar, val in zip(bars, counts.values):
        ax.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
                str(val), va="center", fontsize=10)
    ax.set_xlabel("Nombre d'essais")
    ax.set_title("Répartition des essais par espèce", fontweight="bold")
    ax.invert_yaxis()
    plt.tight_layout()
    save_fig("01_essais_par_espece")


# ─────────────────────────────────────────────
# 2. ESSAIS PAR ANNÉE
# ─────────────────────────────────────────────

def plot_essais_annee(fact: pd.DataFrame):
    df = (
        fact.drop_duplicates("LK_EXPERIMENT_EXPERIMENT_ID")
        .groupby("YEAR")
        .size()
        .reset_index(name="nb")
    )
    df = df[df["YEAR"].between(2010, 2025)]
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.bar(df["YEAR"].astype(int), df["nb"], color="#4A90E2", edgecolor="white")
    ax.set_xlabel("Année")
    ax.set_ylabel("Nombre d'essais")
    ax.set_title("Évolution du nombre d'essais par année", fontweight="bold")
    ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    plt.tight_layout()
    save_fig("02_essais_par_annee")


# ─────────────────────────────────────────────
# 3. BOXPLOT RENDEMENTS PAR ESPÈCE
# ─────────────────────────────────────────────

def plot_boxplot_rendement(fact: pd.DataFrame):
    subset = fact[
        fact["TRAIT"].isin(YIELD_TRAITS) &
        fact["RESULT_NUM"].notna() &
        fact["ESPECE_FR"].notna()
    ].copy()
    # Garder les espèces avec assez de données
    valid_esp = subset.groupby("ESPECE_FR").size()
    valid_esp = valid_esp[valid_esp >= 30].index
    subset = subset[subset["ESPECE_FR"].isin(valid_esp)]
    # Supprimer les outliers extrêmes (IQR 3×)
    q1 = subset["RESULT_NUM"].quantile(0.01)
    q99 = subset["RESULT_NUM"].quantile(0.99)
    subset = subset[(subset["RESULT_NUM"] >= q1) & (subset["RESULT_NUM"] <= q99)]

    especes_present = sorted(subset["ESPECE_FR"].unique().tolist())
    data_by_esp = [subset[subset["ESPECE_FR"] == esp]["RESULT_NUM"].dropna().values
                   for esp in especes_present]
    colors = [PALETTE.get(sp, "#888") for sp in especes_present]
    fig, ax = plt.subplots(figsize=(10, 5))
    bps = ax.boxplot(data_by_esp, patch_artist=True, widths=0.5,
                     flierprops=dict(marker=".", alpha=0.3, markersize=3))
    for patch, color in zip(bps["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.75)
    ax.set_xticks(range(1, len(especes_present) + 1))
    ax.set_xticklabels(especes_present, rotation=20, ha="right")
    ax.set_xlabel("Espèce")
    ax.set_ylabel("Valeur mesurée")
    ax.set_title("Distribution des mesures de rendement/humidité par espèce", fontweight="bold")
    plt.tight_layout()
    save_fig("03_boxplot_rendement_espece")


# ─────────────────────────────────────────────
# 4. ÉVOLUTION ANNUELLE DU RENDEMENT
# ─────────────────────────────────────────────

def plot_evolution_annuelle(fact: pd.DataFrame):
    subset = fact[
        fact["TRAIT"].isin(YIELD_TRAITS) &
        fact["RESULT_NUM"].notna() &
        fact["ESPECE_FR"].notna() &
        fact["YEAR"].notna()
    ].copy()
    subset["YEAR"] = subset["YEAR"].astype(int)
    subset = subset[subset["YEAR"].between(2010, 2025)]
    grp = subset.groupby(["YEAR", "ESPECE_FR"])["RESULT_NUM"].mean().reset_index()

    valid_esp = grp.groupby("ESPECE_FR").size()
    valid_esp = valid_esp[valid_esp >= 3].index
    grp = grp[grp["ESPECE_FR"].isin(valid_esp)]

    if grp.empty:
        print("  Évolution annuelle : données insuffisantes, ignoré.")
        return
    fig, ax = plt.subplots(figsize=(11, 5))
    for espece, sub in grp.groupby("ESPECE_FR"):
        sub = sub.sort_values("YEAR")
        color = PALETTE.get(espece, "#888")
        ax.plot(sub["YEAR"], sub["RESULT_NUM"], marker="o", label=espece, color=color, linewidth=2)
    ax.set_xlabel("Année")
    ax.set_ylabel("Valeur moyennée (traits rendement/humidité)")
    ax.set_title("Évolution annuelle moyenne par espèce", fontweight="bold")
    ax.legend(title="Espèce", bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=9)
    ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    plt.tight_layout()
    save_fig("04_evolution_annuelle")


# ─────────────────────────────────────────────
# 5. TOP 15 RÉGIONS PAR NOMBRE D'ESSAIS
# ─────────────────────────────────────────────

def plot_top_regions(fact: pd.DataFrame):
    essais_u = fact.drop_duplicates("LK_EXPERIMENT_EXPERIMENT_ID")
    top = essais_u["REGION"].value_counts().dropna().head(15)
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(top.index, top.values, color="#4A90E2", edgecolor="white")
    for i, v in enumerate(top.values):
        ax.text(v + 0.3, i, str(v), va="center", fontsize=9)
    ax.set_xlabel("Nombre d'essais")
    ax.set_title("Top 15 régions par nombre d'essais", fontweight="bold")
    ax.invert_yaxis()
    plt.tight_layout()
    save_fig("05_top_regions")


# ─────────────────────────────────────────────
# 6. HEATMAP RÉGION × ESPÈCE
# ─────────────────────────────────────────────

def plot_heatmap_region_espece(fact: pd.DataFrame):
    essais_u = fact.drop_duplicates("LK_EXPERIMENT_EXPERIMENT_ID")
    pivot = essais_u.groupby(["REGION", "ESPECE_FR"]).size().unstack(fill_value=0)
    if pivot.empty or pivot.shape[0] == 0 or pivot.shape[1] == 0:
        print("  Heatmap région×espèce : données insuffisantes, ignoré.")
        return
    top_reg = pivot.sum(axis=1).nlargest(15).index
    pivot = pivot.loc[top_reg]
    fig, ax = plt.subplots(figsize=(12, 6))
    sns.heatmap(pivot, annot=True, fmt="d", cmap="Blues", linewidths=0.5,
                ax=ax, cbar_kws={"label": "Nombre d'essais"})
    ax.set_title("Nombre d'essais par région et espèce (top 15 régions)", fontweight="bold")
    ax.set_xlabel("Espèce")
    ax.set_ylabel("Région")
    plt.tight_layout()
    save_fig("06_heatmap_region_espece")


# ─────────────────────────────────────────────
# 7. HEATMAP CORRÉLATIONS (première espèce disponible)
# ─────────────────────────────────────────────

def plot_correlation_heatmap(fact: pd.DataFrame):
    corr_path = os.path.join(REPORT_DIR, "correlations.json")
    if not os.path.exists(corr_path):
        return
    with open(corr_path, encoding="utf-8") as f:
        corr_data = json.load(f)

    for espece, corr_dict in corr_data.items():
        corr_df = pd.DataFrame(corr_dict)
        if len(corr_df) < 2:
            continue
        # Garder max 15 traits
        if len(corr_df) > 15:
            corr_df = corr_df.iloc[:15, :15]
        mask = np.triu(np.ones_like(corr_df, dtype=bool), k=1)
        fig, ax = plt.subplots(figsize=(max(8, len(corr_df) * 0.7), max(6, len(corr_df) * 0.65)))
        sns.heatmap(corr_df, annot=True, fmt=".2f", cmap="RdBu_r", vmin=-1, vmax=1,
                    mask=mask, ax=ax, linewidths=0.3,
                    cbar_kws={"label": "Corrélation de Pearson"})
        ax.set_title(f"Corrélations entre traits — {espece}", fontweight="bold")
        plt.tight_layout()
        name = espece.replace(" ", "_").replace("/", "_")
        save_fig(f"07_correlation_{name}")
        break  # Générer seulement pour la première espèce avec données suffisantes


# ─────────────────────────────────────────────
# 8. TOP MATÉRIELS (barres horizontales)
# ─────────────────────────────────────────────

def plot_top_materiels(fact: pd.DataFrame):
    top_path = os.path.join(ENRICH_DIR, "top_materiels.csv")
    if not os.path.exists(top_path):
        return
    top = pd.read_csv(top_path, sep=";")
    if top.empty:
        return
    top = top.head(15).sort_values("mean")
    colors = [PALETTE.get(sp, "#888") for sp in top["ESPECE_FR"]]
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.barh(top["MAIN_NAME"], top["mean"], color=colors, edgecolor="white")
    for bar, val in zip(bars, top["mean"]):
        ax.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height() / 2,
                f"{val:.1f}", va="center", fontsize=9)
    ax.set_xlabel("Valeur moyenne du trait")
    ax.set_title("Top 15 matériels les plus performants", fontweight="bold")
    plt.tight_layout()
    save_fig("08_top_materiels")


# ─────────────────────────────────────────────
# 9. CARTE GÉOGRAPHIQUE INTERACTIVE
# ─────────────────────────────────────────────

def plot_carte_essais(fact: pd.DataFrame):
    base_cols = ["LK_EXPERIMENT_EXPERIMENT_ID", "ESPECE_FR", "YEAR",
                 "CULTURE_UNIT", "REGION", "LAT", "LON"]
    available = [c for c in base_cols if c in fact.columns]
    essais = fact.drop_duplicates("LK_EXPERIMENT_EXPERIMENT_ID")[available].copy()
    essais = essais[essais["LAT"].notna() & essais["LON"].notna()]
    essais = essais[essais["LAT"].between(40, 55) & essais["LON"].between(-5, 12)]

    if essais.empty:
        print("  Aucune coordonnée valide pour la carte.")
        return

    center_lat = essais["LAT"].mean()
    center_lon = essais["LON"].mean()
    m = folium.Map(location=[center_lat, center_lon], zoom_start=6, tiles="CartoDB positron")

    icon_colors = {
        "Maïs": "orange", "Tournesol": "beige", "Blé tendre": "green",
        "Triticale": "blue", "Colza": "purple", "Blé dur/Orge": "gray",
    }

    cluster = MarkerCluster(name="Essais").add_to(m)
    for _, row in essais.iterrows():
        color = icon_colors.get(str(row["ESPECE_FR"]), "lightblue")
        popup_html = f"""
        <b>Essai :</b> {row['LK_EXPERIMENT_EXPERIMENT_ID']}<br>
        <b>Espèce :</b> {row.get('ESPECE_FR', 'N/A')}<br>
        <b>Année :</b> {row.get('YEAR', 'N/A')}<br>
        <b>Site :</b> {row.get('CULTURE_UNIT', 'N/A')}<br>
        <b>Région :</b> {row.get('REGION', 'N/A')}
        """
        folium.Marker(
            location=[row["LAT"], row["LON"]],
            popup=folium.Popup(popup_html, max_width=280),
            tooltip=f"{row['ESPECE_FR']} – {row['YEAR']}",
            icon=folium.Icon(color=color, icon="leaf", prefix="fa"),
        ).add_to(cluster)

    folium.LayerControl().add_to(m)

    out = os.path.join(REPORT_DIR, "carte_essais.html")
    m.save(out)
    print(f"  Carte interactive : reports/carte_essais.html  ({len(essais)} points)")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def run():
    print("=" * 80)
    print("  PHASE 4 — VISUALISATIONS")
    print("=" * 80)
    setup_dirs()

    print("\nChargement de la table de faits...")
    fact = pd.read_parquet(os.path.join(ENRICH_DIR, "fact_table.parquet"))
    print(f"  {len(fact):,} lignes")

    print("\nGénération des graphiques...")
    plot_essais_especes(fact)
    plot_essais_annee(fact)
    plot_boxplot_rendement(fact)
    plot_evolution_annuelle(fact)
    plot_top_regions(fact)
    plot_heatmap_region_espece(fact)
    plot_correlation_heatmap(fact)
    plot_top_materiels(fact)

    print("\nGénération de la carte géographique...")
    plot_carte_essais(fact)

    print("\n  Visualisations terminées.")


if __name__ == "__main__":
    run()
