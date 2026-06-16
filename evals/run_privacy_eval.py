from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "evals" / ".tmp" / "privacy"


def main() -> int:
    if OUTPUT_ROOT.exists():
        shutil.rmtree(OUTPUT_ROOT)
    source_dir = OUTPUT_ROOT / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    (source_dir / "capture.json").write_text(
        json.dumps(
            {
                "visible_text": "Contact privacy@example.test for review.",
                "tokens": "sk_example1234567890",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    command = [
        sys.executable,
        str(ROOT / "scripts" / "privacy_report_runner.py"),
        str(source_dir),
        "--output-root",
        str(OUTPUT_ROOT),
        "--run-id",
        "eval-privacy-report",
    ]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    errors: list[str] = []
    if completed.returncode == 0:
        errors.append("privacy runner returned success despite forbidden key")
    report = json.loads((OUTPUT_ROOT / "eval-privacy-report" / "artifacts" / "privacy-report.json").read_text(encoding="utf-8"))
    codes = "\n".join(item["code"] for item in report.get("findings", []))
    if "PRIVACY_FORBIDDEN_KEY:tokens" not in codes:
        errors.append("privacy report missing forbidden token key finding")
    if "PRIVACY_PRIVATE_TEXT:email_address" not in codes:
        errors.append("privacy report missing email finding")
    if errors:
        print("FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
