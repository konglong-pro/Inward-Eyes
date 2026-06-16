from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from inward_eyes.io import write_json, write_text


def _read_manifest(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def summarize_run(run_dir: Path, output_root: Path) -> dict[str, Any] | None:
    manifest = _read_manifest(run_dir / "manifest.json")
    if not manifest:
        return None
    return {
        "run_id": manifest.get("run_id") or run_dir.name,
        "task": manifest.get("task"),
        "skill": manifest.get("skill"),
        "run_status": manifest.get("run_status"),
        "validation_status": manifest.get("validation_status"),
        "requires_manual_review": bool(manifest.get("requires_manual_review")),
        "started_at": manifest.get("started_at"),
        "finished_at": manifest.get("finished_at"),
        "path": run_dir.resolve().relative_to(output_root.resolve()).as_posix(),
        "completion_blockers": manifest.get("completion_blockers") or [],
        "warnings": manifest.get("warnings") or [],
    }


def index_runs(output_root: Path) -> list[dict[str, Any]]:
    if not output_root.exists():
        return []
    records = []
    for manifest_path in sorted(output_root.rglob("manifest.json")):
        run_dir = manifest_path.parent
        record = summarize_run(run_dir, output_root)
        if record:
            records.append(record)
    return sorted(records, key=lambda item: str(item.get("started_at") or ""))


def write_run_index(output_root: Path, index_path: Path) -> list[dict[str, Any]]:
    records = index_runs(output_root)
    lines = [json.dumps(record, ensure_ascii=False, sort_keys=True) for record in records]
    write_text(index_path, "\n".join(lines) + ("\n" if lines else ""))
    return records


def build_retry_plan(records: list[dict[str, Any]]) -> dict[str, Any]:
    retryable = []
    for record in records:
        blockers = [str(item) for item in record.get("completion_blockers", [])]
        policy_blocked = record.get("run_status") == "aborted_by_policy" or any("policy_blocked" in item for item in blockers)
        if record.get("run_status") in {"failed", "partial"} and not policy_blocked:
            retryable.append(
                {
                    "run_id": record.get("run_id"),
                    "task": record.get("task"),
                    "path": record.get("path"),
                    "reason": blockers or record.get("warnings", []),
                }
            )
    return {
        "schema_version": "1.0",
        "retryable_runs": retryable,
        "non_retryable_policy_runs": [
            record.get("run_id")
            for record in records
            if record.get("run_status") == "aborted_by_policy"
        ],
    }


def write_retry_plan(records: list[dict[str, Any]], output_path: Path) -> dict[str, Any]:
    plan = build_retry_plan(records)
    write_json(output_path, plan)
    return plan
