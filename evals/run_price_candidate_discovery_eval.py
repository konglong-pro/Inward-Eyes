from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "evals" / "fixtures" / "price-candidate-discovery"
OUTPUT_ROOT = ROOT / "evals" / ".tmp" / "price-candidate-discovery"


def load_cases() -> list[dict[str, object]]:
    return json.loads((FIXTURE_ROOT / "cases.json").read_text(encoding="utf-8"))


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_case(case: dict[str, object]) -> list[str]:
    errors: list[str] = []
    run_id = f"eval-{case['name']}"
    command = [
        sys.executable,
        str(ROOT / "scripts" / "price_candidate_discovery_runner.py"),
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
        return [f"{case['name']}: runner should have blocked invalid candidate discovery"]
    if not expect_blocked and completed.returncode != 0:
        return [f"{case['name']}: runner failed: {completed.stderr.strip()} {completed.stdout.strip()}".strip()]

    run_dir = OUTPUT_ROOT / run_id
    candidate_validation = read_json(run_dir / "validation" / "candidate-validation-report.json")
    candidates_doc = read_json(run_dir / "artifacts" / "candidates.json")
    manifest = read_json(run_dir / "manifest.json")

    if candidate_validation["status"] != case["expected_candidate_status"]:
        errors.append(f"{case['name']}: candidate status {candidate_validation['status']!r}: {candidate_validation.get('errors')}")
    if manifest["run_status"] != case["expected_run_status"]:
        errors.append(f"{case['name']}: run_status {manifest['run_status']!r}")

    expected_approved = case.get("expected_approved_count")
    if expected_approved is not None and candidate_validation["approved_candidates"] != expected_approved:
        errors.append(f"{case['name']}: approved count {candidate_validation['approved_candidates']!r}")

    serialized_candidates = json.dumps(candidates_doc.get("candidates", []), sort_keys=True)
    if "approved_candidate_discovery" not in serialized_candidates:
        errors.append(f"{case['name']}: candidate assessment method missing")

    joined_candidate_errors = "\n".join(candidate_validation.get("errors", []))
    for term in case.get("required_candidate_error_terms", []):
        if str(term) not in joined_candidate_errors:
            errors.append(f"{case['name']}: missing candidate error {term}")

    joined_rejections = "\n".join(
        str(candidate.get("rejection_rationale") or "")
        for candidate in candidates_doc.get("candidates", [])
        if isinstance(candidate, dict) and candidate.get("status") == "rejected"
    )
    for term in case.get("required_rejection_terms", []):
        if str(term) not in joined_rejections:
            errors.append(f"{case['name']}: missing rejection reason {term}")

    for path in (
        run_dir / "artifacts" / "candidates.json",
        run_dir / "artifacts" / "candidates.csv",
        run_dir / "artifacts" / "candidate-review.md",
        run_dir / "capture" / "candidate-search" / "discovery-scope.json",
        run_dir / "validation" / "candidate-validation-report.json",
    ):
        if not path.exists():
            errors.append(f"{case['name']}: missing {path.relative_to(run_dir).as_posix()}")

    expect_prices = bool(case.get("expect_price_artifacts"))
    price_path = run_dir / "artifacts" / "prices.json"
    if expect_prices and not price_path.exists():
        errors.append(f"{case['name']}: expected price artifacts")
        return errors
    if not expect_prices:
        if price_path.exists():
            errors.append(f"{case['name']}: unexpected price artifacts")
        return errors

    prices = read_json(price_path)
    price_validation = read_json(run_dir / "validation" / "price-validation-report.json")
    if price_validation["status"] != case["expected_price_status"]:
        errors.append(f"{case['name']}: price status {price_validation['status']!r}: {price_validation.get('errors')}")
    expected_lowest = case.get("expected_lowest")
    if prices["comparison"]["lowest_eligible_quote_id"] != expected_lowest:
        errors.append(f"{case['name']}: lowest mismatch {prices['comparison']['lowest_eligible_quote_id']!r}")

    if "provided_url_candidate_assessment" not in json.dumps(prices.get("candidates", []), sort_keys=True):
        errors.append(f"{case['name']}: M9 candidate assessment method missing")

    for quote in prices.get("quotes", []):
        source_id = quote["source_id"]
        source_dir = f"source-{int(source_id[1:]):03d}"
        for path in (
            run_dir / "capture" / source_dir / "page_capture.json",
            run_dir / "evidence" / source_dir / "source_record.json",
        ):
            if not path.exists():
                errors.append(f"{case['name']}: missing {path.relative_to(run_dir).as_posix()}")
        if quote.get("screenshot") and not (run_dir / str(quote["screenshot"])).exists():
            errors.append(f"{case['name']}: missing screenshot {quote['screenshot']}")

    anomalies = (run_dir / "artifacts" / "anomalies.md").read_text(encoding="utf-8")
    for term in case.get("required_anomalies", []):
        if str(term) not in anomalies:
            errors.append(f"{case['name']}: missing anomaly {term}")

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
