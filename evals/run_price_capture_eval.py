from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "evals" / "fixtures" / "price-capture"
OUTPUT_ROOT = ROOT / "evals" / ".tmp" / "price-capture"


def load_cases() -> list[dict[str, object]]:
    return json.loads((FIXTURE_ROOT / "cases.json").read_text(encoding="utf-8"))


def run_case(case: dict[str, object]) -> list[str]:
    errors: list[str] = []
    input_path = FIXTURE_ROOT / str(case["input"])
    run_id = f"eval-{case['name']}"
    command = [
        sys.executable,
        str(ROOT / "scripts" / "price_capture_runner.py"),
        "--input",
        str(input_path),
        "--output-root",
        str(OUTPUT_ROOT),
        "--run-id",
        run_id,
    ]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    if completed.returncode != 0:
        return [f"{case['name']}: runner failed: {completed.stderr.strip()}"]

    run_dir = OUTPUT_ROOT / run_id
    prices = json.loads((run_dir / "artifacts" / "prices.json").read_text(encoding="utf-8"))
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    validation = json.loads((run_dir / "validation" / "price-validation-report.json").read_text(encoding="utf-8"))
    anomalies = (run_dir / "artifacts" / "anomalies.md").read_text(encoding="utf-8")
    warnings = (run_dir / "validation" / "warnings.md").read_text(encoding="utf-8")

    expected_status = str(case["expected_status"])
    if validation["status"] != expected_status:
        errors.append(f"{case['name']}: validation status {validation['status']!r}, expected {expected_status!r}: {validation['errors']}")
    expected_run_status = str(case["expected_run_status"])
    if manifest["run_status"] != expected_run_status:
        errors.append(f"{case['name']}: run_status {manifest['run_status']!r}, expected {expected_run_status!r}")

    expected_lowest = case.get("expected_lowest")
    if prices["comparison"]["lowest_eligible_quote_id"] != expected_lowest:
        errors.append(f"{case['name']}: lowest mismatch: {prices['comparison']['lowest_eligible_quote_id']!r}")

    if not (run_dir / "capture" / "price-input.json").exists():
        errors.append(f"{case['name']}: generated price input missing")
    for index, quote in enumerate(prices["quotes"], start=1):
        source_dir = f"source-{index:03d}"
        if not (run_dir / "capture" / source_dir / "page_capture.json").exists():
            errors.append(f"{case['name']}: page capture missing for {source_dir}")
        if not (run_dir / "evidence" / source_dir / "source_record.json").exists():
            errors.append(f"{case['name']}: source record missing for {source_dir}")
        if quote.get("eligible_for_lowest_price") and quote.get("excluded_from_lowest_price"):
            errors.append(f"{case['name']}: eligible quote is also excluded: {quote['quote_id']}")
        if quote.get("screenshot") and not (run_dir / str(quote["screenshot"])).exists():
            errors.append(f"{case['name']}: screenshot missing on disk: {quote['screenshot']}")
        if quote.get("quote_context_hash", "").startswith("sha256:") is False:
            errors.append(f"{case['name']}: quote context hash missing for {quote['quote_id']}")

    for term in case.get("required_anomalies", []):
        if str(term) not in anomalies:
            errors.append(f"{case['name']}: required anomaly missing: {term}")

    joined_errors = "\n".join(validation.get("errors", []))
    for term in case.get("required_error_terms", []):
        if str(term) not in joined_errors:
            errors.append(f"{case['name']}: required validation error missing: {term}")

    if "claim" in warnings.lower():
        errors.append(f"{case['name']}: research claim warning leaked into price capture warnings")
    if "provided_url_candidate_assessment" not in json.dumps(prices.get("candidates", []), sort_keys=True):
        errors.append(f"{case['name']}: candidate assessment method missing")

    return errors


def main() -> int:
    if OUTPUT_ROOT.exists():
        shutil.rmtree(OUTPUT_ROOT)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    all_errors: list[str] = []
    for case in load_cases():
        all_errors.extend(run_case(case))

    if all_errors:
        print("FAIL")
        for error in all_errors:
            print(f"- {error}")
        return 1

    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
