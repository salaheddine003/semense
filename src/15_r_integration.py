"""Execute the mandatory statistical analysis through Rscript."""

import json
import os
import shutil
import subprocess
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT_DIR = os.path.join(BASE_DIR, "reports")


def find_rscript():
    executable = shutil.which("Rscript")
    if executable:
        return executable
    root = os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "R")
    if os.path.isdir(root):
        versions = sorted(os.listdir(root), reverse=True)
        for version in versions:
            candidate = os.path.join(root, version, "bin", "Rscript.exe")
            if os.path.exists(candidate):
                return candidate
    return None


def run():
    print("=" * 80)
    print("  INTEGRATION R - statistiques accessibles au pôle R&D")
    print("=" * 80)
    rscript = find_rscript()
    report = {
        "status": "ERROR", "engine": "Rscript", "timestamp": datetime.now().isoformat(),
        "script": "R/analyse_pipeline.R", "outputs": [],
    }
    if not rscript:
        report["error"] = "Rscript introuvable. Installer R >= 4.3."
    else:
        command = [
            rscript, os.path.join(BASE_DIR, "R", "analyse_pipeline.R"),
            os.path.join(BASE_DIR, "data", "enriched", "fact_table.csv"),
            os.path.join(BASE_DIR, "reports", "r"),
        ]
        result = subprocess.run(
            command, cwd=BASE_DIR, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=300,
        )
        report.update({
            "status": "OK" if result.returncode == 0 else "ERROR",
            "rscript": os.path.basename(rscript), "return_code": result.returncode,
            "stdout": result.stdout[-4000:], "stderr": result.stderr[-4000:],
            "outputs": [
                "reports/r/stats_r.csv", "reports/r/anova_r.csv",
                "reports/r/rendement_espece_r.png",
            ],
        })
    os.makedirs(REPORT_DIR, exist_ok=True)
    with open(os.path.join(REPORT_DIR, "r_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    if report["status"] != "OK":
        raise RuntimeError(report.get("error") or report.get("stderr") or "Échec de R")
    print("  Analyse R exécutée; résultats dans reports/r/")
    return report


if __name__ == "__main__":
    run()
