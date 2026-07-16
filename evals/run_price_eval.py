from __future__ import annotations

import json
import base64
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "evals" / "fixtures" / "price-compare"
OUTPUT_ROOT = ROOT / "evals" / ".tmp" / "price-compare"
SCREENSHOT_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def load_cases() -> list[dict[str, object]]:
    return json.loads((FIXTURE_ROOT / "cases.json").read_text(encoding="utf-8"))


def run_case(case: dict[str, object]) -> list[str]:
    errors: list[str] = []
    fixture_path = FIXTURE_ROOT / str(case["input"])
    case_input_root = OUTPUT_ROOT / "_inputs" / str(case["name"])
    case_input_root.mkdir(parents=True, exist_ok=True)
    input_doc = json.loads(fixture_path.read_text(encoding="utf-8"))
    for index, quote in enumerate(input_doc.get("quotes", []), start=1):
        if not isinstance(quote, dict) or not quote.pop("screenshot_fixture", False):
            continue
        screenshot_name = f"quote-{index:03d}.png"
        (case_input_root / screenshot_name).write_bytes(SCREENSHOT_PNG)
        quote["screenshot_source"] = screenshot_name
    input_path = case_input_root / "input.json"
    input_path.write_text(json.dumps(input_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    run_id = f"eval-{case['name']}"
    command = [
        sys.executable,
        str(ROOT / "scripts" / "price_compare_runner.py"),
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
    report = (run_dir / "artifacts" / "price-report.md").read_text(encoding="utf-8")
    anomalies = (run_dir / "artifacts" / "anomalies.md").read_text(encoding="utf-8")
    prices_csv = (run_dir / "artifacts" / "prices.csv").read_text(encoding="utf-8")
    validation = json.loads((run_dir / "validation" / "price-validation-report.json").read_text(encoding="utf-8"))
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    chart_bytes = (run_dir / "artifacts" / "price-chart.png").read_bytes()

    expected_status = str(case["expected_status"])
    if validation["status"] != expected_status:
        errors.append(f"{case['name']}: validation status {validation['status']!r}, expected {expected_status!r}: {validation['errors']}")
    if expected_status == "pass" and not manifest["validation"]["schema_valid"]:
        errors.append(f"{case['name']}: manifest schema_valid is false")
    if chart_bytes[:8] != b"\x89PNG\r\n\x1a\n":
        errors.append(f"{case['name']}: price-chart.png is not a PNG")

    expected_lowest = case.get("expected_lowest")
    if prices["comparison"]["lowest_eligible_quote_id"] != expected_lowest:
        errors.append(f"{case['name']}: lowest mismatch: {prices['comparison']['lowest_eligible_quote_id']!r}")

    for term in case.get("required_report_terms", []):
        if str(term) not in report:
            errors.append(f"{case['name']}: required report term missing: {term}")

    for term in case.get("required_anomalies", []):
        if str(term) not in anomalies:
            errors.append(f"{case['name']}: required anomaly missing: {term}")

    joined_errors = "\n".join(validation.get("errors", []))
    for term in case.get("required_error_terms", []):
        if str(term) not in joined_errors:
            errors.append(f"{case['name']}: required validation error missing: {term}")

    for quote in prices["quotes"]:
        if quote["quote_id"] not in prices_csv:
            errors.append(f"{case['name']}: quote missing from CSV: {quote['quote_id']}")
        screenshot = quote.get("screenshot")
        if screenshot and not (run_dir / screenshot).exists():
            errors.append(f"{case['name']}: screenshot missing on disk: {screenshot}")

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
