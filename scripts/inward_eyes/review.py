from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def build_run_review(run_dir: Path) -> dict[str, Any]:
    manifest = _load_json(run_dir / "manifest.json")
    validation_reports = []
    for path in sorted((run_dir / "validation").glob("*.json")):
        report = _load_json(path)
        if report is not None:
            validation_reports.append({"path": path.relative_to(run_dir).as_posix(), "report": report})
    missing_paths: list[str] = []
    if manifest:
        for section in ("artifacts", "evidence"):
            for item in manifest.get(section, []):
                if not isinstance(item, dict) or not item.get("path"):
                    continue
                if not (run_dir / str(item["path"])).exists():
                    missing_paths.append(str(item["path"]))
    blockers: list[str] = []
    warnings: list[str] = []
    if not manifest:
        blockers.append("REVIEW_MANIFEST_MISSING")
    elif manifest.get("completion_blockers"):
        blockers.extend(str(item) for item in manifest.get("completion_blockers", []))
    for item in validation_reports:
        report = item["report"]
        blockers.extend(str(error) for error in report.get("errors", []))
        warnings.extend(str(warning) for warning in report.get("warnings", []))
    blockers.extend(f"REVIEW_MISSING_PATH:{path}" for path in missing_paths)
    review_required = bool(blockers or warnings or (manifest or {}).get("requires_manual_review"))
    return {
        "schema_version": "1.0",
        "run_dir": str(run_dir),
        "manifest": manifest,
        "validation_reports": validation_reports,
        "missing_paths": missing_paths,
        "blockers": list(dict.fromkeys(blockers)),
        "warnings": list(dict.fromkeys(warnings)),
        "review_required": review_required,
        "status": "fail" if blockers else "pass",
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
    if not (review.get("blockers") or review.get("warnings") or review.get("missing_paths")):
        lines.append("No blockers or warnings found.")
    return "\n".join(lines).rstrip() + "\n"
