from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "evals" / ".tmp" / "review-ui"
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
        "eval-review-source",
        "--page-type",
        "article",
    ]
    page_completed = subprocess.run(page_command, cwd=ROOT, text=True, capture_output=True)
    if page_completed.returncode != 0:
        errors.append(f"page fixture failed: {page_completed.stderr.strip()}")
    review_command = [
        sys.executable,
        str(ROOT / "scripts" / "review_run.py"),
        str(OUTPUT_ROOT / "eval-review-source"),
    ]
    review_completed = subprocess.run(review_command, cwd=ROOT, text=True, capture_output=True)
    if review_completed.returncode != 0:
        errors.append(f"review runner failed: {review_completed.stderr.strip()} {review_completed.stdout.strip()}".strip())
    review_md = OUTPUT_ROOT / "eval-review-source" / "review" / "review.md"
    if not review_md.exists():
        errors.append("review markdown missing")
    elif "Run status" not in review_md.read_text(encoding="utf-8"):
        errors.append("review markdown missing run status")
    if errors:
        print("FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
