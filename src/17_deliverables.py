"""Validate group deliverables without overwriting the presentation or dashboards."""
import json
from datetime import datetime
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET

BASE_DIR = Path(__file__).resolve().parents[1]
PPTX_PATH = BASE_DIR / "deliverables" / "presentation_semences.pptx"


def run():
    if not (BASE_DIR / "README.md").is_file():
        raise FileNotFoundError("README.md manquant")
    with zipfile.ZipFile(PPTX_PATH) as deck:
        if deck.testzip() is not None:
            raise RuntimeError("Présentation PowerPoint corrompue")
        document = ET.fromstring(deck.read("ppt/presentation.xml"))
        slides = document.findall(
            ".//{http://schemas.openxmlformats.org/presentationml/2006/main}sldId"
        )
    if len(slides) < 20:
        raise RuntimeError("La présentation détaillée doit contenir au moins 20 diapositives")
    report = {
        "status": "OK", "presentation": PPTX_PATH.relative_to(BASE_DIR).as_posix(),
        "readme": "README.md", "slides": len(slides),
        "mode": "validation des livrables maintenus, sans régénération",
        "timestamp": datetime.now().isoformat(),
    }
    report_dir = BASE_DIR / "reports"
    report_dir.mkdir(exist_ok=True)
    (report_dir / "deliverables_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  Livrables validés : README et présentation ({len(slides)} diapositives)")
    return report


if __name__ == "__main__":
    run()
