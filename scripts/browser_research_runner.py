from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from inward_eyes.io import read_json, utc_now, write_json, write_text
from inward_eyes.research import (
    build_research_model,
    render_missing_sources,
    render_research_report,
    render_source_notes,
    render_sources_csv,
    source_dir_name,
    source_record_from_summary,
)
from inward_eyes.validation import validate_browser_research_run


def _slug_timestamp(timestamp: str) -> str:
    return re.sub(r"[^0-9TZ]", "", timestamp)


def create_manifest(
    run_id: str,
    started_at: str,
    finished_at: str,
    input_record: dict[str, Any],
    model: dict[str, Any],
    validation_report: dict[str, Any] | None,
) -> dict[str, Any]:
    validation = validation_report or {
        "status": "pending",
        "warnings": [],
        "requires_manual_review": False,
        "run_status": "complete",
        "validation_status": "pending",
        "manual_review": {"required": False, "severity": "info", "reasons": []},
        "completion_blockers": [],
    }
    evidence = [
        {
            "id": source["source_id"],
            "type": "source_record",
            "path": source["evidence_path"],
            "url": source.get("url"),
            "captured_at": source.get("accessed_at"),
        }
        for source in model["sources"]
    ]
    if validation_report is not None:
        evidence.append(
            {
                "id": "V001",
                "type": "validation_report",
                "path": "validation/claim-coverage-report.json",
            }
        )

    return {
        "run_id": run_id,
        "task": "browser-research",
        "started_at": started_at,
        "finished_at": finished_at,
        "operator": "codex",
        "skill": "browser-research",
        "inputs": input_record,
        "artifacts": [
            {"id": "A001", "type": "markdown_report", "path": "artifacts/report.md"},
            {"id": "A002", "type": "claim_ledger", "path": "artifacts/claims.json"},
            {"id": "A003", "type": "sources_csv", "path": "artifacts/sources.csv"},
            {"id": "A004", "type": "source_notes", "path": "artifacts/source_notes.md"},
        ],
        "evidence": evidence,
        "validation": {
            "schema_valid": validation.get("status") == "pass",
            "warnings": len(validation.get("warnings", [])),
            "requires_manual_review": bool(validation.get("requires_manual_review")),
            "report_path": "validation/claim-coverage-report.json",
            "missing_sources_path": "validation/missing-sources.md",
        },
        "warnings": list(model.get("warnings") or []) + list(validation.get("warnings", [])),
        "requires_manual_review": bool(validation.get("requires_manual_review")),
        "run_status": validation.get("run_status", "failed" if validation.get("status") == "fail" else "partial" if validation.get("requires_manual_review") else "complete"),
        "validation_status": validation.get("validation_status", "passed" if validation.get("status") == "pass" else "failed" if validation.get("status") == "fail" else "pending"),
        "manual_review": validation.get(
            "manual_review",
            {"required": bool(validation.get("requires_manual_review")), "severity": "warning" if validation.get("requires_manual_review") else "info", "reasons": []},
        ),
        "completion_blockers": validation.get("completion_blockers", []),
        "screenshot_policy": {"required": False, "reason": "per_source_policy", "status": "not_required"},
    }


def run(args: argparse.Namespace) -> Path:
    input_path = Path(args.input).resolve()
    if not input_path.exists():
        raise SystemExit(f"input does not exist: {input_path}")

    started_at = utc_now()
    run_id = args.run_id or f"{_slug_timestamp(started_at)}-browser-research"
    output_root = Path(args.output_root or "browser-operator-runs").resolve()
    run_dir = output_root / run_id
    (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    (run_dir / "evidence").mkdir(parents=True, exist_ok=True)
    (run_dir / "validation").mkdir(parents=True, exist_ok=True)

    raw_input = read_json(input_path)
    if args.topic:
        raw_input["topic"] = args.topic
    if args.question:
        raw_input["question"] = args.question

    input_record = {
        "input_path": str(input_path),
        "topic": raw_input.get("topic"),
        "question": raw_input.get("question"),
        "source_count": len(raw_input.get("sources", [])) if isinstance(raw_input.get("sources"), list) else 0,
    }
    write_json(run_dir / "input.json", input_record)

    model = build_research_model(raw_input, started_at)
    write_json(run_dir / "artifacts" / "claims.json", model)
    write_text(run_dir / "artifacts" / "sources.csv", render_sources_csv(model["sources"]))
    write_text(run_dir / "artifacts" / "report.md", render_research_report(model))
    write_text(run_dir / "artifacts" / "source_notes.md", render_source_notes(model))

    for source in model["sources"]:
        source_dir = run_dir / "evidence" / source_dir_name(source["source_id"])
        source_dir.mkdir(parents=True, exist_ok=True)
        write_json(source_dir / "source_record.json", source_record_from_summary(source))

    write_text(run_dir / "validation" / "missing-sources.md", "# Missing Sources\n\nPending validation.\n")
    draft_manifest = create_manifest(run_id, started_at, utc_now(), input_record, model, None)
    write_json(run_dir / "manifest.json", draft_manifest)

    validation_report = validate_browser_research_run(run_dir)
    write_json(run_dir / "validation" / "claim-coverage-report.json", validation_report)
    write_text(run_dir / "validation" / "missing-sources.md", render_missing_sources(validation_report))

    final_manifest = create_manifest(run_id, started_at, utc_now(), input_record, model, validation_report)
    write_json(run_dir / "manifest.json", final_manifest)
    final_validation_report = validate_browser_research_run(run_dir)
    write_json(run_dir / "validation" / "claim-coverage-report.json", final_validation_report)
    write_text(run_dir / "validation" / "missing-sources.md", render_missing_sources(final_validation_report))
    final_manifest = create_manifest(run_id, started_at, utc_now(), input_record, model, final_validation_report)
    write_json(run_dir / "manifest.json", final_manifest)
    print(run_dir)
    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Render and validate a source-backed browser research run.")
    parser.add_argument("--input", required=True, help="Local browser-research input JSON.")
    parser.add_argument("--output-root", default="browser-operator-runs", help="Directory where run outputs are written.")
    parser.add_argument("--run-id", help="Optional run id.")
    parser.add_argument("--topic", help="Override research topic.")
    parser.add_argument("--question", help="Override research question.")
    args = parser.parse_args()
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
