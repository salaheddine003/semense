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
    ax.set_title("Répartition des essais par catégorie", fontweight="bold")
    ax.invert_yaxis()
    plt.tight_layout()
    save_fig("01_essais_par_categorie")


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
    key = "LK_EXPERIMENT_EXPERIMENT_ID"
    base_cols = [key, "ESPECE_FR", "YEAR", "CULTURE_UNIT", "REGION", "LAT", "LON"]
    base = fact.drop_duplicates(key)[base_cols].copy()
    base = base[base["LAT"].notna() & base["LON"].notna()]
    base = base[base["LAT"].between(40, 55) & base["LON"].between(-5, 12)]
    if base.empty:
        print("  Aucune coordonnée valide pour la carte.")
        return
    counts = fact.groupby(key).size().rename("NB_MESURES")
    traits = fact.groupby(key)["TRAIT"].agg(lambda values: sorted(set(map(str, values.dropna())))).rename("TRAITS")
    essais = base.join(counts, on=key).join(traits, on=key)
    essais["PAYS"] = np.where(essais["REGION"].astype(str).str.upper().isin(["TOLNA", "BARANYA"]), "Hongrie", "France")
    records = []
    for _, row in essais.iterrows():
        records.append({
            "id": str(row[key]), "categorie": str(row.get("ESPECE_FR", "Non renseignée")),
            "annee": int(row["YEAR"]) if pd.notna(row["YEAR"]) else None,
            "site": str(row.get("CULTURE_UNIT", "Non renseigné")),
            "region": str(row.get("REGION", "Non renseignée")), "pays": str(row["PAYS"]),
            "lat": round(float(row["LAT"]), 6), "lon": round(float(row["LON"]), 6),
            "mesures": int(row["NB_MESURES"]), "traits": list(row["TRAITS"]),
        })
    data = json.dumps(records, ensure_ascii=False).replace("</", "<\\/")
    categories = json.dumps(sorted(essais["ESPECE_FR"].astype(str).unique()), ensure_ascii=False)
    years = json.dumps(sorted(int(v) for v in essais["YEAR"].dropna().unique()))
    regions = json.dumps(sorted(essais["REGION"].astype(str).unique()), ensure_ascii=False)
    trait_values = json.dumps(sorted({t for values in essais["TRAITS"] for t in values}), ensure_ascii=False)
    out = os.path.join(REPORT_DIR, "carte_essais.html")
    html = f'''<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Carte interactive des essais — Semences R&amp;D</title><meta name="description" content="Carte filtrable de 424 essais agronomiques en France et en Hongrie"><meta name="author" content="Salaheddine Abbar"><meta property="og:title" content="Carte des essais — Semences R&amp;D"><meta property="og:description" content="424 essais agronomiques filtrables en France et en Hongrie"><meta property="og:image" content="../og.png"><link rel="icon" type="image/png" href="../og.png"><link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css"><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.5.3/MarkerCluster.css"><link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.5.3/MarkerCluster.Default.css"><style>
*{{box-sizing:border-box}}html,body{{height:100%;margin:0;font:14px Inter,system-ui,-apple-system,"Segoe UI",sans-serif;background:#07110f;color:#eef7f2}}a,button,select{{font:inherit}}:focus-visible{{outline:3px solid #f2bd59;outline-offset:2px}}header{{min-height:72px;padding:10px 16px;display:flex;align-items:center;gap:14px;background:#07110f}}h1{{font-size:20px;margin:0}}header p{{margin:2px 0;color:#a9beb5}}.back,.link,button{{border:1px solid #29443a;border-radius:9px;padding:9px 11px;background:#142720;color:#eef7f2;text-decoration:none;cursor:pointer}}.back{{background:#55d68b;color:#092016;font-weight:800}}#counter{{margin-left:auto;font-weight:800}}.layout{{height:calc(100% - 72px);display:grid;grid-template-columns:310px 1fr}}aside{{padding:14px;background:#0f1d19;overflow:auto;border-right:1px solid #29443a}}label{{display:block;margin:10px 0 4px;font-weight:750}}select{{width:100%;padding:8px;border:1px solid #355347;border-radius:7px;background:#142720;color:#fff}}.check{{display:flex;gap:8px;align-items:center;font-weight:600}}.check input{{width:auto}}.actions{{display:flex;gap:8px;margin:14px 0;flex-wrap:wrap}}.info,.offline{{padding:10px;border-left:3px solid #69aef8;background:#13251f;margin-top:12px}}.offline{{border-color:#f2bd59}}.legend span{{display:block;margin:5px 0}}.dot{{display:inline-grid;place-items:center;width:18px;height:18px;border-radius:50%;background:#55d68b;color:#07110f;font-size:10px;font-weight:900;margin-right:6px}}#map{{height:100%;min-height:420px}}.leaflet-control-layers-base label{{color:#17211d}}@media(max-width:800px){{header{{flex-wrap:wrap}}#counter{{margin-left:0}}.layout{{height:auto;grid-template-columns:1fr}}aside{{border:0}}#map{{height:65vh}}}}
</style></head><body><header><a class="back" href="../INDEX.html">← Portail</a><div><h1>Carte interactive des essais</h1><p>Semences R&amp;D · France et Hongrie</p></div><strong id="counter" aria-live="polite">{len(records)} points affichés sur {len(records)}</strong><a class="link" href="dashboard.html">Dashboard</a></header><main class="layout"><aside aria-label="Filtres et légende"><h2>Filtrer les essais</h2><label for="category">Catégorie</label><select id="category"><option value="">Toutes</option></select><label for="year">Année</label><select id="year"><option value="">Toutes</option></select><label for="region">Région</label><select id="region"><option value="">Toutes</option></select><label for="country">Pays</label><select id="country"><option value="">Tous</option><option>France</option><option>Hongrie</option></select><label for="trait">Trait mesuré</label><select id="trait"><option value="">Tous</option></select><label class="check"><input id="franceOnly" type="checkbox"> Afficher uniquement la France</label><div class="actions"><button id="reset" type="button">Réinitialiser les filtres</button></div><div class="legend" aria-label="Légende"><h2>Légende</h2><span><i class="dot">1</i>Point individuel</span><span><i class="dot">12</i>Cluster : nombre d’essais regroupés</span><span>🇫🇷 France · 🇭🇺 Hongrie</span><span>Les essais sans coordonnées valides sont exclus de la carte.</span></div><div class="info"><strong>Pourquoi la Hongrie ?</strong><br>Le jeu de données inclut des essais français et hongrois. TOLNA et BARANYA sont conservées pour respecter la traçabilité des sources.</div><div class="offline" id="offline">La carte nécessite une connexion Internet. Les données restent disponibles dans le <a href="../data/enriched/essais_par_region.csv">tableau des régions</a>.</div></aside><div id="map" role="region" aria-label="Carte des essais géolocalisés"></div></main>
<script src="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js"></script><script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.5.3/leaflet.markercluster.js"></script><script>
const points={data},total=points.length,values={{category:{categories},year:{years},region:{regions},trait:{trait_values}}};
const esc=value=>String(value??'').replace(/[&<>"']/g,char=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[char]));
const selects={{category:document.querySelector('#category'),year:document.querySelector('#year'),region:document.querySelector('#region'),country:document.querySelector('#country'),trait:document.querySelector('#trait')}};
for(const [key,list] of Object.entries(values))for(const value of list)selects[key].insertAdjacentHTML('beforeend',`<option>${{esc(value)}}</option>`);
let map,cluster;const offline=document.querySelector('#offline');
if(window.L){{offline.hidden=true;map=L.map('map').setView([47.7,2.1],6);const tiles=L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png',{{attribution:'&copy; OpenStreetMap &copy; CARTO'}}).addTo(map);cluster=L.markerClusterGroup();map.addLayer(cluster);L.control.layers({{'Fond de carte clair':tiles}},{{'Essais géolocalisés':cluster}}).addTo(map);const zin=document.querySelector('.leaflet-control-zoom-in'),zout=document.querySelector('.leaflet-control-zoom-out');if(zin){{zin.title='Agrandir la carte';zin.setAttribute('aria-label','Agrandir la carte')}}if(zout){{zout.title='Réduire la carte';zout.setAttribute('aria-label','Réduire la carte')}}render()}}
function popup(p){{return `<b>Essai :</b> ${{esc(p.id)}}<br><b>Catégorie :</b> ${{esc(p.categorie)}}<br><b>Région :</b> ${{esc(p.region)}}<br><b>Pays :</b> ${{esc(p.pays)}}<br><b>Année :</b> ${{esc(p.annee)}}<br><b>Coordonnées :</b> ${{p.lat.toLocaleString('fr-FR')}}, ${{p.lon.toLocaleString('fr-FR')}}<br><b>Mesures :</b> ${{p.mesures.toLocaleString('fr-FR')}}<br><b>Traits :</b> ${{p.traits.map(esc).join(', ')}}`}}
function render(){{if(!cluster)return;cluster.clearLayers();const franceOnly=document.querySelector('#franceOnly').checked,filtered=points.filter(p=>(!selects.category.value||p.categorie===selects.category.value)&&(!selects.year.value||String(p.annee)===selects.year.value)&&(!selects.region.value||p.region===selects.region.value)&&(!selects.country.value||p.pays===selects.country.value)&&(!selects.trait.value||p.traits.includes(selects.trait.value))&&(!franceOnly||p.pays==='France'));for(const p of filtered)L.marker([p.lat,p.lon],{{title:`${{p.categorie}} — ${{p.region}}`}}).bindPopup(popup(p)).addTo(cluster);document.querySelector('#counter').textContent=`${{filtered.length.toLocaleString('fr-FR')}} points affichés sur ${{total.toLocaleString('fr-FR')}}`;if(filtered.length)map.fitBounds(cluster.getBounds(),{{padding:[25,25],maxZoom:9}})}}
Object.values(selects).forEach(select=>select.addEventListener('change',render));document.querySelector('#franceOnly').addEventListener('change',render);document.querySelector('#reset').onclick=()=>{{Object.values(selects).forEach(select=>select.value='');document.querySelector('#franceOnly').checked=false;render()}};
</script></body></html>'''
    with open(out, "w", encoding="utf-8") as handle:
        handle.write(html)
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
