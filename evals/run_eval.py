from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "evals" / "fixtures" / "page-to-md"
OUTPUT_ROOT = ROOT / "evals" / ".tmp" / "page-to-md"


def load_cases() -> list[dict[str, object]]:
    return json.loads((FIXTURE_ROOT / "cases.json").read_text(encoding="utf-8"))


def run_case(case: dict[str, object]) -> list[str]:
    errors: list[str] = []
    input_path = FIXTURE_ROOT / str(case["input"])
    run_id = f"eval-{case['name']}"
    command = [
        sys.executable,
        str(ROOT / "scripts" / "page_to_md_runner.py"),
        "--input",
        str(input_path),
        "--url",
        str(case["url"]),
        "--output-root",
        str(OUTPUT_ROOT),
        "--run-id",
        run_id,
        "--page-type",
        str(case.get("page_type", "auto")),
    ]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    if completed.returncode != 0:
        return [f"{case['name']}: runner failed: {completed.stderr.strip()}"]

    run_dir = OUTPUT_ROOT / run_id
    metadata = json.loads((run_dir / "artifacts" / "metadata.json").read_text(encoding="utf-8"))
    markdown = (run_dir / "artifacts" / "page.md").read_text(encoding="utf-8")
    validation = json.loads((run_dir / "validation" / "validation-report.json").read_text(encoding="utf-8"))
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))

    expected_title = str(case["expected_title"])
    actual_title = metadata["document"]["title"]["value"]
    if actual_title != expected_title:
        errors.append(f"{case['name']}: title mismatch: {actual_title!r}")

    if validation["status"] != "pass":
        errors.append(f"{case['name']}: validation failed: {validation['errors']}")

    if not manifest["validation"]["schema_valid"]:
        errors.append(f"{case['name']}: manifest schema_valid is false")

    for warning in case.get("required_warnings", []):
        if warning not in metadata["extraction"]["warnings"]:
            errors.append(f"{case['name']}: missing warning {warning}")

    lower_markdown = markdown.lower()
    for term in case.get("forbidden_terms", []):
        if str(term).lower() in lower_markdown:
            errors.append(f"{case['name']}: forbidden term leaked: {term}")

    for term in case.get("required_terms", []):
        if str(term).lower() not in lower_markdown:
            errors.append(f"{case['name']}: required term missing: {term}")

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
