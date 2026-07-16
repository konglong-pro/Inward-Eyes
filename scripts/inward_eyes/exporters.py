from __future__ import annotations

import csv
import io
import json
import os
import re
from pathlib import Path
from typing import Any

from inward_eyes.io import write_json, write_text
from inward_eyes.paths import resolve_run_relative
from inward_eyes.run_index import canonical_manifest_shape_error, find_canonical_run_ancestor
from inward_eyes.validation import validate_manifest_paths, validate_manifest_status


SOURCE_RECORD_TASKS = {"page-to-md", "browser-research", "price-compare"}
EXPORTABLE_TASKS = SOURCE_RECORD_TASKS | {
    "adapter-matrix",
    "batch",
    "capture-adapter",
    "privacy-report",
    "site-profiles",
}
SOURCE_ID_PATTERN = re.compile(r"^S[0-9]{3}$")
SOURCE_RECORD_REQUIRED_FIELDS = {
    "source_id",
    "url",
    "title",
    "page_type",
    "accessed_at",
    "requires_login",
    "capture_method",
    "evidence",
    "screenshot_policy",
    "content_scope",
    "warnings",
}
PAGE_TYPES = {"article", "blog", "docs", "x_thread", "forum_thread", "product_page", "unknown"}
SCREENSHOT_STATUSES = {
    "required_and_present",
    "required_but_missing",
    "not_required",
    "capture_failed",
    "redacted",
}


class ExportError(ValueError):
    pass


def _load_json(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink():
        raise ExportError(f"{label} must not be a symlink: {path}")
    if not path.exists():
        raise ExportError(f"{label} missing: {path}")
    if not path.is_file():
        raise ExportError(f"{label} must be a regular file: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ExportError(f"{label} is not valid JSON: {path}") from exc
    if not isinstance(data, dict):
        raise ExportError(f"{label} must be a JSON object: {path}")
    return data


def _validate_source_record(
    source: dict[str, Any],
    path: str,
    run_dir: Path,
    source_path: Path,
    declared_evidence: dict[str, dict[str, Any]],
) -> None:
    missing = sorted(SOURCE_RECORD_REQUIRED_FIELDS - source.keys())
    if missing:
        raise ExportError(f"source record missing required fields at {path}: {', '.join(missing)}")
    if not SOURCE_ID_PATTERN.fullmatch(str(source.get("source_id") or "")):
        raise ExportError(f"source record has invalid source_id at {path}")
    if not isinstance(source.get("url"), str) or not source["url"]:
        raise ExportError(f"source record has invalid url at {path}")
    if not isinstance(source.get("accessed_at"), str) or not source["accessed_at"]:
        raise ExportError(f"source record has invalid accessed_at at {path}")
    if not isinstance(source.get("capture_method"), str) or not source["capture_method"]:
        raise ExportError(f"source record has invalid capture_method at {path}")
    if source.get("page_type") not in PAGE_TYPES:
        raise ExportError(f"source record has invalid page_type at {path}")
    for field in ("canonical_url", "title", "site_name"):
        if source.get(field) is not None and not isinstance(source.get(field), str):
            raise ExportError(f"source record has invalid {field} at {path}")
    if not isinstance(source.get("requires_login"), bool):
        raise ExportError(f"source record has invalid requires_login at {path}")
    for field in ("evidence", "screenshot_policy", "content_scope"):
        if not isinstance(source.get(field), dict):
            raise ExportError(f"source record has invalid {field} at {path}")
    if not isinstance(source.get("warnings"), list) or not all(isinstance(item, str) for item in source["warnings"]):
        raise ExportError(f"source record has invalid warnings at {path}")
    content_scope = source["content_scope"]
    if not isinstance(content_scope.get("included"), list) or not isinstance(content_scope.get("excluded"), list):
        raise ExportError(f"source record has invalid content_scope lists at {path}")
    if not all(
        isinstance(item, str)
        for field in ("included", "excluded")
        for item in content_scope[field]
    ):
        raise ExportError(f"source record has non-string content_scope entries at {path}")
    screenshot_policy = source["screenshot_policy"]
    if not all(field in screenshot_policy for field in ("required", "reason", "status")):
        raise ExportError(f"source record has incomplete screenshot_policy at {path}")
    if (
        not isinstance(screenshot_policy.get("required"), bool)
        or not isinstance(screenshot_policy.get("reason"), str)
        or screenshot_policy.get("status") not in SCREENSHOT_STATUSES
    ):
        raise ExportError(f"source record has invalid screenshot_policy at {path}")
    evidence = source["evidence"]
    resolved_evidence: dict[str, Path] = {}
    for field in ("screenshot", "snapshot", "source_record"):
        raw_path = evidence.get(field)
        if raw_path is None:
            continue
        if not isinstance(raw_path, str) or not raw_path:
            raise ExportError(f"source record has invalid evidence.{field} at {path}")
        try:
            resolved_path = resolve_run_relative(run_dir, raw_path)
        except ValueError as exc:
            raise ExportError(f"source record evidence path escapes run directory at {path}: {field}") from exc
        if not resolved_path.exists():
            raise ExportError(f"source record evidence path missing at {path}: {field}")
        if not resolved_path.is_file():
            raise ExportError(f"source record evidence path is not a file at {path}: {field}")
        if raw_path not in declared_evidence:
            raise ExportError(f"source record evidence path is not declared by manifest at {path}: {field}")
        expected_type = {"screenshot": "screenshot", "source_record": "source_record"}.get(field)
        if expected_type and declared_evidence[raw_path].get("type") != expected_type:
            raise ExportError(
                f"source record evidence path has wrong manifest type at {path}: "
                f"{field} expected {expected_type}"
            )
        resolved_evidence[field] = resolved_path
    if "source_record" not in resolved_evidence:
        raise ExportError(f"source record evidence.source_record missing at {path}")
    if resolved_evidence["source_record"] != source_path.resolve():
        raise ExportError(f"source record evidence.source_record does not match manifest path at {path}")
    screenshot_status = screenshot_policy["status"]
    screenshot_required = screenshot_policy["required"]
    if screenshot_status == "required_and_present":
        if not screenshot_required or "screenshot" not in resolved_evidence:
            raise ExportError(f"source record required screenshot evidence missing at {path}")
    if screenshot_required and screenshot_status == "not_required":
        raise ExportError(f"source record screenshot policy is inconsistent at {path}")
    if not screenshot_required and screenshot_status in {"required_and_present", "required_but_missing"}:
        raise ExportError(f"source record screenshot policy is inconsistent at {path}")


def _source_records(run_dir: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    evidence = manifest.get("evidence")
    if not isinstance(evidence, list):
        raise ExportError("manifest evidence must be an array")
    declared_evidence: dict[str, dict[str, Any]] = {}
    for item in evidence:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not item["path"]:
            continue
        if item["path"] in declared_evidence:
            raise ExportError(f"duplicate evidence path in manifest: {item['path']}")
        declared_evidence[item["path"]] = item
    declared = [item for item in evidence if isinstance(item, dict) and item.get("type") == "source_record"]
    if manifest.get("task") in SOURCE_RECORD_TASKS and not declared:
        raise ExportError(f"manifest for {manifest.get('task')} declares no canonical source records")
    records: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    seen_source_ids: set[str] = set()
    for item in declared:
        raw_path = item.get("path")
        if not isinstance(raw_path, str) or not raw_path:
            raise ExportError("source record evidence entry is missing a path")
        normalized_path = raw_path
        if normalized_path in seen_paths:
            raise ExportError(f"duplicate source record path in manifest: {normalized_path}")
        seen_paths.add(normalized_path)
        try:
            source_path = resolve_run_relative(run_dir, normalized_path)
        except ValueError as exc:
            raise ExportError(f"source record path escapes run directory: {normalized_path}") from exc
        source = _load_json(source_path, "source record")
        _validate_source_record(source, normalized_path, run_dir, source_path, declared_evidence)
        source_id = str(source["source_id"])
        if manifest.get("task") == "page-to-md":
            expected_path = "evidence/source_record.json"
        else:
            expected_path = f"evidence/source-{int(source_id[1:]):03d}/source_record.json"
        if normalized_path != expected_path:
            raise ExportError(
                f"source record path does not match source_id at {normalized_path}: "
                f"{source_id} requires {expected_path}"
            )
        if source_id in seen_source_ids:
            raise ExportError(f"duplicate source_id in canonical source records: {source_id}")
        seen_source_ids.add(source_id)
        records.append(
            {
                "manifest_evidence_id": item.get("id"),
                "source_record_path": normalized_path,
                "manifest_sha256": item.get("sha256"),
                "record": source,
            }
        )
    return records


def build_run_summary(run_dir: Path) -> dict[str, Any]:
    manifest = _load_json(run_dir / "manifest.json", "manifest")
    shape_error = canonical_manifest_shape_error(manifest, expected_run_id=run_dir.name)
    if shape_error:
        raise ExportError(f"manifest shape is invalid: {shape_error}")
    if manifest["task"] not in EXPORTABLE_TASKS:
        raise ExportError(f"manifest task is not exportable: {manifest['task']}")
    status_errors = validate_manifest_status(manifest)
    if status_errors:
        raise ExportError(f"manifest status is inconsistent: {status_errors[0]}")
    artifacts = manifest.get("artifacts")
    evidence = manifest.get("evidence")
    if not isinstance(artifacts, list):
        raise ExportError("manifest artifacts must be an array")
    if not isinstance(evidence, list):
        raise ExportError("manifest evidence must be an array")
    source_records = _source_records(run_dir, manifest)
    path_errors = validate_manifest_paths(run_dir, manifest)
    if path_errors:
        raise ExportError(f"manifest path is inconsistent: {path_errors[0]}")
    return {
        "schema_version": "1.0",
        "run_id": manifest.get("run_id") or run_dir.name,
        "task": manifest.get("task"),
        "skill": manifest.get("skill"),
        "run_status": manifest.get("run_status"),
        "validation_status": manifest.get("validation_status"),
        "requires_manual_review": bool(manifest.get("requires_manual_review")),
        "manual_review": manifest.get("manual_review"),
        "artifacts": artifacts,
        "evidence": evidence,
        "source_count": len(source_records),
        "source_records": source_records,
        "warnings": manifest.get("warnings") or [],
        "completion_blockers": manifest.get("completion_blockers") or [],
    }


def artifact_index_csv(summary: dict[str, Any]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["section", "id", "type", "path"], lineterminator="\n")
    writer.writeheader()
    for section in ("artifacts", "evidence"):
        for item in summary.get(section, []):
            if not isinstance(item, dict):
                continue
            writer.writerow(
                {
                    "section": section,
                    "id": item.get("id"),
                    "type": item.get("type"),
                    "path": item.get("path"),
                }
            )
    return output.getvalue()


def source_index_csv(summary: dict[str, Any]) -> str:
    output = io.StringIO()
    fieldnames = [
        "manifest_evidence_id",
        "source_id",
        "url",
        "canonical_url",
        "title",
        "page_type",
        "accessed_at",
        "capture_method",
        "source_record_path",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for item in summary.get("source_records", []):
        if not isinstance(item, dict) or not isinstance(item.get("record"), dict):
            continue
        record = item["record"]
        writer.writerow(
            {
                "manifest_evidence_id": item.get("manifest_evidence_id"),
                "source_id": record.get("source_id"),
                "url": record.get("url"),
                "canonical_url": record.get("canonical_url"),
                "title": record.get("title"),
                "page_type": record.get("page_type"),
                "accessed_at": record.get("accessed_at"),
                "capture_method": record.get("capture_method"),
                "source_record_path": item.get("source_record_path"),
            }
        )
    return output.getvalue()


def summary_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Run Export",
        "",
        f"Run: `{summary.get('run_id')}`",
        f"Task: `{summary.get('task')}`",
        f"Run status: `{summary.get('run_status')}`",
        f"Validation status: `{summary.get('validation_status')}`",
        f"Manual review: `{summary.get('requires_manual_review')}`",
        "",
        "## Artifacts",
        "",
    ]
    for item in summary.get("artifacts", []):
        if isinstance(item, dict):
            lines.append(f"- {item.get('id')}: {item.get('type')} -> `{item.get('path')}`")
    lines.extend(["", "## Evidence", ""])
    for item in summary.get("evidence", []):
        if isinstance(item, dict):
            lines.append(f"- {item.get('id')}: {item.get('type')} -> `{item.get('path')}`")
    lines.extend(["", "## Canonical Sources", ""])
    source_records = summary.get("source_records", [])
    if not source_records:
        lines.append("No canonical source records declared for this run type.")
    for item in source_records:
        if not isinstance(item, dict) or not isinstance(item.get("record"), dict):
            continue
        record = item["record"]
        lines.append(
            f"- {record.get('source_id')}: {record.get('title') or 'Untitled'} "
            f"({record.get('url')}) -> `{item.get('source_record_path')}`"
        )
    if summary.get("completion_blockers"):
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- {item}" for item in summary["completion_blockers"])
    if summary.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {item}" for item in summary["warnings"])
    return "\n".join(lines).rstrip() + "\n"


def export_run(run_dir: Path, output_dir: Path) -> dict[str, Path]:
    summary = build_run_summary(run_dir)
    resolved_run_dir = run_dir.resolve()
    lexical_output_dir = Path(os.path.abspath(output_dir))
    resolved_output_dir = lexical_output_dir.resolve(strict=False)
    run_ancestor = find_canonical_run_ancestor(resolved_output_dir)
    if run_ancestor is not None and run_ancestor.resolve() != resolved_run_dir:
        raise ExportError(f"export output must not modify another canonical run: {run_ancestor}")
    try:
        output_relative = lexical_output_dir.relative_to(resolved_run_dir)
    except ValueError:
        output_relative = None
    if output_relative is not None:
        if not output_relative.parts:
            raise ExportError("export output directory must not be the run root")
        if output_relative.parts[0] != "exports":
            raise ExportError("export output inside the source run must stay under the derived exports/ directory")
        current = resolved_run_dir
        for part in output_relative.parts:
            current = current / part
            if current.is_symlink():
                raise ExportError(f"export output path must not traverse a symlink inside the source run: {current}")
        try:
            resolved_output_dir.relative_to(resolved_run_dir / "exports")
        except ValueError as exc:
            raise ExportError("export output path resolves outside the source run exports/ directory") from exc
    lexical_output_dir.mkdir(parents=True, exist_ok=True)
    json_path = lexical_output_dir / "run-summary.json"
    csv_path = lexical_output_dir / "artifact-index.csv"
    source_csv_path = lexical_output_dir / "source-index.csv"
    md_path = lexical_output_dir / "run-summary.md"
    write_json(json_path, summary)
    write_text(csv_path, artifact_index_csv(summary))
    write_text(source_csv_path, source_index_csv(summary))
    write_text(md_path, summary_markdown(summary))
    return {"json": json_path, "csv": csv_path, "source_csv": source_csv_path, "markdown": md_path}
