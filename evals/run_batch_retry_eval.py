from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "evals" / ".tmp" / "batch-retry"
FIXTURE_ROOT = ROOT / "evals" / "fixtures" / "page-to-md"


def main() -> int:
    if OUTPUT_ROOT.exists():
        shutil.rmtree(OUTPUT_ROOT)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    spec_path = OUTPUT_ROOT / "batch-spec.json"
    spec_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "max_retries": 1,
                "jobs": [
                    {
                        "job_id": "article",
                        "task": "page-to-md",
                        "input": str(FIXTURE_ROOT / "public-article.html"),
                        "url": "https://example.test/public-article",
                        "page_type": "article",
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    command = [
        sys.executable,
        str(ROOT / "scripts" / "batch_runner.py"),
        "--spec",
        str(spec_path),
        "--output-root",
        str(OUTPUT_ROOT),
        "--run-id",
        "eval-batch",
    ]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    errors: list[str] = []
    if completed.returncode != 0:
        errors.append(f"batch runner failed: {completed.stderr.strip()} {completed.stdout.strip()}".strip())
    index_path = OUTPUT_ROOT / "eval-batch" / "artifacts" / "run-index.jsonl"
    if not index_path.exists() or not index_path.read_text(encoding="utf-8").strip():
        errors.append("batch run index missing or empty")
    db_index_path = OUTPUT_ROOT / "run-index.jsonl"
    db_command = [
        sys.executable,
        str(ROOT / "scripts" / "run_database.py"),
        "index",
        "--output-root",
        str(OUTPUT_ROOT),
        "--index",
        str(db_index_path),
    ]
    db_completed = subprocess.run(db_command, cwd=ROOT, text=True, capture_output=True)
    if db_completed.returncode != 0:
        errors.append(f"run database index failed: {db_completed.stderr.strip()}")
    retry_path = OUTPUT_ROOT / "retry-plan.json"
    retry_command = [
        sys.executable,
        str(ROOT / "scripts" / "run_database.py"),
        "retry-plan",
        "--index",
        str(db_index_path),
        "--output",
        str(retry_path),
    ]
    retry_completed = subprocess.run(retry_command, cwd=ROOT, text=True, capture_output=True)
    if retry_completed.returncode != 0:
        errors.append(f"retry plan failed: {retry_completed.stderr.strip()}")
    retry_plan = json.loads(retry_path.read_text(encoding="utf-8"))
    if not isinstance(retry_plan.get("retryable_runs"), list):
        errors.append("retry plan missing retryable_runs")
    if errors:
        print("FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
