from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "evals" / ".tmp" / "site-profiles"


def main() -> int:
    if OUTPUT_ROOT.exists():
        shutil.rmtree(OUTPUT_ROOT)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    schema_command = [
        sys.executable,
        str(ROOT / "scripts" / "validation" / "validate_json_schema.py"),
        "--schema",
        str(ROOT / "schemas" / "site_profiles.schema.json"),
        "--json",
        str(ROOT / "profiles" / "site_profiles.json"),
    ]
    schema_completed = subprocess.run(schema_command, cwd=ROOT, text=True, capture_output=True)
    if schema_completed.returncode != 0:
        errors.append(f"site profile schema failed: {schema_completed.stdout.strip()} {schema_completed.stderr.strip()}".strip())
    command = [
        sys.executable,
        str(ROOT / "scripts" / "site_profile_runner.py"),
        "--url",
        "https://shop.example.test/product/sku-123",
        "--page-type",
        "product_page",
        "--output-root",
        str(OUTPUT_ROOT),
        "--run-id",
        "eval-site-profiles",
    ]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    if completed.returncode != 0:
        errors.append(f"site profile runner failed: {completed.stderr.strip()} {completed.stdout.strip()}".strip())
    match = json.loads((OUTPUT_ROOT / "eval-site-profiles" / "artifacts" / "site-profile-match.json").read_text(encoding="utf-8"))
    if match.get("matched_profile_id") != "ecommerce_product":
        errors.append(f"unexpected profile match: {match.get('matched_profile_id')}")

    invalid_profile = OUTPUT_ROOT / "invalid-profiles.json"
    invalid_profile.write_text("{not-json", encoding="utf-8")
    invalid_run_id = "eval-invalid-site-profiles"
    invalid_completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "site_profile_runner.py"),
            "--profile-file",
            str(invalid_profile),
            "--output-root",
            str(OUTPUT_ROOT),
            "--run-id",
            invalid_run_id,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if invalid_completed.returncode == 0:
        errors.append("invalid profile JSON unexpectedly succeeded")
    if (OUTPUT_ROOT / invalid_run_id).exists():
        errors.append("invalid profile JSON left an orphan run directory")
    if errors:
        print("FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
