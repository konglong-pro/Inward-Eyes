from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "evals" / ".tmp" / "real-world-style"


def main() -> int:
    if OUTPUT_ROOT.exists():
        shutil.rmtree(OUTPUT_ROOT)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    payload_path = OUTPUT_ROOT / "observed-docs-page.txt"
    payload_path.write_text(
        "Real World Replay Docs\n\n"
        "This deterministic replay fixture represents a captured public documentation page. "
        "The eval supplies observed text directly so the capture runner must not perform live browser fallback. "
        "Source evidence, timestamps, validation reports, and rendered Markdown remain traceable.",
        encoding="utf-8",
    )
    capture_command = [
        sys.executable,
        str(ROOT / "scripts" / "capture" / "playwright_mcp_capture.py"),
        "--url",
        "https://example.test/docs/real-world-replay",
        "--page-title",
        "Real World Replay Docs",
        "--selected-main-content-file",
        str(payload_path),
        "--output-root",
        str(OUTPUT_ROOT),
        "--run-id",
        "eval-real-world-replay-capture",
    ]
    capture_completed = subprocess.run(capture_command, cwd=ROOT, text=True, capture_output=True)
    if capture_completed.returncode != 0:
        errors.append(f"capture replay failed: {capture_completed.stderr.strip()} {capture_completed.stdout.strip()}".strip())
    capture_dir = OUTPUT_ROOT / "eval-real-world-replay-capture"
    capture_report = json.loads((capture_dir / "validation" / "capture-validation-report.json").read_text(encoding="utf-8"))
    joined_capture = "\n".join(capture_report.get("errors", []) + capture_report.get("warnings", []))
    if "playwright_capture_failed" in joined_capture:
        errors.append("capture replay attempted live Playwright fallback")
    page_command = [
        sys.executable,
        str(ROOT / "scripts" / "page_to_md_runner.py"),
        "--input",
        str(capture_dir / "capture" / "page_capture.json"),
        "--output-root",
        str(OUTPUT_ROOT),
        "--run-id",
        "eval-real-world-replay-page",
        "--page-type",
        "docs",
    ]
    page_completed = subprocess.run(page_command, cwd=ROOT, text=True, capture_output=True)
    if page_completed.returncode != 0:
        errors.append(f"page replay failed: {page_completed.stderr.strip()}")
    page_validation = json.loads(
        (OUTPUT_ROOT / "eval-real-world-replay-page" / "validation" / "validation-report.json").read_text(encoding="utf-8")
    )
    if page_validation["status"] != "pass":
        errors.append(f"page replay validation failed: {page_validation['errors']}")
    if errors:
        print("FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
