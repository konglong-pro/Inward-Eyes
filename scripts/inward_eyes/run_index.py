from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from inward_eyes.io import write_json, write_text
from inward_eyes.validation import canonical_manifest_shape_error, validate_manifest_paths, validate_manifest_status


NON_RETRYABLE_BLOCKER_TOKENS = (
    "aborted_by_policy",
    "policy",
    "private_data",
    "privacy",
    "scope",
    "requires_login",
    "yellow_unapproved",
    "red_action",
)

def find_canonical_run_ancestor(target: Path) -> Path | None:
    resolved = target.resolve(strict=False)
    for candidate in (resolved, *resolved.parents):
        manifest_path = candidate / "manifest.json"
        if manifest_path.is_symlink() or manifest_path.is_file():
            return candidate
    return None


def _read_manifest(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if path.is_symlink():
        return None, "RUN_INDEX_MANIFEST_SYMLINK"
    if not path.is_file():
        return None, "RUN_INDEX_MANIFEST_NOT_FILE"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None, "RUN_INDEX_MANIFEST_INVALID_JSON"
    if not isinstance(data, dict):
        return None, "RUN_INDEX_MANIFEST_INVALID_SHAPE"
    return data, None


def _manifest_error(manifest: dict[str, Any], run_dir: Path) -> str | None:
    shape_error = canonical_manifest_shape_error(manifest, expected_run_id=run_dir.name)
    if shape_error == "run_id_mismatch":
        return "RUN_INDEX_MANIFEST_RUN_ID_MISMATCH"
    if shape_error:
        category, _, field = shape_error.partition(":")
        if category == "required_field_missing":
            return f"RUN_INDEX_MANIFEST_REQUIRED_FIELD_MISSING:{field}"
        return f"RUN_INDEX_MANIFEST_FIELD_INVALID:{field or category}"
    status_errors = validate_manifest_status(manifest)
    if status_errors:
        return f"RUN_INDEX_MANIFEST_STATUS_INCONSISTENT:{status_errors[0]}"
    path_errors = validate_manifest_paths(run_dir, manifest)
    if path_errors:
        return f"RUN_INDEX_MANIFEST_PATH_INCONSISTENT:{path_errors[0]}"
    return None


def _invalid_summary(run_dir: Path, relative_path: str, error: str) -> dict[str, Any]:
    return {
        "run_id": run_dir.name,
        "task": None,
        "skill": None,
        "run_status": "failed",
        "validation_status": "failed",
        "requires_manual_review": True,
        "manual_review": {"required": True, "severity": "blocking", "reasons": []},
        "started_at": None,
        "finished_at": None,
        "path": relative_path,
        "completion_blockers": [error],
        "warnings": [],
        "index_error": error,
    }


def summarize_run(run_dir: Path, output_root: Path) -> dict[str, Any]:
    manifest, manifest_error = _read_manifest(run_dir / "manifest.json")
    try:
        relative_path = run_dir.resolve().relative_to(output_root.resolve()).as_posix()
    except ValueError:
        relative_path = run_dir.relative_to(output_root).as_posix()
        return _invalid_summary(run_dir, relative_path, "RUN_INDEX_RUN_DIR_OUTSIDE_ROOT")
    if manifest_error:
        return _invalid_summary(run_dir, relative_path, manifest_error)
    assert manifest is not None
    manifest_error = _manifest_error(manifest, run_dir)
    if manifest_error:
        return _invalid_summary(run_dir, relative_path, manifest_error)
    return {
        "run_id": manifest.get("run_id") or run_dir.name,
        "task": manifest.get("task"),
        "skill": manifest.get("skill"),
        "run_status": manifest.get("run_status"),
        "validation_status": manifest.get("validation_status"),
        "requires_manual_review": bool(manifest.get("requires_manual_review")),
        "manual_review": manifest.get("manual_review") if isinstance(manifest.get("manual_review"), dict) else {},
        "started_at": manifest.get("started_at"),
        "finished_at": manifest.get("finished_at"),
        "path": relative_path,
        "completion_blockers": manifest.get("completion_blockers") or [],
        "warnings": manifest.get("warnings") or [],
    }


def index_runs(output_root: Path) -> list[dict[str, Any]]:
    if not output_root.exists():
        return []
    records = []
    for manifest_path in sorted(output_root.rglob("manifest.json")):
        run_dir = manifest_path.parent
        records.append(summarize_run(run_dir, output_root))
    return sorted(records, key=lambda item: str(item.get("started_at") or ""))


def write_run_index(output_root: Path, index_path: Path) -> list[dict[str, Any]]:
    records = index_runs(output_root)
    lines = [json.dumps(record, ensure_ascii=False, sort_keys=True) for record in records]
    write_text(index_path, "\n".join(lines) + ("\n" if lines else ""))
    return records


def _manual_reason_text(manual_review: dict[str, Any]) -> list[str] | None:
    reasons = manual_review.get("reasons", [])
    if not isinstance(reasons, list) or not all(isinstance(reason, dict) for reason in reasons):
        return None
    values: list[str] = []
    for reason in reasons:
        for field in ("code", "message"):
            value = reason.get(field)
            if value is None:
                continue
            if not isinstance(value, str):
                return None
            if value:
                values.append(value)
    return values


def classify_retryability(record: dict[str, Any]) -> tuple[bool, str]:
    """Return a conservative retry decision for a manifest or index record."""

    if not isinstance(record, dict):
        return False, "record_invalid_shape"
    status = record.get("run_status")
    raw_blockers = record.get("completion_blockers")
    raw_warnings = record.get("warnings")
    if not isinstance(raw_blockers, list) or not all(isinstance(item, str) for item in raw_blockers):
        return False, "completion_blockers_invalid"
    if not isinstance(raw_warnings, list) or not all(isinstance(item, str) for item in raw_warnings):
        return False, "warnings_invalid"
    blockers = raw_blockers
    warnings = raw_warnings
    raw_manual_review = record.get("manual_review")
    if not isinstance(raw_manual_review, dict):
        return False, "manual_review_invalid"
    manual_review = raw_manual_review
    if "required" in manual_review and not isinstance(manual_review.get("required"), bool):
        return False, "manual_review_invalid"
    manual_reason_text = _manual_reason_text(manual_review)
    if manual_reason_text is None:
        return False, "manual_review_invalid"
    if "requires_manual_review" in record and not isinstance(record.get("requires_manual_review"), bool):
        return False, "requires_manual_review_invalid"
    review_required = bool(record.get("requires_manual_review") or manual_review.get("required"))
    if record.get("retryable") is False or record.get("non_retryable") is True:
        return False, "explicitly_non_retryable"
    if record.get("index_error"):
        return False, "invalid_manifest"
    if status == "aborted_by_policy":
        return False, "aborted_by_policy"
    reason_text = " ".join(blockers + warnings + manual_reason_text).lower()
    if any(token in reason_text for token in NON_RETRYABLE_BLOCKER_TOKENS):
        return False, "policy_privacy_or_scope_blocker"
    if status == "partial" and review_required:
        return False, "manual_review_partial"
    if status == "complete":
        return False, "status_not_retryable"
    if status not in {"failed", "partial"}:
        return False, "status_invalid_or_unknown"
    if not isinstance(record.get("task"), str) or not record["task"]:
        return False, "task_missing"
    return True, "retryable_failure" if status == "failed" else "retryable_partial"


def build_retry_plan(records: list[dict[str, Any]]) -> dict[str, Any]:
    retryable: list[dict[str, Any]] = []
    non_retryable: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            non_retryable.append(
                {"run_id": None, "task": None, "path": None, "reason": [], "classification": "record_invalid_shape"}
            )
            continue
        raw_blockers = record.get("completion_blockers")
        blockers = raw_blockers if isinstance(raw_blockers, list) else []
        raw_warnings = record.get("warnings")
        warnings = raw_warnings if isinstance(raw_warnings, list) else []
        manual_review = record.get("manual_review") if isinstance(record.get("manual_review"), dict) else {}
        manual_reasons = _manual_reason_text(manual_review) or []
        can_retry, classification = classify_retryability(record)
        entry = {
            "run_id": record.get("run_id"),
            "task": record.get("task"),
            "path": record.get("path"),
            "reason": blockers or warnings or manual_reasons,
            "classification": classification,
        }
        if can_retry:
            retryable.append(entry)
        elif record.get("run_status") != "complete" or classification != "status_not_retryable":
            non_retryable.append(entry)
    return {
        "schema_version": "1.0",
        "retryable_runs": retryable,
        "non_retryable_runs": non_retryable,
        "non_retryable_policy_runs": [
            record.get("run_id")
            for record in records
            if isinstance(record, dict) and record.get("run_status") == "aborted_by_policy"
        ],
    }


def write_retry_plan(records: list[dict[str, Any]], output_path: Path) -> dict[str, Any]:
    plan = build_retry_plan(records)
    write_json(output_path, plan)
    return plan
