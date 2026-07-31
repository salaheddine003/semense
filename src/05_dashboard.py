"""
Phase 5 — Dashboard HTML interactif
Génère un rapport complet en HTML avec statistiques, graphiques et carte intégrés.
"""

import os
import json
import base64
import pandas as pd
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENRICH_DIR = os.path.join(BASE_DIR, "data", "enriched")
REPORT_DIR = os.path.join(BASE_DIR, "reports")
IMG_DIR = os.path.join(REPORT_DIR, "images")


def img_to_b64(path: str) -> str:
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def load_kpi() -> dict:
    p = os.path.join(REPORT_DIR, "kpi_globaux.json")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {}


def load_prediction() -> dict:
    p = os.path.join(REPORT_DIR, "prediction_report.json")
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {}


def load_anova() -> str:
    p = os.path.join(ENRICH_DIR, "anova_region.csv")
    if not os.path.exists(p):
        return ""
    df = pd.read_csv(p, sep=";")
    return df.to_html(index=False, classes="table table-sm table-striped", border=0)


def load_top_mat() -> str:
    p = os.path.join(ENRICH_DIR, "top_materiels.csv")
    if not os.path.exists(p):
        return ""
    df = pd.read_csv(p, sep=";")
    df = df.rename(columns={"MAIN_NAME": "Matériel", "ESPECE_FR": "Espèce",
                             "TRAIT": "Trait", "count": "N", "mean": "Moyenne", "std": "Écart-type"})
    df["Moyenne"] = df["Moyenne"].round(2)
    df["Écart-type"] = df["Écart-type"].round(2)
    return df.to_html(index=False, classes="table table-sm table-striped", border=0)


def load_stats_table() -> str:
    p = os.path.join(ENRICH_DIR, "stats_espece_trait.csv")
    if not os.path.exists(p):
        return ""
    df = pd.read_csv(p, sep=";")
    df = df.head(50)
    return df.to_html(index=False, classes="table table-sm table-striped", border=0)


def load_regions_table() -> str:
    p = os.path.join(ENRICH_DIR, "essais_par_region.csv")
    if not os.path.exists(p):
        return ""
    df = pd.read_csv(p, sep=";")
    df = df.head(20)
    return df.to_html(index=False, classes="table table-sm table-striped", border=0)


def img_card(name: str, title: str, description: str = "") -> str:
    b64 = img_to_b64(os.path.join(IMG_DIR, f"{name}.png"))
    if not b64:
        return ""
    desc_html = f'<p class="text-muted small mt-1">{description}</p>' if description else ""
    return f"""
    <div class="col-md-6 mb-4">
      <div class="card shadow-sm h-100">
        <div class="card-body">
          <h6 class="card-title fw-bold">{title}</h6>
          {desc_html}
          <img src="data:image/png;base64,{b64}" class="img-fluid rounded" alt="{title}">
        </div>
      </div>
    </div>"""


def generate_dashboard():
    kpi = load_kpi()
    prediction = load_prediction()
    pred_metrics = prediction.get("metrics", {})
    class_report = prediction.get("classification_evaluation", {})
    class_metrics = class_report.get("metrics", {})
    now = datetime.now().strftime("%d/%m/%Y à %H:%M")

    annees = kpi.get("annees_couvertes", [])
    annees_str = f"{min(annees)} – {max(annees)}" if annees else "N/A"

    especes_list = kpi.get("especes", {})
    especes_badges = " ".join(
        f'<span class="badge bg-success me-1">{k} ({v})</span>'
        for k, v in list(especes_list.items())[:8]
    )

    HTML = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Semences — Plateforme d'analyse Big Data</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ background: #f4f6f9; font-family: 'Segoe UI', sans-serif; }}
    body {{ margin: 0; color: #212529; }}
    .container {{ width: min(1180px, calc(100% - 32px)); margin: 0 auto; }}
    .row {{ display: flex; flex-wrap: wrap; margin: -6px; }}
    [class*="col-"] {{ padding: 6px; width: 100%; }}
    .col-6 {{ width: 50%; }} .col-12 {{ width: 100%; }}
    @media (min-width: 768px) {{
      .col-md-1 {{ width: 8.333%; }} .col-md-2 {{ width: 16.666%; }}
      .col-md-3 {{ width: 25%; }} .col-md-4 {{ width: 33.333%; }}
      .col-md-6 {{ width: 50%; }}
    }}
    .navbar {{ background: linear-gradient(135deg, #1a3a2a 0%, #2d6a4f 100%); }}
    .navbar-brand {{ color: white; }}
    .hero {{ background: linear-gradient(135deg, #2d6a4f 0%, #40916c 50%, #52b788 100%);
             color: white; padding: 3rem 0 2rem; }}
    .kpi-card {{ border-left: 4px solid #40916c; }}
    .kpi-value {{ font-size: 2rem; font-weight: 700; color: #2d6a4f; }}
    .section-title {{ border-left: 4px solid #52b788; padding-left: 1rem;
                      margin: 2rem 0 1rem; color: #1a3a2a; }}
    .table thead {{ background-color: #2d6a4f; color: white; }}
    .badge {{ font-size: 0.85rem; }}
    .map-container {{ border-radius: 8px; overflow: hidden; border: 1px solid #dee2e6; }}
    footer {{ background: #1a3a2a; color: #adb5bd; }}
    .card {{ background: white; border: none; border-radius: 8px; }}
    .p-3 {{ padding: 1rem; }} .p-4 {{ padding: 1.5rem; }}
    .py-2 {{ padding-block: .5rem; }} .py-3 {{ padding-block: 1rem; }}
    .mt-1 {{ margin-top: .25rem; }} .mt-2 {{ margin-top: .5rem; }}
    .mt-3 {{ margin-top: 1rem; }} .mt-4 {{ margin-top: 1.5rem; }} .mt-5 {{ margin-top: 3rem; }}
    .mb-1 {{ margin-bottom: .25rem; }} .mb-2 {{ margin-bottom: .5rem; }}
    .mb-3 {{ margin-bottom: 1rem; }} .mb-4 {{ margin-bottom: 1.5rem; }}
    .text-center {{ text-align: center; }} .text-muted {{ color: #667085; }} .text-white-50 {{ color: #d2ded7; }}
    .small {{ font-size: .875rem; }} .fw-bold {{ font-weight: 700; }}
    .display-5 {{ font-size: 2.5rem; }} .lead {{ font-size: 1.15rem; }}
    .shadow-sm {{ box-shadow: 0 2px 8px rgba(20,40,30,.10); }}
    .badge {{ display:inline-block; padding:.35rem .55rem; border-radius:4px; color:white; background:#287a50; }}
    .bg-primary {{ background:#2463a8; }} .bg-success {{ background:#287a50; }}
    .bg-warning {{ background:#e0a000; color:#17200f; }} .bg-light {{ background:#f1f3f5; }}
    .table-responsive {{ overflow-x:auto; }} table {{ width:100%; border-collapse:collapse; background:white; }}
    th, td {{ padding:.55rem .7rem; border-bottom:1px solid #dee2e6; text-align:left; }}
    .nav {{ display:flex; flex-wrap:wrap; gap:4px; padding:0; list-style:none; }}
    .nav-link {{ border:1px solid #ccd5cf; background:white; padding:.65rem .9rem; cursor:pointer; }}
    .nav-link.active {{ color:white; background:#2d6a4f; }}
    .tab-pane {{ display:none; }} .tab-pane.active {{ display:block; }}
    .table-filter {{ width:min(420px,100%); padding:.65rem; border:1px solid #aeb8b2; margin-bottom:1rem; }}
  </style>
</head>
<body>

<!-- NAVBAR -->
<nav class="navbar navbar-dark py-2">
  <div class="container">
    <span class="navbar-brand fw-bold fs-5">
      <i class="fa-solid fa-seedling me-2"></i>Plateforme Big Data – Semences
    </span>
    <span class="text-white-50 small">Rapport généré le {now}</span>
  </div>
</nav>

<!-- HERO -->
<div class="hero">
  <div class="container">
    <h1 class="display-5 fw-bold mb-1">Analyse Culturale & Génétique</h1>
    <p class="lead opacity-75">Système de prédiction culturale — Pôle R&D</p>
    <div class="mt-2">{especes_badges}</div>
  </div>
</div>

<!-- KPIs -->
<div class="container mt-4">
  <div class="row g-3">
    <div class="col-6 col-md-3">
      <div class="card kpi-card p-3 shadow-sm text-center">
        <div class="kpi-value">{kpi.get('nb_essais', 0):,}</div>
        <div class="text-muted small"><i class="fa fa-flask me-1"></i>Essais</div>
      </div>
    </div>
    <div class="col-6 col-md-3">
      <div class="card kpi-card p-3 shadow-sm text-center">
        <div class="kpi-value">{kpi.get('nb_materiels', 0):,}</div>
        <div class="text-muted small"><i class="fa fa-dna me-1"></i>Matériels génétiques</div>
      </div>
    </div>
    <div class="col-6 col-md-3">
      <div class="card kpi-card p-3 shadow-sm text-center">
        <div class="kpi-value">{kpi.get('nb_mesures', 0):,}</div>
        <div class="text-muted small"><i class="fa fa-chart-bar me-1"></i>Mesures collectées</div>
      </div>
    </div>
    <div class="col-6 col-md-3">
      <div class="card kpi-card p-3 shadow-sm text-center">
        <div class="kpi-value">{kpi.get('nb_traits', 0)}</div>
        <div class="text-muted small"><i class="fa fa-tags me-1"></i>Traits mesurés</div>
      </div>
    </div>
    <div class="col-6 col-md-3">
      <div class="card kpi-card p-3 shadow-sm text-center">
        <div class="kpi-value">{kpi.get('nb_especes', 0)}</div>
        <div class="text-muted small"><i class="fa fa-leaf me-1"></i>Espèces</div>
      </div>
    </div>
    <div class="col-6 col-md-3">
      <div class="card kpi-card p-3 shadow-sm text-center">
        <div class="kpi-value">{kpi.get('nb_regions', 0)}</div>
        <div class="text-muted small"><i class="fa fa-map me-1"></i>Régions</div>
      </div>
    </div>
    <div class="col-12 col-md-6">
      <div class="card kpi-card p-3 shadow-sm text-center">
        <div class="kpi-value fs-3">{annees_str}</div>
        <div class="text-muted small"><i class="fa fa-calendar me-1"></i>Période couverte</div>
      </div>
    </div>
  </div>

  <!-- GRAPHIQUES -->
  <h2 class="section-title mt-5"><i class="fa fa-wand-magic-sparkles me-2"></i>Prédiction culturale</h2>
  <div class="row g-3 mb-4">
    <div class="col-md-3"><div class="card kpi-card p-3 shadow-sm text-center">
      <div class="kpi-value">{pred_metrics.get('mae', 'N/A')}</div><div class="text-muted small">MAE test temporel</div>
    </div></div>
    <div class="col-md-3"><div class="card kpi-card p-3 shadow-sm text-center">
      <div class="kpi-value">{pred_metrics.get('rmse', 'N/A')}</div><div class="text-muted small">RMSE test temporel</div>
    </div></div>
    <div class="col-md-3"><div class="card kpi-card p-3 shadow-sm text-center">
      <div class="kpi-value">{pred_metrics.get('r2', 'N/A')}</div><div class="text-muted small">R²</div>
    </div></div>
    <div class="col-md-3"><div class="card kpi-card p-3 shadow-sm text-center">
      <div class="kpi-value">{prediction.get('test_year', 'N/A')}</div><div class="text-muted small">Année de validation</div>
    </div></div>
  </div>
  <div class="row g-3 mb-4">
    <div class="col-md-3"><div class="card kpi-card p-3 shadow-sm text-center">
      <div class="kpi-value">{class_metrics.get('accuracy', 'N/A')}</div><div class="text-muted small">Accuracy 2018 sans fuite</div>
    </div></div>
    <div class="col-md-3"><div class="card kpi-card p-3 shadow-sm text-center">
      <div class="kpi-value">{class_metrics.get('precision', 'N/A')}</div><div class="text-muted small">Précision</div>
    </div></div>
    <div class="col-md-3"><div class="card kpi-card p-3 shadow-sm text-center">
      <div class="kpi-value">{class_metrics.get('recall', 'N/A')}</div><div class="text-muted small">Rappel</div>
    </div></div>
    <div class="col-md-3"><div class="card kpi-card p-3 shadow-sm text-center">
      <div class="kpi-value">{class_metrics.get('f1_score', 'N/A')}</div><div class="text-muted small">F1-score</div>
    </div></div>
  </div>
  <p class="text-muted small">
    Validation officielle : GroupKFold par essai sur 2015–2017, test temporel
    final 2018, aucun essai partagé et variables de fuite exclues.
  </p>

  <h2 class="section-title mt-5"><i class="fa fa-chart-pie me-2"></i>Répartition & distribution</h2>
  <div class="row">
    {img_card("01_essais_par_espece", "Essais par espèce", "Nombre total d'essais réalisés pour chaque espèce cultivée.")}
    {img_card("02_essais_par_annee", "Évolution temporelle des essais", "Nombre d'essais réalisés chaque année.")}
    {img_card("05_top_regions", "Top 15 régions by nb d'essais", "Régions les plus actives dans le programme d'essais.")}
    {img_card("06_heatmap_region_espece", "Heatmap région × espèce", "Intensité des essais par combinaison région/espèce.")}
  </div>

  <h2 class="section-title"><i class="fa fa-chart-line me-2"></i>Performances culturales</h2>
  <div class="row">
    {img_card("03_boxplot_rendement_espece", "Distribution des valeurs par espèce", "Médiane, quartiles et outliers des mesures de rendement/humidité.")}
    {img_card("04_evolution_annuelle", "Évolution annuelle par espèce", "Tendance des valeurs moyennées année par année.")}
    {img_card("07_correlation_Bl_tendre", "Corrélations inter-traits — Blé tendre", "Matrice de corrélation de Pearson entre les traits mesurés.")}
    {img_card("08_top_materiels", "Top 15 matériels performants", "Matériels génétiques avec les meilleures performances moyennes.")}
  </div>

  <!-- CARTE -->
  <h2 class="section-title"><i class="fa fa-map-location-dot me-2"></i>Géolocalisation des essais</h2>
  <p class="text-muted small">La carte contient 424 marqueurs locaux mais nécessite Internet pour charger Leaflet et les tuiles CARTO.</p>
  <div class="map-container mb-4">
    <iframe src="carte_essais.html" width="100%" height="520" frameborder="0"
            style="border:0;" allowfullscreen title="Carte des essais"></iframe>
  </div>

  <!-- TABLEAUX -->
  <h2 class="section-title"><i class="fa fa-table me-2"></i>Statistiques détaillées</h2>
  <label for="tableFilter" class="small fw-bold">Filtrer les lignes affichées</label><br>
  <input id="tableFilter" class="table-filter" type="search" placeholder="Espèce, région, trait ou matériel">

  <ul class="nav nav-tabs mb-3" id="statsTabs" role="tablist">
    <li class="nav-item"><button class="nav-link active" data-bs-toggle="tab" data-bs-target="#tab-stats">Stats espèce × trait</button></li>
    <li class="nav-item"><button class="nav-link" data-bs-toggle="tab" data-bs-target="#tab-mat">Top matériels</button></li>
    <li class="nav-item"><button class="nav-link" data-bs-toggle="tab" data-bs-target="#tab-reg">Essais par région</button></li>
    <li class="nav-item"><button class="nav-link" data-bs-toggle="tab" data-bs-target="#tab-anova">ANOVA région</button></li>
  </ul>
  <div class="tab-content">
    <div class="tab-pane fade show active" id="tab-stats">
      <div class="table-responsive">{load_stats_table()}</div>
    </div>
    <div class="tab-pane fade" id="tab-mat">
      <div class="table-responsive">{load_top_mat()}</div>
    </div>
    <div class="tab-pane fade" id="tab-reg">
      <div class="table-responsive">{load_regions_table()}</div>
    </div>
    <div class="tab-pane fade" id="tab-anova">
      <p class="text-muted small">Test ANOVA one-way : l'effet région sur le rendement est-il significatif ? (p &lt; 0.05 = oui)</p>
      <div class="table-responsive">{load_anova()}</div>
    </div>
  </div>

  <!-- ARCHITECTURE -->
  <h2 class="section-title mt-4"><i class="fa fa-diagram-project me-2"></i>Architecture de la solution</h2>
  <div class="card shadow-sm p-4 mb-4">
    <div class="row text-center">
      <div class="col-md-2">
        <div class="bg-light rounded p-3 mb-2">
          <i class="fa fa-file-csv fa-2x text-success"></i>
          <div class="small fw-bold mt-1">Sources CSV</div>
          <div class="text-muted" style="font-size:0.75rem">6 fichiers bruts</div>
        </div>
      </div>
      <div class="col-md-1 d-flex align-items-center justify-content-center">
        <i class="fa fa-arrow-right fa-lg text-muted"></i>
      </div>
      <div class="col-md-2">
        <div class="bg-light rounded p-3 mb-2">
          <i class="fa fa-broom fa-2x text-primary"></i>
          <div class="small fw-bold mt-1">ETL/Nettoyage</div>
          <div class="text-muted" style="font-size:0.75rem">Typage, jointures, Parquet</div>
        </div>
      </div>
      <div class="col-md-1 d-flex align-items-center justify-content-center">
        <i class="fa fa-arrow-right fa-lg text-muted"></i>
      </div>
      <div class="col-md-2">
        <div class="bg-light rounded p-3 mb-2">
          <i class="fa fa-database fa-2x text-warning"></i>
          <div class="small fw-bold mt-1">Data Lake</div>
          <div class="text-muted" style="font-size:0.75rem">Raw / Transformed / Enriched</div>
        </div>
      </div>
      <div class="col-md-1 d-flex align-items-center justify-content-center">
        <i class="fa fa-arrow-right fa-lg text-muted"></i>
      </div>
      <div class="col-md-2">
        <div class="bg-light rounded p-3 mb-2">
          <i class="fa fa-magnifying-glass-chart fa-2x text-danger"></i>
          <div class="small fw-bold mt-1">Analyse</div>
          <div class="text-muted" style="font-size:0.75rem">Python + R + ANOVA</div>
        </div>
      </div>
      <div class="col-md-1 d-flex align-items-center justify-content-center">
        <i class="fa fa-arrow-right fa-lg text-muted"></i>
      </div>
    </div>
    <div class="row text-center mt-2">
      <div class="col-12">
        <div class="bg-success bg-opacity-10 border border-success rounded p-3">
          <i class="fa fa-gauge-high fa-2x text-success"></i>
          <div class="small fw-bold mt-1">Dashboard & Reporting</div>
          <div class="text-muted" style="font-size:0.75rem">Tableau de bord HTML local • Carte Folium avec accès Internet</div>
        </div>
      </div>
    </div>
    <div class="row mt-3">
      <div class="col-12">
        <h6 class="fw-bold">Choix technologiques</h6>
        <div class="row g-2">
          <div class="col-md-4"><span class="badge bg-primary me-1">Pandas</span> Manipulation & ETL</div>
          <div class="col-md-4"><span class="badge bg-primary me-1">Apache Parquet</span> Stockage colonnaire (Big Data)</div>
          <div class="col-md-4"><span class="badge bg-primary me-1">Folium/Leaflet</span> Géolocalisation interactive</div>
          <div class="col-md-4"><span class="badge bg-success me-1">R / ggplot2</span> Analyse statistique avancée</div>
          <div class="col-md-4"><span class="badge bg-success me-1">SciPy ANOVA</span> Tests statistiques</div>
          <div class="col-md-4"><span class="badge bg-success me-1">Seaborn / Matplotlib</span> Visualisation</div>
          <div class="col-md-4"><span class="badge bg-warning text-dark me-1">Kafka</span> Adaptation fonctionnelle locale</div>
          <div class="col-md-4"><span class="badge bg-warning text-dark me-1">NiFi</span> Adaptation fonctionnelle locale</div>
          <div class="col-md-4"><span class="badge bg-warning text-dark me-1">HDFS</span> Adaptation fonctionnelle locale sur fichiers</div>
        </div>
      </div>
    </div>
  </div>

</div>

<footer class="py-3 mt-4 text-center">
  <small>Pôle R&D — Système de prédiction culturale · Généré le {now}</small>
</footer>

<script>
document.querySelectorAll('[data-bs-target]').forEach(function(button) {{
  button.addEventListener('click', function() {{
    document.querySelectorAll('.nav-link').forEach(function(x) {{ x.classList.remove('active'); }});
    document.querySelectorAll('.tab-pane').forEach(function(x) {{ x.classList.remove('active'); }});
    button.classList.add('active');
    document.querySelector(button.dataset.bsTarget).classList.add('active');
  }});
}});
document.getElementById('tableFilter').addEventListener('input', function(event) {{
  var term = event.target.value.toLowerCase();
  document.querySelectorAll('.tab-pane tbody tr').forEach(function(row) {{
    row.style.display = row.textContent.toLowerCase().includes(term) ? '' : 'none';
  }});
}});
</script>
</body>
</html>"""

    out = os.path.join(REPORT_DIR, "dashboard.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(HTML)
    print(f"  Dashboard généré : reports/dashboard.html")


def run():
    print("=" * 80)
    print("  PHASE 5 — GÉNÉRATION DU DASHBOARD HTML")
    print("=" * 80)
    generate_dashboard()
    print("  Dashboard terminé.")


if __name__ == "__main__":
    run()
