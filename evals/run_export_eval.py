from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "evals" / ".tmp" / "exports"
FIXTURE_ROOT = ROOT / "evals" / "fixtures" / "page-to-md"


def main() -> int:
    if OUTPUT_ROOT.exists():
        shutil.rmtree(OUTPUT_ROOT)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    page_command = [
        sys.executable,
        str(ROOT / "scripts" / "page_to_md_runner.py"),
        "--input",
        str(FIXTURE_ROOT / "public-article.html"),
        "--url",
        "https://example.test/public-article",
        "--output-root",
        str(OUTPUT_ROOT),
        "--run-id",
        "eval-export-source",
        "--page-type",
        "article",
    ]
    page_completed = subprocess.run(page_command, cwd=ROOT, text=True, capture_output=True)
    if page_completed.returncode != 0:
        errors.append(f"page fixture failed: {page_completed.stderr.strip()}")
    export_command = [
        sys.executable,
        str(ROOT / "scripts" / "export_run.py"),
        str(OUTPUT_ROOT / "eval-export-source"),
    ]
    export_completed = subprocess.run(export_command, cwd=ROOT, text=True, capture_output=True)
    if export_completed.returncode != 0:
        errors.append(f"export runner failed: {export_completed.stderr.strip()}")
    for relative in ("exports/run-summary.json", "exports/artifact-index.csv", "exports/run-summary.md"):
        if not (OUTPUT_ROOT / "eval-export-source" / relative).exists():
            errors.append(f"export missing {relative}")
    if errors:
        print("FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
