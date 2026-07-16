from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "evals" / "fixtures" / "research-discovery"
OUTPUT_ROOT = ROOT / "evals" / ".tmp" / "research-discovery"


def load_cases() -> list[dict[str, object]]:
    return json.loads((FIXTURE_ROOT / "cases.json").read_text(encoding="utf-8"))


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_case(case: dict[str, object]) -> list[str]:
    errors: list[str] = []
    run_id = f"eval-{case['name']}"
    command = [
        sys.executable,
        str(ROOT / "scripts" / "research_discovery_runner.py"),
        "--input",
        str(FIXTURE_ROOT / str(case["input"])),
        "--output-root",
        str(OUTPUT_ROOT),
        "--run-id",
        run_id,
    ]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    expect_blocked = bool(case.get("expect_runner_blocked"))
    if expect_blocked and completed.returncode == 0:
        return [f"{case['name']}: runner should have blocked invalid discovery scope"]
    if not expect_blocked and completed.returncode != 0:
        return [f"{case['name']}: runner failed: {completed.stderr.strip()} {completed.stdout.strip()}".strip()]

    run_dir = OUTPUT_ROOT / run_id
    discovery_validation = read_json(run_dir / "validation" / "discovery-validation-report.json")
    discovery_log = read_json(run_dir / "artifacts" / "discovery-log.json")

    if discovery_validation["status"] != case["expected_discovery_status"]:
        errors.append(f"{case['name']}: discovery status {discovery_validation['status']!r}")

    joined_discovery_errors = "\n".join(discovery_validation.get("errors", []))
    for term in case.get("required_discovery_error_terms", []):
        if str(term) not in joined_discovery_errors:
            errors.append(f"{case['name']}: missing discovery error {term}")

    joined_rejections = "\n".join(
        str(candidate.get("reason") or "")
        for candidate in discovery_log.get("candidates", [])
        if isinstance(candidate, dict) and candidate.get("status") == "rejected"
    )
    for term in case.get("required_rejection_terms", []):
        if str(term) not in joined_rejections:
            errors.append(f"{case['name']}: missing rejection reason {term}")

    expected_selected_count = case.get("expected_selected_count")
    if expected_selected_count is not None and len(discovery_log.get("selected_sources", [])) != expected_selected_count:
        errors.append(
            f"{case['name']}: selected count {len(discovery_log.get('selected_sources', []))}, "
            f"expected {expected_selected_count}"
        )

    if expect_blocked:
        return errors

    claim_validation = read_json(run_dir / "validation" / "claim-coverage-report.json")
    manifest = read_json(run_dir / "manifest.json")
    claims = read_json(run_dir / "artifacts" / "claims.json")

    if claim_validation["status"] != case["expected_claim_status"]:
        errors.append(f"{case['name']}: claim status {claim_validation['status']!r}")
    if manifest["run_status"] != case["expected_run_status"]:
        errors.append(f"{case['name']}: run_status {manifest['run_status']!r}")

    for selected in discovery_log.get("selected_sources", []):
        source_id = selected["source_id"]
        source_dir = f"source-{int(source_id[1:]):03d}"
        for path in (
            run_dir / "capture" / source_dir / "page_capture.json",
            run_dir / "evidence" / source_dir / "source_record.json",
            run_dir / "evidence" / source_dir / "screenshots",
        ):
            if not path.exists():
                errors.append(f"{case['name']}: missing selected-source artifact {path.relative_to(run_dir).as_posix()}")

    claim_source_ids = {source["source_id"] for source in claims.get("sources", [])}
    for selected in discovery_log.get("selected_sources", []):
        if selected["source_id"] not in claim_source_ids:
            errors.append(f"{case['name']}: selected source missing from claims {selected['source_id']}")

    joined_claim_errors = "\n".join(claim_validation.get("errors", []))
    for term in case.get("required_claim_error_terms", []):
        if str(term) not in joined_claim_errors:
            errors.append(f"{case['name']}: missing claim error {term}")

    joined_warnings = "\n".join(claim_validation.get("warnings", []) + manifest.get("warnings", []))
    for term in case.get("required_warnings", []):
        if str(term) not in joined_warnings:
            errors.append(f"{case['name']}: missing warning {term}")

    manifest_paths = [
        item.get("path")
        for section in ("artifacts", "evidence")
        for item in manifest.get(section, [])
        if isinstance(item, dict)
    ]
    for required_path in (
        "artifacts/discovery-log.json",
        "artifacts/discovery-log.md",
        "validation/discovery-validation-report.json",
    ):
        if required_path not in manifest_paths:
            errors.append(f"{case['name']}: manifest missing {required_path}")

    return errors


def run_validator_fail_closed_cases() -> list[str]:
    errors: list[str] = []
    source_run = OUTPUT_ROOT / "eval-bounded-three-sources"
    cases = (
        ("validator-non-object", "[]\n", "json_object_required:artifacts/discovery-log.json"),
        ("validator-invalid-source-id", None, "discovery.selected_source_id_invalid:../../escape"),
    )
    for name, replacement, required_error in cases:
        run_dir = OUTPUT_ROOT / name
        shutil.copytree(source_run, run_dir)
        discovery_path = run_dir / "artifacts" / "discovery-log.json"
        if replacement is not None:
            discovery_path.write_text(replacement, encoding="utf-8")
        else:
            discovery = read_json(discovery_path)
            discovery["selected_sources"][0]["source_id"] = "../../escape"
            discovery_path.write_text(json.dumps(discovery, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "validation" / "validate_research_discovery.py"),
                str(run_dir),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        if completed.returncode == 0:
            errors.append(f"{name}: malformed discovery evidence passed validation")
            continue
        if required_error not in completed.stdout:
            errors.append(f"{name}: missing fail-closed error {required_error}: {completed.stderr.strip()}")
    return errors


def main() -> int:
    if OUTPUT_ROOT.exists():
        shutil.rmtree(OUTPUT_ROOT)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    all_errors: list[str] = []
    for case in load_cases():
        all_errors.extend(run_case(case))
    all_errors.extend(run_validator_fail_closed_cases())

    if all_errors:
        print("FAIL")
        for error in all_errors:
            print(f"- {error}")
        return 1

    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
