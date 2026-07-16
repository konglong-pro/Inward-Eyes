from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "evals" / ".tmp"
SCRIPT_ROOT = ROOT / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from inward_eyes.paths import create_continuation_handoff

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

SCREENSHOT_STATUSES = {
    "required_and_present",
    "required_but_missing",
    "not_required",
    "capture_failed",
    "redacted",
}
AGGREGATE_SCREENSHOT_STATUSES = SCREENSHOT_STATUSES | {"per_source_policy", "per_quote_policy"}

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
    for script in (
        "run_eval.py",
        "run_research_eval.py",
        "run_price_eval.py",
        "run_research_discovery_eval.py",
        "run_price_candidate_discovery_eval.py",
    ):
        completed = subprocess.run([sys.executable, str(ROOT / "evals" / script)], cwd=ROOT, text=True, capture_output=True)
        if completed.returncode != 0:
            errors.append(f"{script}: {completed.stdout.strip()} {completed.stderr.strip()}".strip())
    return errors


def schema_errors(schema_name: str, data: Any, label: str) -> list[str]:
    schema = read_json(ROOT / "schemas" / schema_name)
    return [f"{label}: {error}" for error in VALIDATOR.validate_minimal(schema, data)]


def require_keys(label: str, data: Any, expected: set[str]) -> list[str]:
    if not isinstance(data, dict):
        return [f"{label}: expected object"]
    missing = expected - set(data.keys())
    if missing:
        return [f"{label}: missing required keys {sorted(missing)}"]
    return []


def validate_screenshot_policy(
    label: str,
    data: Any,
    allowed_statuses: set[str] = SCREENSHOT_STATUSES,
) -> list[str]:
    errors = require_keys(label, data, REQUIRED_OBJECT_KEYS["screenshot_policy"])
    if errors:
        return errors
    if not isinstance(data["required"], bool):
        errors.append(f"{label}.required: expected boolean")
    if not isinstance(data["reason"], str):
        errors.append(f"{label}.reason: expected string")
    if not isinstance(data["status"], str):
        errors.append(f"{label}.status: expected string")
    elif data["status"] not in allowed_statuses:
        errors.append(f"{label}.status: invalid {data['status']!r}")
    return errors


def validate_manual_review(label: str, data: Any) -> list[str]:
    errors = require_keys(label, data, REQUIRED_OBJECT_KEYS["manual_review"])
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
    errors.extend(require_keys(label, data, REQUIRED_OBJECT_KEYS["source_record"]))
    if isinstance(data, dict):
        errors.extend(validate_screenshot_policy(f"{label}.screenshot_policy", data.get("screenshot_policy")))
    return errors


def validate_status_invariants(label: str, data: Any) -> list[str]:
    if not isinstance(data, dict):
        return [f"{label}: expected object"]
    errors: list[str] = []
    run_status = data.get("run_status")
    validation_status = data.get("validation_status")
    requires_review = data.get("requires_manual_review")
    manual_review = data.get("manual_review") if isinstance(data.get("manual_review"), dict) else {}
    blockers = data.get("completion_blockers")
    if run_status not in {"complete", "partial", "failed", "aborted_by_policy"}:
        errors.append(f"{label}.run_status: invalid {run_status!r}")
        return errors
    if validation_status not in {"passed", "failed"}:
        errors.append(f"{label}.validation_status: invalid {validation_status!r}")
    if not isinstance(blockers, list):
        errors.append(f"{label}.completion_blockers: expected array")
        blockers = []
    if requires_review != manual_review.get("required"):
        errors.append(f"{label}: requires_manual_review disagrees with manual_review.required")

    expected = {
        "complete": ({"passed"}, False, "info"),
        "partial": ({"passed"}, True, "warning"),
        "failed": ({"failed"}, True, "blocking"),
    }
    if run_status in expected:
        expected_validations, expected_review, expected_severity = expected[run_status]
        if validation_status not in expected_validations:
            errors.append(
                f"{label}: {run_status} requires validation_status in "
                f"{sorted(expected_validations)}, got {validation_status!r}"
            )
        if requires_review is not expected_review:
            errors.append(f"{label}: {run_status} requires requires_manual_review={expected_review}")
        if manual_review.get("severity") != expected_severity:
            errors.append(f"{label}: {run_status} requires manual_review.severity={expected_severity}")
        if run_status == "complete" and blockers:
            errors.append(f"{label}: complete run must not have completion blockers")
        if run_status == "failed" and not blockers:
            errors.append(f"{label}: failed run must have completion blockers")
    else:
        if validation_status != "failed":
            errors.append(f"{label}: aborted_by_policy requires failed validation")
        if requires_review is not True or manual_review.get("severity") != "blocking":
            errors.append(f"{label}: aborted_by_policy requires blocking manual review")
        if not blockers:
            errors.append(f"{label}: aborted_by_policy requires completion blockers")

    report_status = data.get("status")
    if report_status is not None:
        if report_status not in {"pass", "fail"}:
            errors.append(f"{label}.status: invalid {report_status!r}")
        elif (report_status == "pass") != (validation_status == "passed"):
            errors.append(f"{label}: status and validation_status disagree")
    return errors


def validate_status_invariant_matrix() -> list[str]:
    valid_cases = [
        ("complete", "passed", False, "info", []),
        ("partial", "passed", True, "warning", ["REVIEW_REQUIRED"]),
        ("failed", "failed", True, "blocking", ["VALIDATION_FAILED"]),
        ("aborted_by_policy", "failed", True, "blocking", ["PRIVACY_ABORTED"]),
    ]
    errors: list[str] = []
    for index, (run_status, validation_status, review, severity, blockers) in enumerate(valid_cases):
        fixture = {
            "run_status": run_status,
            "validation_status": validation_status,
            "requires_manual_review": review,
            "manual_review": {"required": review, "severity": severity, "reasons": []},
            "completion_blockers": blockers,
        }
        case_errors = validate_status_invariants(f"status_matrix.valid[{index}]", fixture)
        if case_errors:
            errors.extend(case_errors)

    invalid_cases = [
        {
            "run_status": "aborted_by_policy",
            "validation_status": "pending",
            "requires_manual_review": True,
            "manual_review": {"required": True, "severity": "blocking", "reasons": []},
            "completion_blockers": ["SAFETY_ABORTED"],
        },
        {
            "run_status": "complete",
            "validation_status": "failed",
            "requires_manual_review": False,
            "manual_review": {"required": False, "severity": "info", "reasons": []},
            "completion_blockers": [],
        },
        {
            "run_status": "failed",
            "validation_status": "failed",
            "requires_manual_review": True,
            "manual_review": {"required": True, "severity": "blocking", "reasons": []},
            "completion_blockers": [],
        },
        {
            "run_status": "aborted_by_policy",
            "validation_status": "passed",
            "requires_manual_review": True,
            "manual_review": {"required": True, "severity": "blocking", "reasons": []},
            "completion_blockers": ["SAFETY_ABORTED"],
        },
        {
            "run_status": "partial",
            "validation_status": "passed",
            "requires_manual_review": False,
            "manual_review": {"required": False, "severity": "info", "reasons": []},
            "completion_blockers": [],
        },
    ]
    for index, fixture in enumerate(invalid_cases):
        if not validate_status_invariants(f"status_matrix.invalid[{index}]", fixture):
            errors.append(f"status_matrix.invalid[{index}]: invalid fixture was accepted")
    return errors


def validate_validator_features() -> list[str]:
    schema = {
        "type": "object",
        "required": ["id", "score", "items"],
        "properties": {
            "id": {"$ref": "#/$defs/id"},
            "score": {"type": "number", "minimum": 0, "maximum": 1},
            "items": {"type": "array", "minItems": 1, "maxItems": 2, "uniqueItems": True},
        },
        "additionalProperties": False,
        "$defs": {"id": {"type": "string", "pattern": "^S[0-9]{3}$"}},
    }
    errors: list[str] = []
    valid_errors = VALIDATOR.validate_minimal(schema, {"id": "S001", "score": 0.5, "items": ["a"]})
    if valid_errors:
        errors.append(f"validator valid fixture failed: {valid_errors}")
    invalid_errors = VALIDATOR.validate_minimal(
        schema,
        {"id": "unsafe", "score": 2, "items": ["a", "a", "b"], "extra": True},
    )
    for expected in ("pattern", "maximum", "maxItems", "not unique", "additional property"):
        if expected not in "\n".join(invalid_errors):
            errors.append(f"validator invalid fixture did not enforce {expected}: {invalid_errors}")
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
    errors.extend(
        validate_screenshot_policy(
            f"{skill}.manifest.screenshot_policy",
            manifest.get("screenshot_policy"),
            AGGREGATE_SCREENSHOT_STATUSES,
        )
    )
    errors.extend(
        validate_screenshot_policy(
            f"{skill}.validation_report.screenshot_policy",
            validation_report.get("screenshot_policy"),
            AGGREGATE_SCREENSHOT_STATUSES,
        )
    )
    errors.extend(validate_status_invariants(f"{skill}.manifest", manifest))
    errors.extend(validate_status_invariants(f"{skill}.validation_report", validation_report))

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


def validate_workflow_cli_fail_closed() -> list[str]:
    errors: list[str] = []
    negative_root = OUTPUT_ROOT / "workflow-validator-negative"
    if negative_root.exists():
        shutil.rmtree(negative_root)
    negative_root.mkdir(parents=True, exist_ok=True)
    validators = [
        (
            "page",
            OUTPUT_ROOT / "page-to-md" / "eval-public-article",
            ROOT / "scripts" / "validation" / "validate_page_to_md.py",
            "artifacts/metadata.json",
        ),
        (
            "research",
            OUTPUT_ROOT / "browser-research" / "eval-evidence-backed-research",
            ROOT / "scripts" / "validation" / "validate_browser_research.py",
            "artifacts/claims.json",
        ),
        (
            "price",
            OUTPUT_ROOT / "price-compare" / "eval-product-quotes",
            ROOT / "scripts" / "validation" / "validate_price_compare.py",
            "artifacts/prices.json",
        ),
        (
            "research-discovery",
            OUTPUT_ROOT / "research-discovery" / "eval-bounded-three-sources",
            ROOT / "scripts" / "validation" / "validate_research_discovery.py",
            "artifacts/discovery-log.json",
        ),
        (
            "price-discovery",
            OUTPUT_ROOT / "price-candidate-discovery" / "eval-matching-candidates-within-cap",
            ROOT / "scripts" / "validation" / "validate_price_candidate_discovery.py",
            "artifacts/candidates.json",
        ),
    ]

    def run_negative(label: str, source_run: Path, validator: Path, mutate: Any, expected: str) -> None:
        run_dir = negative_root / label
        shutil.copytree(source_run, run_dir)
        mutate(run_dir)
        completed = subprocess.run(
            [sys.executable, str(validator), str(run_dir)],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        output = f"{completed.stdout}\n{completed.stderr}"
        if completed.returncode == 0:
            errors.append(f"{label}: malformed workflow passed CLI validation")
        elif expected not in output:
            errors.append(f"{label}: missing expected error {expected}: {output.strip()}")

    for name, source_run, validator, artifact_path in validators:
        run_negative(
            f"{name}-empty-manifest",
            source_run,
            validator,
            lambda run_dir: (run_dir / "manifest.json").write_text("{}\n", encoding="utf-8"),
            "json_object_empty:manifest.json",
        )

        def unsafe_manifest(run_dir: Path) -> None:
            manifest = read_json(run_dir / "manifest.json")
            manifest.setdefault("artifacts", []).append({"id": "UNSAFE", "type": "unsafe", "path": "../outside"})
            (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        run_negative(f"{name}-unsafe-manifest-path", source_run, validator, unsafe_manifest, "path_invalid:../outside")

        def inconsistent_status(run_dir: Path) -> None:
            manifest = read_json(run_dir / "manifest.json")
            manifest.update(
                {
                    "run_status": "complete",
                    "validation_status": "failed",
                    "requires_manual_review": False,
                    "manual_review": {"required": False, "severity": "info", "reasons": []},
                    "completion_blockers": [],
                }
            )
            manifest["validation"]["requires_manual_review"] = False
            manifest["validation"]["schema_valid"] = True
            (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

        run_negative(f"{name}-inconsistent-status", source_run, validator, inconsistent_status, "complete_validation_not_passed")
        run_negative(
            f"{name}-empty-artifact",
            source_run,
            validator,
            lambda run_dir, relative=artifact_path: (run_dir / relative).write_text("{}\n", encoding="utf-8"),
            f"json_object_empty:{artifact_path}",
        )

    def empty_quotes(run_dir: Path) -> None:
        prices_path = run_dir / "artifacts" / "prices.json"
        prices = read_json(prices_path)
        prices["quotes"] = []
        prices["candidates"] = []
        prices_path.write_text(json.dumps(prices, indent=2) + "\n", encoding="utf-8")

    run_negative(
        "price-empty-quotes",
        OUTPUT_ROOT / "price-compare" / "eval-product-quotes",
        ROOT / "scripts" / "validation" / "validate_price_compare.py",
        empty_quotes,
        "prices.quotes_empty",
    )

    page_screenshot_run = OUTPUT_ROOT / "page-to-md" / "eval-x-thread"

    def remove_page_screenshot_record(run_dir: Path) -> None:
        manifest_path = run_dir / "manifest.json"
        manifest = read_json(manifest_path)
        manifest["evidence"] = [item for item in manifest.get("evidence", []) if item.get("type") != "screenshot"]
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    run_negative(
        "page-screenshot-record-missing",
        page_screenshot_run,
        ROOT / "scripts" / "validation" / "validate_page_to_md.py",
        remove_page_screenshot_record,
        "screenshot_manifest_evidence_missing",
    )

    def tamper_screenshot_and_digest(run_dir: Path) -> None:
        manifest_path = run_dir / "manifest.json"
        manifest = read_json(manifest_path)
        record = next(item for item in manifest["evidence"] if item.get("type") == "screenshot")
        screenshot_path = run_dir / record["path"]
        screenshot_path.write_text("not an image\n", encoding="utf-8")
        record["sha256"] = f"sha256:{hashlib.sha256(screenshot_path.read_bytes()).hexdigest()}"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    run_negative(
        "page-screenshot-tampered-with-new-digest",
        page_screenshot_run,
        ROOT / "scripts" / "validation" / "validate_page_to_md.py",
        tamper_screenshot_and_digest,
        "screenshot_invalid_file",
    )

    symlink_run = negative_root / "page-manifest-external-symlink"
    shutil.copytree(OUTPUT_ROOT / "page-to-md" / "eval-public-article", symlink_run)
    outside_manifest = negative_root / "outside-manifest.json"
    outside_manifest.write_text((symlink_run / "manifest.json").read_text(encoding="utf-8"), encoding="utf-8")
    (symlink_run / "manifest.json").unlink()
    try:
        (symlink_run / "manifest.json").symlink_to(outside_manifest)
    except OSError:
        pass
    else:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "validation" / "validate_page_to_md.py"), str(symlink_run)],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        if completed.returncode == 0 or "manifest.path_invalid:manifest.json" not in completed.stdout:
            errors.append("page-manifest-external-symlink: external symlink was not rejected")
    return errors


def validate_continuation_defer_binding() -> list[str]:
    errors: list[str] = []
    boundary_root = OUTPUT_ROOT / "continuation-defer-negative"
    if boundary_root.exists():
        shutil.rmtree(boundary_root)
    output_root = boundary_root / "runs"
    output_root.mkdir(parents=True, exist_ok=True)
    cases = [
        (
            "browser-research",
            ROOT / "scripts" / "browser_research_runner.py",
            "browser-research-render",
            "capture/research-input.json",
            {"schema_version": "1.0", "topic": "Boundary test", "question": "Boundary test", "sources": []},
            [],
        ),
        (
            "price-compare",
            ROOT / "scripts" / "price_compare_runner.py",
            "price-compare-render",
            "capture/price-input.json",
            {
                "schema_version": "1.0",
                "title": "Boundary test",
                "product": {"target_name": "Boundary product", "required_specs": {"model": "T1"}},
                "candidates": [],
                "quotes": [],
            },
            [],
        ),
        (
            "research-capture",
            ROOT / "scripts" / "research_capture_runner.py",
            "research-capture",
            "capture/discovery-selected-sources.json",
            {"schema_version": "1.0", "question": "Boundary test", "sources": []},
            ["--min-sources", "0"],
        ),
        (
            "price-capture",
            ROOT / "scripts" / "price_capture_runner.py",
            "price-capture",
            "capture/approved-candidates-price-input.json",
            {
                "schema_version": "1.0",
                "product": {"target_name": "Boundary product", "required_specs": {"model": "T1"}},
                "sources": [],
            },
            ["--min-urls", "0"],
        ),
    ]

    for label, runner, stage, input_relative, payload, extra_args in cases:
        run_id = f"{label}-valid-token-no-defer"
        run_dir = output_root / run_id
        input_path = run_dir / Path(*input_relative.split("/"))
        input_path.parent.mkdir(parents=True, exist_ok=True)
        input_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        marker_path = run_dir / ".inward-eyes-handoff.json"
        token = create_continuation_handoff(
            run_dir,
            run_id=run_id,
            from_stage="eval-parent",
            to_stage=stage,
            input_path=input_relative,
        )
        token_sha256 = read_json(marker_path)["token_sha256"]
        completed = subprocess.run(
            [
                sys.executable,
                str(runner),
                "--input",
                str(input_path),
                "--output-root",
                str(output_root),
                "--run-id",
                run_id,
                "--continue-existing-run",
                f"--continuation-token={token}",
                *extra_args,
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        output = f"{completed.stdout}\n{completed.stderr}"
        if completed.returncode == 0:
            errors.append(f"{label}: valid continuation without --defer-manifest was accepted")
        if "authenticated continuation requires --defer-manifest" not in output:
            errors.append(f"{label}: continuation/defer rejection was not enforced: {output.strip()}")
        if (run_dir / "manifest.json").exists():
            errors.append(f"{label}: continuation without --defer-manifest wrote a canonical manifest")
        if list((run_dir / "validation").glob("*stage-manifest.json")):
            errors.append(f"{label}: continuation without --defer-manifest wrote a stage manifest")
        if not marker_path.exists():
            errors.append(f"{label}: rejected continuation consumed its valid one-time handoff")
        else:
            marker = read_json(marker_path)
            if marker.get("token_sha256") != token_sha256:
                errors.append(f"{label}: rejected continuation altered its valid one-time handoff")
    return errors


def validate_continuation_input_digest_binding() -> list[str]:
    errors: list[str] = []
    boundary_root = OUTPUT_ROOT / "continuation-input-digest-negative"
    if boundary_root.exists():
        shutil.rmtree(boundary_root)
    output_root = boundary_root / "runs"
    output_root.mkdir(parents=True, exist_ok=True)
    cases = [
        (
            "research-discovery-to-capture",
            ROOT / "scripts" / "research_capture_runner.py",
            "research-discovery",
            "research-capture",
            "capture/discovery-selected-sources.json",
            {
                "schema_version": "1.0",
                "topic": "Original research topic",
                "question": "Original research question",
                "sources": [],
            },
            {
                "schema_version": "1.0",
                "topic": "Swapped research topic",
                "question": "Swapped research question",
                "sources": [],
            },
            ["--min-sources", "0"],
        ),
        (
            "research-capture-to-render",
            ROOT / "scripts" / "browser_research_runner.py",
            "research-capture",
            "browser-research-render",
            "capture/research-input.json",
            {
                "schema_version": "1.0",
                "topic": "Original research topic",
                "question": "Original research question",
                "sources": [],
            },
            {
                "schema_version": "1.0",
                "topic": "Swapped research topic",
                "question": "Swapped research question",
                "sources": [],
            },
            [],
        ),
        (
            "price-discovery-to-capture",
            ROOT / "scripts" / "price_capture_runner.py",
            "price-candidate-discovery",
            "price-capture",
            "capture/approved-candidates-price-input.json",
            {
                "schema_version": "1.0",
                "product": {"target_name": "Original product", "required_specs": {"model": "T1"}},
                "sources": [],
            },
            {
                "schema_version": "1.0",
                "product": {"target_name": "Swapped product", "required_specs": {"model": "T2"}},
                "sources": [],
            },
            ["--min-urls", "0"],
        ),
        (
            "price-capture-to-render",
            ROOT / "scripts" / "price_compare_runner.py",
            "price-capture",
            "price-compare-render",
            "capture/price-input.json",
            {
                "schema_version": "1.0",
                "title": "Original comparison",
                "product": {"target_name": "Original product", "required_specs": {"model": "T1"}},
                "candidates": [],
                "quotes": [],
            },
            {
                "schema_version": "1.0",
                "title": "Swapped comparison",
                "product": {"target_name": "Swapped product", "required_specs": {"model": "T2"}},
                "candidates": [],
                "quotes": [],
            },
            [],
        ),
    ]

    for label, runner, from_stage, to_stage, input_relative, original, swapped, extra_args in cases:
        run_id = label
        run_dir = output_root / run_id
        input_path = run_dir / Path(*input_relative.split("/"))
        input_path.parent.mkdir(parents=True, exist_ok=True)
        original_bytes = (json.dumps(original, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        swapped_bytes = (json.dumps(swapped, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        input_path.write_bytes(original_bytes)
        original_digest = f"sha256:{hashlib.sha256(original_bytes).hexdigest()}"
        marker_path = run_dir / ".inward-eyes-handoff.json"
        token = create_continuation_handoff(
            run_dir,
            run_id=run_id,
            from_stage=from_stage,
            to_stage=to_stage,
            input_path=input_relative,
            artifact_sha256={input_relative: original_digest},
        )
        input_path.write_bytes(swapped_bytes)
        completed = subprocess.run(
            [
                sys.executable,
                str(runner),
                "--input",
                str(input_path),
                "--output-root",
                str(output_root),
                "--run-id",
                run_id,
                "--continue-existing-run",
                f"--continuation-token={token}",
                "--defer-manifest",
                *extra_args,
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        output = f"{completed.stdout}\n{completed.stderr}"
        if completed.returncode == 0:
            errors.append(f"{label}: swapped continuation input was accepted")
        if "continuation handoff artifact digests do not match" not in output:
            errors.append(f"{label}: missing digest mismatch rejection: {output.strip()}")
        if not marker_path.exists():
            errors.append(f"{label}: digest mismatch consumed its valid continuation handoff")
        else:
            marker = read_json(marker_path)
            if marker.get("artifact_sha256") != {input_relative: original_digest}:
                errors.append(f"{label}: digest mismatch altered the authenticated handoff")
        if (run_dir / "manifest.json").exists() or list((run_dir / "validation").glob("*stage-manifest.json")):
            errors.append(f"{label}: digest mismatch wrote a manifest")
    return errors


def validate_price_screenshot_preflight_before_claim() -> list[str]:
    errors: list[str] = []
    output_root = OUTPUT_ROOT / "price-screenshot-preflight-negative" / "runs"
    if output_root.parent.exists():
        shutil.rmtree(output_root.parent)
    run_id = "price-screenshot-preflight"
    run_dir = output_root / run_id
    input_path = run_dir / "capture" / "price-input.json"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "product": {"target_name": "Boundary product", "required_specs": {"model": "T1"}},
                "quotes": [
                    {
                        "source_id": "S001",
                        "url": "https://example.com/product",
                        "screenshot_source": "bad\u0000.png",
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    marker_path = run_dir / ".inward-eyes-handoff.json"
    token = create_continuation_handoff(
        run_dir,
        run_id=run_id,
        from_stage="price-capture",
        to_stage="price-compare-render",
        input_path="capture/price-input.json",
    )
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "price_compare_runner.py"),
            "--input",
            str(input_path),
            "--output-root",
            str(output_root),
            "--run-id",
            run_id,
            "--continue-existing-run",
            f"--continuation-token={token}",
            "--defer-manifest",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    output = f"{completed.stdout}\n{completed.stderr}"
    if completed.returncode == 0:
        errors.append("price-screenshot-preflight: invalid screenshot path was accepted")
    if "screenshot_source must be a canonical input-relative path" not in output:
        errors.append(f"price-screenshot-preflight: missing expected rejection: {output.strip()}")
    if not marker_path.exists():
        errors.append("price-screenshot-preflight: invalid screenshot input consumed the continuation handoff")
    if (run_dir / "manifest.json").exists() or list((run_dir / "validation").glob("*stage-manifest.json")):
        errors.append("price-screenshot-preflight: invalid screenshot input wrote a manifest")
    return errors


def validate_runner_preflight_no_orphans() -> list[str]:
    errors: list[str] = []
    boundary_root = OUTPUT_ROOT / "runner-preflight-negative"
    if boundary_root.exists():
        shutil.rmtree(boundary_root)
    boundary_root.mkdir(parents=True, exist_ok=True)
    cases = [
        (
            "browser-research-invalid-source-id",
            ROOT / "scripts" / "browser_research_runner.py",
            {
                "schema_version": "1.0",
                "topic": "Preflight test",
                "question": "Preflight test",
                "sources": [{"source_id": "invalid", "url": "https://example.com"}],
            },
            [],
            "source_id must match",
        ),
        (
            "price-compare-invalid-source-id",
            ROOT / "scripts" / "price_compare_runner.py",
            {
                "schema_version": "1.0",
                "product": {"target_name": "Preflight product", "required_specs": {"model": "T1"}},
                "quotes": [
                    {
                        "source_id": "invalid",
                        "url": "https://example.com/product",
                        "product_identity": {"product_name": "Preflight product", "specs": {"model": "T1"}},
                    }
                ],
            },
            [],
            "source_id must match",
        ),
        (
            "price-compare-screenshot-source-mismatch",
            ROOT / "scripts" / "price_compare_runner.py",
            {
                "schema_version": "1.0",
                "product": {"target_name": "Preflight product", "required_specs": {"model": "T1"}},
                "quotes": [
                    {
                        "source_id": "S001",
                        "url": "https://example.com/product",
                        "screenshot": "evidence/source-002/screenshots/001.png",
                    }
                ],
            },
            [],
            "screenshot path must belong to source_id S001",
        ),
        (
            "research-capture-invalid-source-id",
            ROOT / "scripts" / "research_capture_runner.py",
            {
                "schema_version": "1.0",
                "question": "Preflight test",
                "sources": [{"source_id": "invalid", "url": "https://example.com", "approved": True}],
            },
            ["--min-sources", "1"],
            "source_id must match",
        ),
        (
            "research-capture-invalid-backend",
            ROOT / "scripts" / "research_capture_runner.py",
            {
                "schema_version": "1.0",
                "question": "Preflight test",
                "sources": [
                    {
                        "source_id": "S001",
                        "url": "https://example.com",
                        "approved": True,
                        "capture_backend": "unsupported",
                    }
                ],
            },
            ["--min-sources", "1"],
            "unsupported source capture backend",
        ),
        (
            "price-capture-invalid-source-id",
            ROOT / "scripts" / "price_capture_runner.py",
            {
                "schema_version": "1.0",
                "product": {"target_name": "Preflight product", "required_specs": {"model": "T1"}},
                "sources": [
                    {
                        "source_id": "invalid",
                        "url": "https://example.com/product",
                        "approved": True,
                        "capture_backend": "public_url",
                    }
                ],
            },
            ["--min-urls", "1"],
            "source_id must match",
        ),
        (
            "price-capture-invalid-backend",
            ROOT / "scripts" / "price_capture_runner.py",
            {
                "schema_version": "1.0",
                "product": {"target_name": "Preflight product", "required_specs": {"model": "T1"}},
                "sources": [
                    {
                        "source_id": "S001",
                        "url": "https://example.com/product",
                        "approved": True,
                        "capture_backend": "current_chrome",
                    }
                ],
            },
            ["--min-urls", "1"],
            "supports public product URL capture only",
        ),
        (
            "price-capture-invalid-screenshot-path",
            ROOT / "scripts" / "price_capture_runner.py",
            {
                "schema_version": "1.0",
                "product": {"target_name": "Preflight product", "required_specs": {"model": "T1"}},
                "sources": [
                    {
                        "source_id": "S001",
                        "url": "https://example.com/product",
                        "approved": True,
                        "capture_backend": "public_url",
                        "screenshot": "bad\u0000.png",
                    }
                ],
            },
            ["--min-urls", "1"],
            "input path must not contain NUL",
        ),
    ]

    for label, runner, payload, extra_args, expected in cases:
        case_root = boundary_root / label
        case_root.mkdir(parents=True, exist_ok=True)
        input_path = case_root / "input.json"
        input_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        output_root = case_root / "runs"
        run_id = "must-not-exist"
        completed = subprocess.run(
            [
                sys.executable,
                str(runner),
                "--input",
                str(input_path),
                "--output-root",
                str(output_root),
                "--run-id",
                run_id,
                *extra_args,
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        output = f"{completed.stdout}\n{completed.stderr}"
        if completed.returncode == 0:
            errors.append(f"{label}: invalid preflight input was accepted")
        if expected not in output:
            errors.append(f"{label}: missing expected preflight error {expected!r}: {output.strip()}")
        if (output_root / run_id).exists():
            errors.append(f"{label}: invalid preflight input left an orphan run directory")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate cross-skill shared schema and status compatibility.")
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Generate prerequisite page, research, and price eval outputs before validation.",
    )
    args = parser.parse_args()
    errors = generate_eval_outputs() if args.generate else []
    errors.extend(validate_validator_features())
    errors.extend(validate_status_invariant_matrix())
    errors.extend(validate_workflow_cli_fail_closed())
    errors.extend(validate_continuation_defer_binding())
    errors.extend(validate_continuation_input_digest_binding())
    errors.extend(validate_price_screenshot_preflight_before_claim())
    errors.extend(validate_runner_preflight_no_orphans())
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
