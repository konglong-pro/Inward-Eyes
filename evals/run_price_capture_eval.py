from __future__ import annotations

import base64
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "evals" / "fixtures" / "price-capture"
OUTPUT_ROOT = ROOT / "evals" / ".tmp" / "price-capture"

SCREENSHOT_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
PRIVACY_SECRETS = (
    "IE-PRICE-COOKIE-SECRET",
    "IE-PRICE-TOKEN-SECRET",
    "IE-PRICE-PROFILE-SECRET",
)


def load_cases() -> list[dict[str, object]]:
    return json.loads((FIXTURE_ROOT / "cases.json").read_text(encoding="utf-8"))


def run_failed_capture_privacy_retention() -> list[str]:
    errors: list[str] = []
    run_id = "eval-sensitive-failed-admission"
    input_root = OUTPUT_ROOT / "_inputs" / "sensitive-failed-admission"
    input_root.mkdir(parents=True, exist_ok=True)
    input_doc = json.loads((FIXTURE_ROOT / "two-matching-product-urls.json").read_text(encoding="utf-8"))
    for index, source in enumerate(input_doc.get("sources", []), start=1):
        if not isinstance(source, dict):
            continue
        source["accessibility_snapshot"] = {
            "cookies": {"session": PRIVACY_SECRETS[0]},
            "token": PRIVACY_SECRETS[1],
            "browser_profile": {"name": PRIVACY_SECRETS[2]},
        }
        screenshot_path = input_root / f"private-{index}.png"
        screenshot_path.write_bytes(SCREENSHOT_PNG + "|".join(PRIVACY_SECRETS).encode("utf-8"))
        source["screenshot"] = str(screenshot_path)
    input_path = input_root / "input.json"
    input_path.write_text(json.dumps(input_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "price_capture_runner.py"),
            "--input",
            str(input_path),
            "--output-root",
            str(OUTPUT_ROOT),
            "--run-id",
            run_id,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        return [f"sensitive_failed_admission: runner failed: {completed.stderr.strip()}"]

    run_dir = OUTPUT_ROOT / run_id
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    validation = json.loads((run_dir / "validation" / "price-validation-report.json").read_text(encoding="utf-8"))
    if manifest.get("run_status") != "failed" or validation.get("status") != "fail":
        errors.append(
            "sensitive_failed_admission: failed adapter capture was not preserved as an auditable failed run"
        )
    evidence = [item for item in manifest.get("evidence", []) if isinstance(item, dict)]
    retained_raw = [item for item in evidence if item.get("type") in {"page_capture", "screenshot"}]
    if retained_raw:
        errors.append(f"sensitive_failed_admission: manifest retained raw capture evidence: {retained_raw}")
    if list((run_dir / "capture").glob("source-*/page_capture.json")):
        errors.append("sensitive_failed_admission: canonical run retained rejected page_capture.json")
    if list((run_dir / "capture").glob("source-*/capture-validation-report.json")):
        errors.append("sensitive_failed_admission: canonical run retained rejected adapter report")
    raw_image_paths = [
        path
        for root in (run_dir / "capture", run_dir / "evidence")
        for path in root.rglob("*")
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif"}
    ]
    if raw_image_paths:
        errors.append("sensitive_failed_admission: canonical run retained rejected screenshot bytes")
    for path in run_dir.rglob("*"):
        if not path.is_file():
            continue
        payload = path.read_bytes()
        for secret in PRIVACY_SECRETS:
            if secret.encode("utf-8") in payload:
                errors.append(
                    f"sensitive_failed_admission: sensitive value retained in {path.relative_to(run_dir).as_posix()}"
                )
    audit_text = json.dumps(
        {
            "manifest_warnings": manifest.get("warnings", []),
            "validation_errors": validation.get("errors", []),
            "validation_warnings": validation.get("warnings", []),
        },
        sort_keys=True,
    )
    if "capture_contract_not_passed" not in audit_text or "capture_failed" not in audit_text:
        errors.append("sensitive_failed_admission: safe admission failure diagnostics missing")
    if (run_dir / "capture" / "_adapter-stage").exists():
        errors.append("sensitive_failed_admission: raw adapter stage was not removed")
    return errors


def run_case(case: dict[str, object]) -> list[str]:
    errors: list[str] = []
    fixture_path = FIXTURE_ROOT / str(case["input"])
    case_input_root = OUTPUT_ROOT / "_inputs" / str(case["name"])
    case_input_root.mkdir(parents=True, exist_ok=True)
    input_doc = json.loads(fixture_path.read_text(encoding="utf-8"))
    for source in input_doc.get("sources", []):
        if not isinstance(source, dict) or not source.get("screenshot"):
            continue
        screenshot_path = case_input_root / Path(str(source["screenshot"]))
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        screenshot_path.write_bytes(SCREENSHOT_PNG)
    input_path = case_input_root / "input.json"
    input_path.write_text(json.dumps(input_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
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
        capture_path = run_dir / "capture" / source_dir / "page_capture.json"
        if quote.get("capture_method") == "capture_failed" and capture_path.exists():
            errors.append(f"{case['name']}: rejected page capture retained for {source_dir}")
        elif quote.get("capture_method") != "capture_failed" and not capture_path.exists():
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
    all_errors.extend(run_failed_capture_privacy_retention())

    if all_errors:
        print("FAIL")
        for error in all_errors:
            print(f"- {error}")
        return 1

    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
