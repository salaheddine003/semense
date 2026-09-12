"""Create the group's submission archive with code, data and dashboards."""

from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT.parent / "SEMENCES_GROUPE.zip"
FILES = {
    "README.md", "requirements.txt", "main.py", "platform_api.py",
    "INDEX.html", "404.html", "site.css", "og.png", ".nojekyll", "_headers", ".gitignore",
    "deliverables/presentation_semences.pptx", "deliverables/architecture_big_data.png",
    "tools/prepare_submission.py", "tools/check_environment.py",
}
DIRECTORIES = {"src", "tests", "R", "docs", "CSV", "data", "catalog", "hbase", "hive", "drill", "kafka", "models", "reports"}


def selected_files():
    for item in sorted(ROOT.rglob("*")):
        if not item.is_file():
            continue
        relative = item.relative_to(ROOT)
        if any(part in {".git", ".venv", "__pycache__", ".build-presentation", "node_modules"} for part in relative.parts):
            continue
        if relative.as_posix() not in FILES and relative.parts[0] not in DIRECTORIES:
            continue
        if item.suffix.lower() in {".pdf", ".pyc", ".pyo", ".log", ".jsonl"}:
            continue
        if relative.parts[0] == "reports" and item.suffix.lower() in {".md", ".txt"}:
            continue
        yield item, relative


def main():
    temporary = ARCHIVE.with_suffix(".zip.tmp")
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for source, relative in selected_files():
                archive.write(source, "SEMENCES_GROUPE/" + relative.as_posix())
        with zipfile.ZipFile(temporary) as archive:
            if archive.testzip() is not None:
                raise RuntimeError("Archive corrompue")
        temporary.replace(ARCHIVE)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"Archive prête : {ARCHIVE} ({ARCHIVE.stat().st_size / 1024**2:.1f} Mo)")


if __name__ == "__main__":
    main()
