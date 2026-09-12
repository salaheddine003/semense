"""Check prerequisites without changing files or starting the pipeline."""

import argparse
import importlib.metadata
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    "ESSAI.csv", "RESULTAT_ESSAIS.csv", "LK_CRISP_MATERIAL_20190108.csv",
    "PARCELLE_SPECIFICATION_20190108.csv", "REF_ESPECES_20190108.csv",
    "TRIAL_QUALIFICATION_20190108.csv",
)
DEMO_FILES = (
    "INDEX.html", "site.css", "og.png", "reports/dashboard.html",
    "reports/dashboard.js", "reports/carte_essais.html",
    "data/enriched/stats_espece_trait.csv", "data/enriched/top_materiels.csv",
    "data/enriched/essais_par_region.csv", "data/enriched/anova_region.csv",
)


def executable_works(executable):
    try:
        result = subprocess.run(
            [executable, "-version" if Path(executable).stem.lower() == "java" else "--version"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def main(argv=None):
    parser = argparse.ArgumentParser(description="Diagnostic local du projet Semences")
    parser.add_argument("--demo", action="store_true", help="vérifier uniquement la consultation des résultats")
    parser.add_argument("--strict-spark", action="store_true", help="exiger Java pour viser une exécution PySpark")
    args = parser.parse_args(argv)
    if args.demo and args.strict_spark:
        parser.error("--strict-spark concerne le pipeline complet, pas --demo")
    failures = []

    def check(ok, message, hint="", optional=False):
        status = "OK" if ok else "ATTENTION" if optional else "MANQUANT"
        print(f"[{status}] {message}")
        if not ok:
            if hint:
                print(f"  -> {hint}")
            if not optional:
                failures.append(message)

    print(f"Projet : {ROOT}")
    print(f"Python : {sys.executable}")
    for relative in DEMO_FILES:
        check((ROOT / relative).is_file(), relative, "Récupérer le dépôt ou l'archive avec ses résultats.")
    if not args.demo:
        check(sys.version_info[:2] == (3, 12), "Python 3.12 (version vérifiée)", "Créer .venv avec Python 3.12.")
        requirements = ROOT / "requirements.txt"
        check(requirements.is_file(), "requirements.txt", "Récupérer le fichier des dépendances.")
        if requirements.is_file():
            for entry in requirements.read_text(encoding="utf-8-sig").splitlines():
                if not entry.strip() or entry.lstrip().startswith("#"):
                    continue
                package, expected = entry.strip().split("==", 1)
                try:
                    actual = importlib.metadata.version(package)
                except importlib.metadata.PackageNotFoundError:
                    check(False, package, "Installer : python -m pip install -r requirements.txt")
                else:
                    check(actual == expected, f"{package} {actual} (attendu : {expected})",
                          "Aligner les versions avec requirements.txt pour reproduire les résultats.", optional=True)
        for name in SOURCES:
            check((ROOT / "CSV" / name).is_file(), f"Source {name}", "Restaurer le dossier CSV complet.")
        sys.path.insert(0, str(ROOT))
        from importlib import import_module
        rscript = import_module("src.15_r_integration").find_rscript()
        check(bool(rscript) and executable_works(rscript), "Rscript accessible",
              "Installer R >= 4.3 et rendre Rscript accessible au pipeline.")
        java = shutil.which("java")
        check(bool(java) and executable_works(java), "Java accessible pour PySpark",
              "Installer Java 11 et vérifier le PATH / JAVA_HOME. Sans Java, le pipeline utilise pandas.",
              optional=not args.strict_spark)
        check((ROOT / "deliverables/presentation_semences.pptx").is_file(), "Présentation maintenue",
              "Récupérer deliverables/presentation_semences.pptx, requis par la phase 16.")

    if failures:
        print(f"\n{len(failures)} prérequis manquant(s). Corriger les points ci-dessus puis relancer.")
        return 1
    print("\nPrérequis détectés. Ce diagnostic ne remplace pas le pipeline et ses tests.")
    if args.demo:
        print("Depuis la racine : python -m http.server 8000 --bind 127.0.0.1")
        print("Ouvrir : http://127.0.0.1:8000/INDEX.html")
    else:
        print("Étape suivante : python -X utf8 main.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
