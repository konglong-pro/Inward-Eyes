from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "evals" / "fixtures" / "browser-research"
OUTPUT_ROOT = ROOT / "evals" / ".tmp" / "browser-research"


def load_cases() -> list[dict[str, object]]:
    return json.loads((FIXTURE_ROOT / "cases.json").read_text(encoding="utf-8"))


def run_case(case: dict[str, object]) -> list[str]:
    errors: list[str] = []
    input_path = FIXTURE_ROOT / str(case["input"])
    run_id = f"eval-{case['name']}"
    command = [
        sys.executable,
        str(ROOT / "scripts" / "browser_research_runner.py"),
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
    claims = json.loads((run_dir / "artifacts" / "claims.json").read_text(encoding="utf-8"))
    report = (run_dir / "artifacts" / "report.md").read_text(encoding="utf-8")
    sources_csv = (run_dir / "artifacts" / "sources.csv").read_text(encoding="utf-8")
    validation = json.loads((run_dir / "validation" / "claim-coverage-report.json").read_text(encoding="utf-8"))
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))

    expected_status = str(case["expected_status"])
    if validation["status"] != expected_status:
        errors.append(f"{case['name']}: validation status {validation['status']!r}, expected {expected_status!r}")

    if expected_status == "pass" and not manifest["validation"]["schema_valid"]:
        errors.append(f"{case['name']}: manifest schema_valid is false")
    if expected_status == "fail" and manifest["validation"]["schema_valid"]:
        errors.append(f"{case['name']}: manifest schema_valid should be false")

    for term in case.get("required_report_terms", []):
        if str(term) not in report:
            errors.append(f"{case['name']}: required report term missing: {term}")

    for source_id in case.get("required_source_ids", []):
        if str(source_id) not in sources_csv:
            errors.append(f"{case['name']}: source id missing from sources.csv: {source_id}")
        if str(source_id) not in [source["source_id"] for source in claims["sources"]]:
            errors.append(f"{case['name']}: source id missing from claims.json: {source_id}")

    joined_errors = "\n".join(validation.get("errors", []))
    for term in case.get("required_error_terms", []):
        if str(term) not in joined_errors:
            errors.append(f"{case['name']}: required validation error missing: {term}")

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
