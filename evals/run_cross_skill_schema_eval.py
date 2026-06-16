from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "evals" / ".tmp"

REQUIRED_OBJECT_KEYS = {
    "source_record": {
        "source_id",
        "url",
        "canonical_url",
        "title",
        "site_name",
        "page_type",
        "accessed_at",
        "requires_login",
        "capture_method",
        "evidence",
        "screenshot_policy",
        "content_scope",
        "warnings",
    },
    "screenshot_policy": {"required", "reason", "status"},
    "manual_review": {"required", "severity", "reasons"},
}

RUNS = [
    {
        "skill": "page-to-md",
        "run_dir": OUTPUT_ROOT / "page-to-md" / "eval-public-article",
        "validation_report": "validation/validation-report.json",
        "artifact_json": ["artifacts/metadata.json"],
    },
    {
        "skill": "browser-research",
        "run_dir": OUTPUT_ROOT / "browser-research" / "eval-evidence-backed-research",
        "validation_report": "validation/claim-coverage-report.json",
        "artifact_json": ["artifacts/claims.json"],
    },
    {
        "skill": "price-compare",
        "run_dir": OUTPUT_ROOT / "price-compare" / "eval-product-quotes",
        "validation_report": "validation/price-validation-report.json",
        "artifact_json": ["artifacts/prices.json"],
    },
]


def _load_validator() -> Any:
    path = ROOT / "scripts" / "validation" / "validate_json_schema.py"
    spec = importlib.util.spec_from_file_location("validate_json_schema", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load validator: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VALIDATOR = _load_validator()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def generate_eval_outputs() -> list[str]:
    errors: list[str] = []
    for script in ("run_eval.py", "run_research_eval.py", "run_price_eval.py"):
        completed = subprocess.run([sys.executable, str(ROOT / "evals" / script)], cwd=ROOT, text=True, capture_output=True)
        if completed.returncode != 0:
            errors.append(f"{script}: {completed.stdout.strip()} {completed.stderr.strip()}".strip())
    return errors


def schema_errors(schema_name: str, data: Any, label: str) -> list[str]:
    schema = read_json(ROOT / "schemas" / schema_name)
    return [f"{label}: {error}" for error in VALIDATOR.validate_minimal(schema, data)]


def require_exact_keys(label: str, data: Any, expected: set[str]) -> list[str]:
    if not isinstance(data, dict):
        return [f"{label}: expected object"]
    actual = set(data.keys())
    if actual != expected:
        return [f"{label}: keys {sorted(actual)} != {sorted(expected)}"]
    return []


def validate_screenshot_policy(label: str, data: Any) -> list[str]:
    errors = require_exact_keys(label, data, REQUIRED_OBJECT_KEYS["screenshot_policy"])
    if errors:
        return errors
    if not isinstance(data["required"], bool):
        errors.append(f"{label}.required: expected boolean")
    if not isinstance(data["reason"], str):
        errors.append(f"{label}.reason: expected string")
    if not isinstance(data["status"], str):
        errors.append(f"{label}.status: expected string")
    return errors


def validate_manual_review(label: str, data: Any) -> list[str]:
    errors = require_exact_keys(label, data, REQUIRED_OBJECT_KEYS["manual_review"])
    if errors:
        return errors
    if not isinstance(data["required"], bool):
        errors.append(f"{label}.required: expected boolean")
    if data["severity"] not in {"info", "warning", "blocking"}:
        errors.append(f"{label}.severity: invalid {data['severity']!r}")
    if not isinstance(data["reasons"], list):
        errors.append(f"{label}.reasons: expected array")
    return errors


def validate_source_record(label: str, data: Any) -> list[str]:
    errors = schema_errors("source_record.schema.json", data, label)
    errors.extend(require_exact_keys(label, data, REQUIRED_OBJECT_KEYS["source_record"]))
    if isinstance(data, dict):
        errors.extend(validate_screenshot_policy(f"{label}.screenshot_policy", data.get("screenshot_policy")))
    return errors


def iter_objects(value: Any, key: str, label: str) -> list[tuple[str, Any]]:
    found: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        for current_key, nested in value.items():
            nested_label = f"{label}.{current_key}"
            if current_key == key:
                found.append((nested_label, nested))
            found.extend(iter_objects(nested, key, nested_label))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            found.extend(iter_objects(nested, key, f"{label}[{index}]"))
    return found


def validate_run(run: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    skill = str(run["skill"])
    run_dir = Path(run["run_dir"])
    manifest_path = run_dir / "manifest.json"
    validation_report_path = run_dir / str(run["validation_report"])

    if not manifest_path.exists():
        return [f"{skill}: missing manifest {manifest_path}"]
    if not validation_report_path.exists():
        return [f"{skill}: missing validation report {validation_report_path}"]

    manifest = read_json(manifest_path)
    validation_report = read_json(validation_report_path)
    errors.extend(schema_errors("run_manifest.schema.json", manifest, f"{skill}.manifest"))
    errors.extend(schema_errors("validation_report.schema.json", validation_report, f"{skill}.validation_report"))
    errors.extend(validate_manual_review(f"{skill}.manifest.manual_review", manifest.get("manual_review")))
    errors.extend(validate_manual_review(f"{skill}.validation_report.manual_review", validation_report.get("manual_review")))
    errors.extend(validate_screenshot_policy(f"{skill}.manifest.screenshot_policy", manifest.get("screenshot_policy")))
    errors.extend(validate_screenshot_policy(f"{skill}.validation_report.screenshot_policy", validation_report.get("screenshot_policy")))

    if manifest.get("requires_manual_review") != manifest.get("manual_review", {}).get("required"):
        errors.append(f"{skill}.manifest: requires_manual_review disagrees with manual_review.required")
    if validation_report.get("requires_manual_review") != validation_report.get("manual_review", {}).get("required"):
        errors.append(f"{skill}.validation_report: requires_manual_review disagrees with manual_review.required")

    source_records = [
        record
        for record in manifest.get("evidence", [])
        if isinstance(record, dict) and record.get("type") == "source_record"
    ]
    if not source_records:
        errors.append(f"{skill}.manifest.evidence: no source_record entries")
    for record in source_records:
        raw_path = record.get("path")
        source_record_path = run_dir / str(raw_path)
        if not source_record_path.exists():
            errors.append(f"{skill}.source_record: missing {raw_path}")
            continue
        errors.extend(validate_source_record(f"{skill}.{raw_path}", read_json(source_record_path)))

    for artifact in run.get("artifact_json", []):
        artifact_path = run_dir / str(artifact)
        if not artifact_path.exists():
            errors.append(f"{skill}: missing artifact {artifact}")
            continue
        artifact_doc = read_json(artifact_path)
        for label, policy in iter_objects(artifact_doc, "screenshot_policy", f"{skill}.{artifact}"):
            errors.extend(validate_screenshot_policy(label, policy))

    return errors


def main() -> int:
    errors = generate_eval_outputs()
    for run in RUNS:
        errors.extend(validate_run(run))

    if errors:
        print("FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
