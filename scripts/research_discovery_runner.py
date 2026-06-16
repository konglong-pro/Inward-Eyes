from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from inward_eyes.discovery import (  # noqa: E402
    DEFAULT_MAX_SOURCES,
    build_discovery_log,
    render_discovery_log,
    validate_research_discovery_run,
)
from inward_eyes.io import read_json, utc_now, write_json, write_text  # noqa: E402
from inward_eyes.research import source_dir_name  # noqa: E402
from inward_eyes.validation import validate_browser_research_run  # noqa: E402


def _slug_timestamp(timestamp: str) -> str:
    return re.sub(r"[^0-9TZ]", "", timestamp)


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _strings(value: Any) -> list[str]:
    return [str(item) for item in _as_list(value) if str(item).strip()]


def _load_spec(args: argparse.Namespace) -> dict[str, Any]:
    spec: dict[str, Any] = {}
    if args.input:
        loaded = read_json(Path(args.input).resolve())
        if not isinstance(loaded, dict):
            raise SystemExit("M10A discovery input JSON must be an object")
        spec.update(loaded)
    if args.question:
        spec["research_question"] = args.question
    if args.topic:
        spec["topic"] = args.topic
    if args.discovery_mode:
        spec["discovery_mode"] = args.discovery_mode
    if args.max_sources is not None:
        spec["max_sources"] = args.max_sources
    if args.allowed_domain:
        spec["allowed_domains"] = args.allowed_domain
    if args.allowed_source_type:
        spec["allowed_source_types"] = args.allowed_source_type
    if args.excluded_domain:
        spec["excluded_domains"] = args.excluded_domain
    if args.excluded_source_type:
        spec["excluded_source_types"] = args.excluded_source_type
    if args.query:
        spec["search_queries"] = args.query
    if args.candidate_url:
        spec.setdefault("candidates", [])
        spec["candidates"].extend(
            {
                "url": url,
                "title": url,
                "source_type": "web_page",
                "selection_rationale": "CLI candidate URL within approved discovery scope",
            }
            for url in args.candidate_url
        )
    if args.claims_file:
        claims_doc = read_json(Path(args.claims_file).resolve())
        if not isinstance(claims_doc, dict):
            raise SystemExit("--claims-file must point to a JSON object")
        for key in ("summary", "claims", "unknowns", "warnings"):
            if key in claims_doc:
                spec[key] = claims_doc[key]

    spec.setdefault("discovery_mode", "candidate_list")
    spec.setdefault("max_sources", DEFAULT_MAX_SOURCES)
    spec.setdefault("selection_rationale_required", True)
    return spec


def _validation_report(errors: list[str], warnings: list[str] | None = None) -> dict[str, Any]:
    warnings = warnings or []
    status = "fail" if errors else "pass"
    severity = "blocking" if errors else "warning" if warnings else "info"
    return {
        "schema_version": "1.0",
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "requires_manual_review": bool(errors or warnings),
        "run_status": "failed" if errors else "partial" if warnings else "complete",
        "validation_status": "failed" if errors else "passed",
        "manual_review": {
            "required": bool(errors or warnings),
            "severity": severity,
            "reasons": [
                {
                    "code": code,
                    "message": code.replace("_", " "),
                    "severity": "blocking" if errors else "warning",
                    "artifact": "validation/discovery-validation-report.json",
                }
                for code in (errors or warnings)
            ],
        },
        "completion_blockers": errors,
        "screenshot_policy": {"required": False, "reason": "per_source_policy", "status": "not_required"},
    }


def _write_warnings(path: Path, warnings: list[str]) -> None:
    if not warnings:
        write_text(path, "No warnings.\n")
        return
    lines = ["# Warnings", ""]
    lines.extend(f"- {warning}" for warning in warnings)
    write_text(path, "\n".join(lines) + "\n")


def _base_manifest(
    *,
    run_id: str,
    started_at: str,
    input_record: dict[str, Any],
    report: dict[str, Any],
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "task": "browser-research",
        "started_at": started_at,
        "finished_at": utc_now(),
        "operator": "codex",
        "skill": "browser-research",
        "inputs": input_record,
        "artifacts": [],
        "evidence": [
            {
                "id": "DVAL001",
                "type": "validation_report",
                "path": "validation/discovery-validation-report.json",
            }
        ],
        "validation": {
            "schema_valid": report.get("status") == "pass",
            "warnings": len(report.get("warnings", [])),
            "requires_manual_review": bool(report.get("requires_manual_review")),
            "report_path": "validation/discovery-validation-report.json",
            "missing_sources_path": "validation/missing-sources.md",
        },
        "warnings": report.get("warnings", []),
        "requires_manual_review": bool(report.get("requires_manual_review")),
        "run_status": report.get("run_status", "failed"),
        "validation_status": report.get("validation_status", "failed"),
        "manual_review": report.get("manual_review", {"required": True, "severity": "blocking", "reasons": []}),
        "completion_blockers": report.get("completion_blockers", []),
        "screenshot_policy": {"required": False, "reason": "per_source_policy", "status": "not_required"},
    }


def _write_discovery_only_run(
    run_dir: Path,
    *,
    run_id: str,
    started_at: str,
    input_record: dict[str, Any],
    report: dict[str, Any],
    discovery_log: dict[str, Any] | None = None,
) -> None:
    (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    (run_dir / "validation").mkdir(parents=True, exist_ok=True)
    write_json(run_dir / "input.json", input_record)
    if discovery_log is not None:
        write_json(run_dir / "artifacts" / "discovery-log.json", discovery_log)
        write_text(run_dir / "artifacts" / "discovery-log.md", render_discovery_log(discovery_log))
    write_json(run_dir / "validation" / "discovery-validation-report.json", report)
    write_text(run_dir / "validation" / "missing-sources.md", "# Missing Sources\n\nDiscovery did not select sources.\n")
    _write_warnings(run_dir / "validation" / "warnings.md", report.get("warnings", []))
    manifest = _base_manifest(run_id=run_id, started_at=started_at, input_record=input_record, report=report)
    if discovery_log is not None:
        manifest["artifacts"] = [
            {"id": "D001", "type": "discovery_log_json", "path": "artifacts/discovery-log.json"},
            {"id": "D002", "type": "discovery_log_markdown", "path": "artifacts/discovery-log.md"},
        ]
    write_json(run_dir / "manifest.json", manifest)


def _raw_candidates(spec: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in _as_list(spec.get("candidates") or spec.get("candidate_sources")) if isinstance(item, dict)]


def _selected_capture_sources(discovery_log: dict[str, Any], spec: dict[str, Any]) -> list[dict[str, Any]]:
    raw_candidates = _raw_candidates(spec)
    candidate_records = {
        str(candidate.get("candidate_id")): candidate
        for candidate in discovery_log.get("candidates", [])
        if isinstance(candidate, dict)
    }
    sources: list[dict[str, Any]] = []
    for selected in discovery_log.get("selected_sources", []):
        if not isinstance(selected, dict):
            continue
        candidate_record = candidate_records.get(str(selected.get("candidate_id"))) or {}
        input_index = int(candidate_record.get("input_index") or 0)
        raw = raw_candidates[input_index - 1] if 0 < input_index <= len(raw_candidates) else {}
        source: dict[str, Any] = {
            "source_id": selected["source_id"],
            "url": selected["url"],
            "approved": True,
            "page_title": raw.get("page_title") or selected.get("title") or selected["url"],
            "title": raw.get("title") or selected.get("title") or selected["url"],
            "source_type": raw.get("source_type") or selected.get("source_type") or "web_page",
            "page_type": raw.get("page_type") or "unknown",
            "selection_rationale": selected.get("selection_rationale"),
            "notes": raw.get("notes") or selected.get("selection_rationale"),
        }
        for key in (
            "canonical_url",
            "site_name",
            "selected_main_content",
            "selected_main_content_file",
            "html",
            "html_file",
            "text",
            "text_file",
            "accessibility_snapshot",
            "accessibility_snapshot_file",
            "screenshot",
            "screenshots",
            "screenshot_required",
            "screenshot_reason",
            "failure_reason",
            "warnings",
            "actions",
            "independence",
            "independence_note",
            "content_scope",
            "included",
            "excluded",
            "capture_backend",
            "backend",
            "capture_id",
            "published_at",
        ):
            if key in raw:
                source[key] = raw[key]
        sources.append(source)
    return sources


def _write_discovery_artifacts(run_dir: Path, discovery_log: dict[str, Any]) -> None:
    write_json(run_dir / "artifacts" / "discovery-log.json", discovery_log)
    write_text(run_dir / "artifacts" / "discovery-log.md", render_discovery_log(discovery_log))


def _upsert_path_record(records: list[dict[str, Any]], record: dict[str, Any]) -> None:
    path = record.get("path")
    for index, item in enumerate(records):
        if isinstance(item, dict) and item.get("path") == path:
            records[index] = {**item, **record}
            return
    records.append(record)


def _merge_manifest(
    run_dir: Path,
    *,
    input_record: dict[str, Any],
    discovery_report: dict[str, Any],
    claim_report: dict[str, Any] | None = None,
) -> None:
    manifest_path = run_dir / "manifest.json"
    manifest = read_json(manifest_path)
    artifacts = [item for item in manifest.get("artifacts", []) if isinstance(item, dict)]
    evidence = [item for item in manifest.get("evidence", []) if isinstance(item, dict)]
    _upsert_path_record(artifacts, {"id": "D001", "type": "discovery_log_json", "path": "artifacts/discovery-log.json"})
    _upsert_path_record(artifacts, {"id": "D002", "type": "discovery_log_markdown", "path": "artifacts/discovery-log.md"})
    _upsert_path_record(
        evidence,
        {"id": "DVAL001", "type": "validation_report", "path": "validation/discovery-validation-report.json"},
    )

    claim_report = claim_report or read_json(run_dir / "validation" / "claim-coverage-report.json")
    reports = [discovery_report, claim_report]
    status_failed = any(report.get("status") == "fail" for report in reports)
    warnings = list(
        dict.fromkeys(
            _strings(manifest.get("warnings"))
            + _strings(discovery_report.get("warnings"))
            + _strings(claim_report.get("warnings"))
        )
    )
    requires_manual_review = any(bool(report.get("requires_manual_review")) for report in reports)
    run_status = "failed" if status_failed else "partial" if requires_manual_review else "complete"
    validation_status = "failed" if status_failed else "passed"
    completion_blockers = list(
        dict.fromkeys(
            _strings(discovery_report.get("completion_blockers"))
            + _strings(claim_report.get("completion_blockers"))
        )
    )
    reasons = []
    for report in reports:
        manual_review = report.get("manual_review") if isinstance(report.get("manual_review"), dict) else {}
        reasons.extend(reason for reason in manual_review.get("reasons", []) if isinstance(reason, dict))

    manifest.update(
        {
            "inputs": input_record,
            "artifacts": artifacts,
            "evidence": evidence,
            "warnings": warnings,
            "requires_manual_review": requires_manual_review,
            "run_status": run_status,
            "validation_status": validation_status,
            "manual_review": {
                "required": requires_manual_review,
                "severity": "blocking" if status_failed else "warning" if requires_manual_review else "info",
                "reasons": reasons,
            },
            "completion_blockers": completion_blockers,
            "validation": {
                **(manifest.get("validation") or {}),
                "schema_valid": not status_failed,
                "warnings": len(warnings),
                "requires_manual_review": requires_manual_review,
                "report_path": "validation/claim-coverage-report.json",
                "missing_sources_path": "validation/missing-sources.md",
                "discovery_report_path": "validation/discovery-validation-report.json",
            },
        }
    )
    write_json(manifest_path, manifest)


def _final_input_record(
    *,
    args: argparse.Namespace,
    spec: dict[str, Any],
    discovery_log: dict[str, Any],
    m8_input_path: Path | None,
) -> dict[str, Any]:
    return {
        "schema_version": str(spec.get("schema_version") or "1.0"),
        "research_question": spec.get("research_question") or spec.get("question"),
        "discovery_mode": discovery_log.get("discovery_mode"),
        "max_sources": discovery_log.get("max_sources"),
        "allowed_domains": discovery_log.get("allowed_domains") or [],
        "allowed_source_types": discovery_log.get("allowed_source_types") or [],
        "excluded_domains": discovery_log.get("excluded_domains") or [],
        "excluded_source_types": discovery_log.get("excluded_source_types") or [],
        "recency": discovery_log.get("recency"),
        "search_queries": discovery_log.get("search_queries") or [],
        "selection_rationale_required": bool(discovery_log.get("selection_rationale_required")),
        "input_path": str(args.input) if args.input else None,
        "generated_capture_input": "capture/discovery-selected-sources.json" if m8_input_path else None,
        "topic": spec.get("topic") or spec.get("research_question") or spec.get("question"),
        "question": spec.get("research_question") or spec.get("question"),
        "workflow": "browser-research",
        "capture_stage": "small_scope_discovery",
        "selected_source_count": len(discovery_log.get("selected_sources") or []),
        "candidate_count": len(discovery_log.get("candidates") or []),
        "selected_source_urls": [source.get("url") for source in discovery_log.get("selected_sources") or []],
    }


def run(args: argparse.Namespace) -> tuple[Path, bool]:
    started_at = utc_now()
    run_id = args.run_id or f"{_slug_timestamp(started_at)}-research-discovery"
    output_root = Path(args.output_root or "browser-operator-runs").resolve()
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    spec = _load_spec(args)
    input_record = {
        "input_path": str(args.input) if args.input else None,
        "workflow": "browser-research",
        "capture_stage": "small_scope_discovery",
        "question": spec.get("research_question") or spec.get("question"),
        "max_sources": spec.get("max_sources"),
    }
    try:
        discovery_log, discovery_errors = build_discovery_log(spec, started_at)
    except (TypeError, ValueError) as exc:
        report = _validation_report([f"discovery_input_invalid:{exc.__class__.__name__}"])
        _write_discovery_only_run(run_dir, run_id=run_id, started_at=started_at, input_record=input_record, report=report)
        print(run_dir)
        return run_dir, True

    selected_sources = _selected_capture_sources(discovery_log, spec)
    if discovery_errors or not selected_sources:
        report = _validation_report(discovery_errors or ["no_sources_selected"])
        _write_discovery_only_run(
            run_dir,
            run_id=run_id,
            started_at=started_at,
            input_record=_final_input_record(args=args, spec=spec, discovery_log=discovery_log, m8_input_path=None),
            report=report,
            discovery_log=discovery_log,
        )
        print(run_dir)
        return run_dir, True

    m8_input = {
        "schema_version": "1.0",
        "topic": spec.get("topic") or spec.get("research_question") or spec.get("question"),
        "question": spec.get("research_question") or spec.get("question"),
        "summary": spec.get("summary"),
        "sources": selected_sources,
        "claims": [claim for claim in _as_list(spec.get("claims")) if isinstance(claim, dict)],
        "unknowns": [unknown for unknown in _as_list(spec.get("unknowns")) if isinstance(unknown, dict)],
        "warnings": _strings(spec.get("warnings")),
    }
    m8_input_path = run_dir / "capture" / "discovery-selected-sources.json"
    write_json(m8_input_path, m8_input)

    command = [
        sys.executable,
        str(SCRIPT_ROOT / "research_capture_runner.py"),
        "--input",
        str(m8_input_path),
        "--output-root",
        str(output_root),
        "--run-id",
        run_id,
        "--min-sources",
        "1",
        "--max-sources",
        str(discovery_log.get("max_sources") or DEFAULT_MAX_SOURCES),
    ]
    completed = subprocess.run(command, cwd=Path(__file__).resolve().parents[1], text=True, capture_output=True)
    if completed.returncode != 0:
        report = _validation_report([completed.stderr.strip() or "research_capture_runner_failed"])
        _write_discovery_only_run(
            run_dir,
            run_id=run_id,
            started_at=started_at,
            input_record=_final_input_record(args=args, spec=spec, discovery_log=discovery_log, m8_input_path=m8_input_path),
            report=report,
            discovery_log=discovery_log,
        )
        print(run_dir)
        return run_dir, True

    _write_discovery_artifacts(run_dir, discovery_log)
    input_record = _final_input_record(args=args, spec=spec, discovery_log=discovery_log, m8_input_path=m8_input_path)
    discovery_report = validate_research_discovery_run(run_dir)
    write_json(run_dir / "validation" / "discovery-validation-report.json", discovery_report)
    _merge_manifest(run_dir, input_record=input_record, discovery_report=discovery_report)

    final_discovery_report = validate_research_discovery_run(run_dir)
    write_json(run_dir / "validation" / "discovery-validation-report.json", final_discovery_report)
    final_claim_report = validate_browser_research_run(run_dir)
    write_json(run_dir / "validation" / "claim-coverage-report.json", final_claim_report)
    _merge_manifest(run_dir, input_record=input_record, discovery_report=final_discovery_report, claim_report=final_claim_report)
    for selected in discovery_log.get("selected_sources") or []:
        if isinstance(selected, dict) and selected.get("source_id"):
            (run_dir / "evidence" / source_dir_name(str(selected["source_id"])) / "screenshots").mkdir(
                parents=True,
                exist_ok=True,
            )
    write_json(run_dir / "input.json", input_record)
    _write_warnings(
        run_dir / "validation" / "warnings.md",
        list(dict.fromkeys(_strings(final_discovery_report.get("warnings")) + _strings(final_claim_report.get("warnings")))),
    )
    print(run_dir)
    return run_dir, False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Discover a small bounded set of public browser-research sources, then run the M8 capture pipeline."
    )
    parser.add_argument("--input", help="M10A research discovery JSON spec.")
    parser.add_argument("--question", help="Research question.")
    parser.add_argument("--topic", help="Report topic.")
    parser.add_argument("--discovery-mode", choices=["candidate_list", "search_results"])
    parser.add_argument("--max-sources", type=int)
    parser.add_argument("--allowed-domain", action="append", default=[])
    parser.add_argument("--allowed-source-type", action="append", default=[])
    parser.add_argument("--excluded-domain", action="append", default=[])
    parser.add_argument("--excluded-source-type", action="append", default=[])
    parser.add_argument("--query", action="append", default=[])
    parser.add_argument("--candidate-url", action="append", default=[])
    parser.add_argument("--claims-file", help="Optional claim ledger JSON with claims/unknowns/summary.")
    parser.add_argument("--output-root", default="browser-operator-runs")
    parser.add_argument("--run-id")
    args = parser.parse_args()
    _, blocked = run(args)
    return 1 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
