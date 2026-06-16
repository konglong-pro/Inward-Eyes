from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "evals" / ".tmp" / "adapter-matrix"


def main() -> int:
    if OUTPUT_ROOT.exists():
        shutil.rmtree(OUTPUT_ROOT)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(ROOT / "scripts" / "adapter_matrix_runner.py"),
        "--output-root",
        str(OUTPUT_ROOT),
        "--run-id",
        "eval-adapter-matrix",
    ]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    errors: list[str] = []
    if completed.returncode != 0:
        errors.append(f"adapter matrix runner failed: {completed.stderr.strip()} {completed.stdout.strip()}".strip())
    run_dir = OUTPUT_ROOT / "eval-adapter-matrix"
    matrix = json.loads((run_dir / "artifacts" / "adapter-matrix.json").read_text(encoding="utf-8"))
    report = json.loads((run_dir / "validation" / "adapter-matrix-report.json").read_text(encoding="utf-8"))
    adapter_ids = {adapter["adapter_id"] for adapter in matrix.get("adapters", [])}
    required = {
        "local_html_input",
        "page_capture_json_input",
        "playwright_mcp_public_url",
        "current_chrome_visible_page",
        "research_provided_url_capture",
        "research_small_scope_discovery",
        "price_product_url_capture",
        "price_candidate_discovery",
    }
    missing = sorted(required - adapter_ids)
    if missing:
        errors.append(f"adapter matrix missing ids: {missing}")
    if report["status"] != "pass":
        errors.append(f"adapter matrix validation failed: {report['errors']}")
    if errors:
        print("FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
