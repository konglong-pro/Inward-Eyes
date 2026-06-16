from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "evals" / "fixtures" / "research-capture"
OUTPUT_ROOT = ROOT / "evals" / ".tmp" / "research-capture"


def load_cases() -> list[dict[str, object]]:
    return json.loads((FIXTURE_ROOT / "cases.json").read_text(encoding="utf-8"))


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_case(case: dict[str, object]) -> list[str]:
    errors: list[str] = []
    run_id = f"eval-{case['name']}"
    command = [
        sys.executable,
        str(ROOT / "scripts" / "research_capture_runner.py"),
        "--input",
        str(FIXTURE_ROOT / str(case["input"])),
        "--output-root",
        str(OUTPUT_ROOT),
        "--run-id",
        run_id,
    ]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    if completed.returncode != 0:
        return [f"{case['name']}: runner failed: {completed.stderr.strip()} {completed.stdout.strip()}".strip()]

    run_dir = OUTPUT_ROOT / run_id
    validation = read_json(run_dir / "validation" / "claim-coverage-report.json")
    manifest = read_json(run_dir / "manifest.json")
    claims = read_json(run_dir / "artifacts" / "claims.json")
    report = (run_dir / "artifacts" / "report.md").read_text(encoding="utf-8")
    sources_csv = (run_dir / "artifacts" / "sources.csv").read_text(encoding="utf-8")

    if validation["status"] != case["expected_status"]:
        errors.append(f"{case['name']}: validation status {validation['status']!r}")
    if manifest["run_status"] != case["expected_run_status"]:
        errors.append(f"{case['name']}: run_status {manifest['run_status']!r}")

    expected_missing = set(str(item) for item in case.get("missing_capture_sources", []))
    for source in claims["sources"]:
        source_dir = source["evidence_path"].split("/")[1]
        source_record = run_dir / source["evidence_path"]
        if not source_record.exists():
            errors.append(f"{case['name']}: missing source record {source['evidence_path']}")
        capture_path = run_dir / "capture" / source_dir / "page_capture.json"
        if source_dir in expected_missing:
            if capture_path.exists():
                errors.append(f"{case['name']}: unexpected capture for failed source {source_dir}")
        elif not capture_path.exists():
            errors.append(f"{case['name']}: missing capture {capture_path.relative_to(run_dir).as_posix()}")

    for path in (
        run_dir / "input.json",
        run_dir / "capture" / "research-input.json",
        run_dir / "artifacts" / "claims.json",
        run_dir / "artifacts" / "report.md",
        run_dir / "artifacts" / "sources.csv",
        run_dir / "artifacts" / "source_notes.md",
        run_dir / "validation" / "missing-sources.md",
        run_dir / "validation" / "warnings.md",
    ):
        if not path.exists():
            errors.append(f"{case['name']}: missing {path.relative_to(run_dir).as_posix()}")

    joined_errors = "\n".join(validation.get("errors", []))
    for term in case.get("required_error_terms", []):
        if str(term) not in joined_errors:
            errors.append(f"{case['name']}: missing error {term}")

    joined_warnings = "\n".join(validation.get("warnings", []) + manifest.get("warnings", []))
    for term in case.get("required_warnings", []):
        if str(term) not in joined_warnings:
            errors.append(f"{case['name']}: missing warning {term}")

    for term in case.get("required_report_terms", []):
        if str(term) not in report:
            errors.append(f"{case['name']}: missing report term {term}")

    for source_id in case.get("required_source_ids", []):
        if str(source_id) not in sources_csv:
            errors.append(f"{case['name']}: missing source id in CSV {source_id}")

    capture_warnings = []
    for capture_path in (run_dir / "capture").glob("source-*/page_capture.json"):
        capture_warnings.extend(read_json(capture_path).get("warnings", []))
    for term in case.get("required_capture_warnings", []):
        if str(term) not in "\n".join(capture_warnings):
            errors.append(f"{case['name']}: missing capture warning {term}")

    manifest_paths = [item.get("path") for item in manifest.get("evidence", []) if isinstance(item, dict)]
    if "capture/research-input.json" not in manifest_paths:
        errors.append(f"{case['name']}: manifest missing generated research input")

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
