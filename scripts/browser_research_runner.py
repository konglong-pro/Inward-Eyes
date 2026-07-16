from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from inward_eyes.io import utc_now, write_json, write_text
from inward_eyes.research import (
    build_research_model,
    render_missing_sources,
    render_research_report,
    render_source_notes,
    render_sources_csv,
    source_dir_name,
    source_record_from_summary,
)
from inward_eyes.paths import prepare_run_dir, resolve_run_relative
from inward_eyes.validation import validate_browser_research_run

BROWSER_RESEARCH_STAGE_MANIFEST = "validation/browser-research-stage-manifest.json"


def _slug_timestamp(timestamp: str) -> str:
    return re.sub(r"[^0-9TZ]", "", timestamp)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _sha256_bytes(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def create_manifest(
    run_dir: Path,
    run_id: str,
    started_at: str,
    finished_at: str,
    input_record: dict[str, Any],
    model: dict[str, Any],
    validation_report: dict[str, Any],
) -> dict[str, Any]:
    validation = validation_report
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
    for source in model["sources"]:
        screenshot = source.get("evidence", {}).get("screenshot") if isinstance(source.get("evidence"), dict) else None
        if not screenshot or source.get("screenshot_policy", {}).get("status") != "required_and_present":
            continue
        try:
            screenshot_path = resolve_run_relative(run_dir, str(screenshot), must_exist=True)
        except (ValueError, FileNotFoundError):
            continue
        evidence.append(
            {
                "id": f"{source['source_id']}-screenshot",
                "type": "screenshot",
                "path": screenshot,
                "sha256": _sha256_file(screenshot_path),
            }
        )
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
        "validation_status": validation.get("validation_status")
        if validation.get("validation_status") in {"passed", "failed"}
        else "failed",
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
    input_bytes = input_path.read_bytes()
    raw_input = json.loads(input_bytes.decode("utf-8"))
    if not isinstance(raw_input, dict):
        raise SystemExit("browser-research input must be a JSON object")

    started_at = utc_now()
    run_id = args.run_id or f"{_slug_timestamp(started_at)}-browser-research"
    output_root = Path(args.output_root or "browser-operator-runs").resolve()
    continue_existing = bool(getattr(args, "continue_existing_run", False))
    defer_manifest = bool(getattr(args, "defer_manifest", False))
    if continue_existing and not defer_manifest:
        raise SystemExit("authenticated continuation requires --defer-manifest")
    if defer_manifest and not continue_existing:
        raise SystemExit("deferred browser-research manifest requires authenticated continuation")
    if continue_existing and input_path != (output_root / run_id / "capture" / "research-input.json").resolve():
        raise SystemExit("continued browser-research run must consume capture/research-input.json from that run")
    if args.topic:
        raw_input["topic"] = args.topic
    if args.question:
        raw_input["question"] = args.question
    model = build_research_model(raw_input, started_at)
    run_dir = prepare_run_dir(
        output_root,
        run_id,
        continue_existing=continue_existing,
        continuation_required_paths=("capture/research-input.json",) if continue_existing else (),
        continuation_token=getattr(args, "continuation_token", None),
        continuation_stage="browser-research-render" if continue_existing else None,
        continuation_input_path="capture/research-input.json" if continue_existing else None,
        continuation_artifact_sha256=(
            {"capture/research-input.json": _sha256_bytes(input_bytes)}
            if continue_existing
            else None
        ),
    )
    (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    (run_dir / "evidence").mkdir(parents=True, exist_ok=True)
    (run_dir / "validation").mkdir(parents=True, exist_ok=True)

    input_record = {
        "input_path": str(input_path),
        "topic": raw_input.get("topic"),
        "question": raw_input.get("question"),
        "source_count": len(raw_input.get("sources", [])) if isinstance(raw_input.get("sources"), list) else 0,
    }
    write_json(run_dir / "input.json", input_record)

    write_json(run_dir / "artifacts" / "claims.json", model)
    write_text(run_dir / "artifacts" / "sources.csv", render_sources_csv(model["sources"]))
    write_text(run_dir / "artifacts" / "report.md", render_research_report(model))
    write_text(run_dir / "artifacts" / "source_notes.md", render_source_notes(model))

    for source in model["sources"]:
        source_dir = run_dir / "evidence" / source_dir_name(source["source_id"])
        source_dir.mkdir(parents=True, exist_ok=True)
        write_json(source_dir / "source_record.json", source_record_from_summary(source))

    write_text(
        run_dir / "validation" / "missing-sources.md",
        "# Missing Sources\n\nPending in-memory validation.\n",
    )
    pending_validation_paths = {
        "validation/claim-coverage-report.json",
        "validation/missing-sources.md",
    }
    final_validation_report = validate_browser_research_run(
        run_dir,
        manifest_override={},
        pending_manifest_paths=pending_validation_paths,
        skip_manifest_validation=True,
    )
    final_manifest: dict[str, Any] | None = None
    for _ in range(4):
        candidate_manifest = create_manifest(
            run_dir,
            run_id,
            started_at,
            utc_now(),
            input_record,
            model,
            final_validation_report,
        )
        checked_report = validate_browser_research_run(
            run_dir,
            manifest_override=candidate_manifest,
            pending_manifest_paths=pending_validation_paths,
        )
        if checked_report == final_validation_report:
            final_manifest = candidate_manifest
            break
        final_validation_report = checked_report
    if final_manifest is None:
        raise RuntimeError("browser-research manifest validation did not converge")
    write_text(run_dir / "validation" / "missing-sources.md", render_missing_sources(final_validation_report))
    write_json(run_dir / "validation" / "claim-coverage-report.json", final_validation_report)
    manifest_output = BROWSER_RESEARCH_STAGE_MANIFEST if defer_manifest else "manifest.json"
    write_json(resolve_run_relative(run_dir, manifest_output), final_manifest)
    print(run_dir)
    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Render and validate a source-backed browser research run.")
    parser.add_argument("--input", required=True, help="Local browser-research input JSON.")
    parser.add_argument("--output-root", default="browser-operator-runs", help="Directory where run outputs are written.")
    parser.add_argument("--run-id", help="Optional run id.")
    parser.add_argument("--topic", help="Override research topic.")
    parser.add_argument("--question", help="Override research question.")
    parser.add_argument(
        "--continue-existing-run",
        action="store_true",
        help="Continue a capture-orchestrated run using its canonical capture/research-input.json.",
    )
    parser.add_argument("--continuation-token", help=argparse.SUPPRESS)
    parser.add_argument("--defer-manifest", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
