from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from inward_eyes.paths import resolve_run_relative
from inward_eyes.run_index import canonical_manifest_shape_error
from inward_eyes.validation import validate_manifest_paths, validate_manifest_status


VALIDATION_REPORT_REQUIRED_FIELDS = {
    "schema_version",
    "status",
    "errors",
    "warnings",
    "requires_manual_review",
    "run_status",
    "validation_status",
    "manual_review",
    "completion_blockers",
}


def _load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if path.is_symlink():
        return None, "symlink"
    if not path.exists():
        return None, "missing"
    if not path.is_file():
        return None, "not_file"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None, "invalid_json"
    if not isinstance(data, dict):
        return None, "invalid_shape"
    return data, None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def _validation_report_findings(report: dict[str, Any], relative_path: str) -> tuple[list[str], list[str]]:
    blockers: list[str] = []
    warnings: list[str] = []
    missing = sorted(VALIDATION_REPORT_REQUIRED_FIELDS - report.keys())
    if missing:
        return [f"REVIEW_VALIDATION_REPORT_REQUIRED_FIELD_MISSING:{relative_path}:{missing[0]}"], []
    if not isinstance(report.get("schema_version"), str) or not report["schema_version"]:
        return [f"REVIEW_VALIDATION_REPORT_FIELD_INVALID:{relative_path}:schema_version"], []
    if report.get("status") not in {"pass", "fail"}:
        return [f"REVIEW_VALIDATION_REPORT_FIELD_INVALID:{relative_path}:status"], []
    for field in ("errors", "warnings", "completion_blockers"):
        value = report.get(field)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            return [f"REVIEW_VALIDATION_REPORT_FIELD_INVALID:{relative_path}:{field}"], []
    if not isinstance(report.get("requires_manual_review"), bool):
        return [f"REVIEW_VALIDATION_REPORT_FIELD_INVALID:{relative_path}:requires_manual_review"], []
    manual_review = report.get("manual_review")
    if not isinstance(manual_review, dict):
        return [f"REVIEW_VALIDATION_REPORT_FIELD_INVALID:{relative_path}:manual_review"], []
    if (
        not isinstance(manual_review.get("required"), bool)
        or manual_review.get("severity") not in {"info", "warning", "blocking"}
        or not isinstance(manual_review.get("reasons"), list)
    ):
        return [f"REVIEW_VALIDATION_REPORT_FIELD_INVALID:{relative_path}:manual_review"], []
    if not all(isinstance(reason, dict) for reason in manual_review["reasons"]):
        return [f"REVIEW_VALIDATION_REPORT_FIELD_INVALID:{relative_path}:manual_review.reasons"], []
    for reason in manual_review["reasons"]:
        if (
            not isinstance(reason.get("code"), str)
            or not isinstance(reason.get("message"), str)
            or reason.get("severity") not in {"info", "warning", "blocking"}
            or not isinstance(reason.get("artifact"), str)
        ):
            return [f"REVIEW_VALIDATION_REPORT_FIELD_INVALID:{relative_path}:manual_review.reasons"], []

    blockers.extend(f"REVIEW_VALIDATION_REPORT_STATUS:{relative_path}:{error}" for error in validate_manifest_status(report))
    report_errors = report["errors"]
    report_warnings = report["warnings"]
    completion_blockers = report["completion_blockers"]
    blockers.extend(report_errors)
    blockers.extend(completion_blockers)
    warnings.extend(report_warnings)
    if report.get("status") == "fail":
        blockers.append(f"REVIEW_VALIDATION_REPORT_FAILED:{relative_path}")
    elif report_errors or completion_blockers or report.get("validation_status") == "failed":
        blockers.append(f"REVIEW_VALIDATION_REPORT_STATUS_INCONSISTENT:{relative_path}")
    if report.get("run_status") in {"failed", "aborted_by_policy"}:
        blockers.append(f"REVIEW_VALIDATION_REPORT_RUN_STATUS:{relative_path}:{report.get('run_status')}")

    reason_count = 0
    for reason in manual_review["reasons"]:
        code = str(reason.get("code") or "REVIEW_REASON_UNSPECIFIED")
        reason_count += 1
        if reason.get("severity") == "blocking":
            blockers.append(code)
        else:
            warnings.append(code)
    report_review_required = bool(report.get("requires_manual_review") or manual_review.get("required"))
    if report.get("run_status") == "partial" or report_review_required:
        if not report_warnings and not reason_count:
            warnings.append(f"REVIEW_VALIDATION_REPORT_REVIEW_REQUIRED:{relative_path}")
    return blockers, warnings


def build_run_review(run_dir: Path) -> dict[str, Any]:
    manifest, manifest_error = _load_json(run_dir / "manifest.json")
    validation_reports = []
    blockers: list[str] = []
    warnings: list[str] = []
    if manifest_error == "missing":
        blockers.append("REVIEW_MANIFEST_MISSING")
    elif manifest_error:
        blockers.append(f"REVIEW_MANIFEST_{manifest_error.upper()}")
    report_paths = set((run_dir / "validation").glob("*.json"))
    if manifest is not None:
        if not manifest:
            blockers.append("REVIEW_MANIFEST_EMPTY")
        shape_error = canonical_manifest_shape_error(manifest, expected_run_id=run_dir.name)
        if shape_error:
            blockers.append(f"REVIEW_MANIFEST_SHAPE:{shape_error}")
        validation = manifest.get("validation") if isinstance(manifest.get("validation"), dict) else {}
        declared_reports = [
            value
            for key, value in validation.items()
            if (key == "report_path" or key.endswith("_report_path")) and value
        ]
        evidence = manifest.get("evidence") if isinstance(manifest.get("evidence"), list) else []
        declared_reports.extend(
            item.get("path")
            for item in evidence
            if isinstance(item, dict) and item.get("type") == "validation_report" and item.get("path")
        )
        if not declared_reports:
            blockers.append("REVIEW_VALIDATION_REPORT_UNDECLARED")
        for declared_report in declared_reports:
            try:
                report_path = resolve_run_relative(run_dir, str(declared_report))
            except ValueError:
                blockers.append(f"REVIEW_VALIDATION_REPORT_PATH_INVALID:{declared_report}")
                continue
            if report_path.suffix.lower() != ".json":
                blockers.append(f"REVIEW_VALIDATION_REPORT_NOT_JSON:{declared_report}")
                continue
            if not report_path.exists():
                blockers.append(f"REVIEW_VALIDATION_REPORT_MISSING:{declared_report}")
                continue
            if not report_path.is_file():
                blockers.append(f"REVIEW_VALIDATION_REPORT_NOT_FILE:{declared_report}")
                continue
            report_paths.add(report_path)
    for path in sorted(report_paths):
        try:
            relative_path = path.relative_to(run_dir).as_posix()
            safe_path = resolve_run_relative(run_dir, relative_path)
        except ValueError:
            blockers.append(f"REVIEW_VALIDATION_REPORT_PATH_INVALID:{path}")
            continue
        lexical_path = run_dir / Path(*relative_path.split("/"))
        if lexical_path.is_symlink():
            blockers.append(f"REVIEW_VALIDATION_REPORT_SYMLINK:{relative_path}")
            continue
        report, report_error = _load_json(safe_path)
        if report_error:
            blockers.append(f"REVIEW_VALIDATION_REPORT_{report_error.upper()}:{relative_path}")
            validation_reports.append({"path": relative_path, "report": None, "error": report_error})
        else:
            validation_reports.append({"path": relative_path, "report": report})
            report_blockers, report_warnings = _validation_report_findings(report, relative_path)
            blockers.extend(report_blockers)
            warnings.extend(report_warnings)
    missing_paths: list[str] = []
    if manifest is not None:
        blockers.extend(f"REVIEW_MANIFEST_STATUS:{error}" for error in validate_manifest_status(manifest))
        blockers.extend(f"REVIEW_MANIFEST_PATH:{error}" for error in validate_manifest_paths(run_dir, manifest))
        for section in ("artifacts", "evidence"):
            items = manifest.get(section, [])
            if not isinstance(items, list):
                blockers.append(f"REVIEW_MANIFEST_{section.upper()}_INVALID")
                continue
            for item in items:
                if not isinstance(item, dict) or not item.get("path"):
                    continue
                try:
                    declared_path = resolve_run_relative(run_dir, str(item["path"]))
                except ValueError:
                    blockers.append(f"REVIEW_INVALID_PATH:{item['path']}")
                    continue
                if not declared_path.exists():
                    missing_paths.append(str(item["path"]))
    if manifest is not None:
        blockers.extend(_string_list(manifest.get("completion_blockers")))
        warnings.extend(_string_list(manifest.get("warnings")))
        manual_review = manifest.get("manual_review") if isinstance(manifest.get("manual_review"), dict) else {}
        reasons = manual_review.get("reasons") if isinstance(manual_review.get("reasons"), list) else []
        for reason in reasons:
            if not isinstance(reason, dict):
                continue
            code = str(reason.get("code") or "REVIEW_REASON_UNSPECIFIED")
            if reason.get("severity") == "blocking":
                blockers.append(code)
            else:
                warnings.append(code)
        manifest_review_required = bool(manifest.get("requires_manual_review") or manual_review.get("required"))
        if manifest_review_required and not reasons:
            warnings.append("REVIEW_MANUAL_REVIEW_REQUIRED")
        if manifest.get("run_status") in {"failed", "aborted_by_policy"}:
            blockers.append(f"REVIEW_RUN_STATUS:{manifest.get('run_status')}")
    blockers.extend(f"REVIEW_MISSING_PATH:{path}" for path in missing_paths)
    review_required = bool(blockers or warnings or (manifest or {}).get("requires_manual_review"))
    review_status = "fail" if blockers else "review_required" if review_required else "pass"
    return {
        "schema_version": "1.0",
        "run_dir": str(run_dir),
        "manifest": manifest,
        "validation_reports": validation_reports,
        "missing_paths": missing_paths,
        "blockers": list(dict.fromkeys(blockers)),
        "warnings": list(dict.fromkeys(warnings)),
        "review_required": review_required,
        "status": review_status,
        "review_status": review_status,
    }


def render_run_review_markdown(review: dict[str, Any]) -> str:
    manifest = review.get("manifest") or {}
    lines = [
        "# Run Review",
        "",
        f"Run: `{manifest.get('run_id', 'unknown')}`",
        f"Task: `{manifest.get('task', 'unknown')}`",
        f"Run status: `{manifest.get('run_status', 'unknown')}`",
        f"Validation status: `{manifest.get('validation_status', 'unknown')}`",
        f"Review required: `{review.get('review_required')}`",
        f"Review result: `{review.get('review_status')}`",
        "",
    ]
    manual_review = manifest.get("manual_review") if isinstance(manifest.get("manual_review"), dict) else {}
    reasons = manual_review.get("reasons") if isinstance(manual_review.get("reasons"), list) else []
    if reasons:
        lines.extend(["## Manual Review Reasons", ""])
        for reason in reasons:
            if isinstance(reason, dict):
                lines.append(f"- {reason.get('severity', 'warning')}: {reason.get('code')} ({reason.get('artifact')})")
        lines.append("")
    if review.get("blockers"):
        lines.extend(["## Blockers", ""])
        lines.extend(f"- {item}" for item in review["blockers"])
        lines.append("")
    if review.get("warnings"):
        lines.extend(["## Warnings", ""])
        lines.extend(f"- {item}" for item in review["warnings"])
        lines.append("")
    if review.get("missing_paths"):
        lines.extend(["## Missing Manifest Paths", ""])
        lines.extend(f"- {item}" for item in review["missing_paths"])
        lines.append("")
    if not review.get("review_required"):
        lines.append("No blockers or warnings found.")
    elif not (review.get("blockers") or review.get("warnings") or review.get("missing_paths")):
        lines.append("Manual review is required.")
    return "\n".join(lines).rstrip() + "\n"
