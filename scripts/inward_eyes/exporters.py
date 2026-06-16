from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from inward_eyes.io import write_json, write_text


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def build_run_summary(run_dir: Path) -> dict[str, Any]:
    manifest = _load_json(run_dir / "manifest.json") or {}
    return {
        "schema_version": "1.0",
        "run_id": manifest.get("run_id") or run_dir.name,
        "task": manifest.get("task"),
        "skill": manifest.get("skill"),
        "run_status": manifest.get("run_status"),
        "validation_status": manifest.get("validation_status"),
        "requires_manual_review": bool(manifest.get("requires_manual_review")),
        "manual_review": manifest.get("manual_review"),
        "artifacts": manifest.get("artifacts") or [],
        "evidence": manifest.get("evidence") or [],
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
    if summary.get("completion_blockers"):
        lines.extend(["", "## Blockers", ""])
        lines.extend(f"- {item}" for item in summary["completion_blockers"])
    if summary.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {item}" for item in summary["warnings"])
    return "\n".join(lines).rstrip() + "\n"


def export_run(run_dir: Path, output_dir: Path) -> dict[str, Path]:
    summary = build_run_summary(run_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "run-summary.json"
    csv_path = output_dir / "artifact-index.csv"
    md_path = output_dir / "run-summary.md"
    write_json(json_path, summary)
    write_text(csv_path, artifact_index_csv(summary))
    write_text(md_path, summary_markdown(summary))
    return {"json": json_path, "csv": csv_path, "markdown": md_path}
