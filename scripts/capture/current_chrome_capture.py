from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from inward_eyes.capture import (  # noqa: E402
    build_page_capture,
    claim_page_workflow_ownership,
    screenshot_file_is_valid,
    validate_page_capture_contract,
    write_capture_stage_manifest,
    write_capture_warnings,
)
from inward_eyes.io import utc_now, write_bytes, write_json  # noqa: E402
from inward_eyes.paths import prepare_run_dir  # noqa: E402
from inward_eyes.safety import classify_action  # noqa: E402

SCREENSHOT_REQUIRED_PAGE_TYPES = {"x_thread", "forum_thread", "product_page"}
SCREENSHOT_REQUIRED_WARNINGS = {
    "dynamic_page",
    "ambiguous_extraction",
    "personal_context",
    "thread_page",
    "forum_thread",
    "ecommerce_page",
}


def _slug_timestamp(timestamp: str) -> str:
    return re.sub(r"[^0-9TZ]", "", timestamp).replace("Z", "Z")


def _safe_asset_name(raw_name: str, index: int) -> str:
    suffix = Path(raw_name).suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        suffix = ".png"
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(raw_name).stem).strip(".-") or f"screenshot-{index:03d}"
    return f"{index:03d}-{stem}{suffix}"


def _read_optional_text(path: str | None) -> str | None:
    if not path:
        return None
    return Path(path).read_text(encoding="utf-8")


def _read_optional_json(path: str | None) -> Any:
    if not path:
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _read_optional_json_or_text(json_path: str | None, text_path: str | None) -> Any:
    if json_path:
        return _read_optional_json(json_path)
    return _read_optional_text(text_path)


def _has_observation_payload(
    html: str | None,
    text: str | None,
    selected_main_content: str | None,
    accessibility_snapshot: Any,
) -> bool:
    return any(
        value is not None and (not isinstance(value, str) or bool(value.strip()))
        for value in (html, text, selected_main_content, accessibility_snapshot)
    )


def _failure_report(reason: str, screenshot_required: bool = False) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "status": "fail",
        "errors": [reason],
        "warnings": [reason],
        "requires_manual_review": True,
        "screenshot_policy": {
            "required": screenshot_required,
            "reason": "current_chrome_capture_failed",
            "status": "capture_failed",
        },
        "run_status": "failed",
        "validation_status": "failed",
        "manual_review": {
            "required": True,
            "severity": "blocking",
            "reasons": [
                {
                    "code": reason,
                    "message": reason.replace("_", " "),
                    "severity": "blocking",
                    "artifact": "capture/page_capture.json",
                }
            ],
        },
        "completion_blockers": [reason],
    }


def _write_failure_run(
    run_dir: Path,
    *,
    run_id: str,
    started_at: str,
    input_record: dict[str, Any],
    report: dict[str, Any],
    aborted_by_policy: bool = False,
) -> None:
    write_json(run_dir / "input.json", input_record)
    write_json(run_dir / "validation" / "capture-validation-report.json", report)
    write_capture_warnings(run_dir / "validation" / "warnings.md", report.get("warnings", []))
    write_capture_stage_manifest(
        run_dir,
        run_id=run_id,
        started_at=started_at,
        finished_at=utc_now(),
        input_record=input_record,
        report=report,
        capture_written=False,
        aborted_by_policy=aborted_by_policy,
    )


def _screenshot_required(args: argparse.Namespace, warnings: list[str]) -> tuple[bool, str]:
    reasons: list[str] = []
    if args.requires_login or args.login_state in {"confirmed", "suspected"}:
        reasons.append("logged_in_page")
    if args.contains_private_data:
        reasons.append("private_data")
    if args.page_type in SCREENSHOT_REQUIRED_PAGE_TYPES:
        reasons.append(args.page_type)
    for warning in sorted(set(warnings).intersection(SCREENSHOT_REQUIRED_WARNINGS)):
        reasons.append(warning)
    if args.screenshot_required:
        reasons.append(args.screenshot_reason or "current_page_policy")
    reasons = list(dict.fromkeys(reasons))
    return bool(reasons), "+".join(reasons) if reasons else args.screenshot_reason


def _copy_reviewed_screenshots(args: argparse.Namespace, run_dir: Path) -> tuple[list[str], list[str]]:
    if args.screenshot and not args.screenshot_privacy_reviewed:
        return [], ["screenshot_privacy_review_required"]

    copied: list[str] = []
    warnings: list[str] = []
    for index, raw_path in enumerate(args.screenshot, start=1):
        source = Path(raw_path).resolve()
        if not screenshot_file_is_valid(source):
            warnings.append(f"screenshot_asset_missing:{raw_path}")
            continue
        destination = run_dir / "capture" / "screenshots" / _safe_asset_name(raw_path, index)
        destination.parent.mkdir(parents=True, exist_ok=True)
        write_bytes(destination, source.read_bytes())
        if not screenshot_file_is_valid(destination):
            destination.unlink(missing_ok=True)
            warnings.append(f"screenshot_asset_copy_invalid:{raw_path}")
            continue
        copied.append(f"screenshots/{destination.name}")
    return copied, warnings


def run(args: argparse.Namespace) -> Path:
    started_at = utc_now()
    run_id = args.run_id or f"{_slug_timestamp(started_at)}-current-chrome-capture"
    html = args.html if args.html is not None else _read_optional_text(args.html_file)
    text = args.text if args.text is not None else _read_optional_text(args.text_file)
    selected_main_content = (
        args.selected_main_content
        if args.selected_main_content is not None
        else _read_optional_text(args.selected_main_content_file)
    )
    accessibility_snapshot = _read_optional_json_or_text(
        args.accessibility_snapshot_json,
        args.accessibility_snapshot_file,
    )
    for raw_path in args.screenshot:
        screenshot_file_is_valid(Path(raw_path).resolve())
    run_dir = prepare_run_dir(args.output_root or "browser-operator-runs", run_id)
    claim_page_workflow_ownership(
        run_dir,
        run_id=run_id,
        ownership_token=getattr(args, "wrapper_ownership_token", None),
    )

    input_record: dict[str, Any] = {
        "visible_url": args.url,
        "backend": "current_chrome",
        "workflow": "page-to-md",
        "capture_stage": "browser_adapter",
        "scope": "current_visible_page",
        "user_approved_current_page": bool(args.user_approved_current_page),
        "requires_login": bool(args.requires_login),
        "login_state": args.login_state,
        "actions": ["capture_current_visible_page", "read_visible_text", "save_artifacts", *args.action],
    }

    if not args.user_approved_current_page:
        report = _failure_report("current_page_approval_required")
        _write_failure_run(
            run_dir,
            run_id=run_id,
            started_at=started_at,
            input_record=input_record,
            report=report,
            aborted_by_policy=True,
        )
        print(run_dir)
        return run_dir

    for action in input_record["actions"]:
        decision = classify_action(str(action))
        if not decision.allowed:
            report = _failure_report(f"policy_blocked:{decision.classification}:{decision.action}")
            _write_failure_run(
                run_dir,
                run_id=run_id,
                started_at=started_at,
                input_record={**input_record, "policy_decision": decision.__dict__},
                report=report,
                aborted_by_policy=True,
            )
            print(run_dir)
            return run_dir

    if not _has_observation_payload(html, text, selected_main_content, accessibility_snapshot):
        report = _failure_report("content.payload_missing")
        _write_failure_run(run_dir, run_id=run_id, started_at=started_at, input_record=input_record, report=report)
        print(run_dir)
        return run_dir

    warnings = list(dict.fromkeys(args.warning))
    screenshot_required, screenshot_reason = _screenshot_required(args, warnings)
    screenshot_paths, screenshot_warnings = _copy_reviewed_screenshots(args, run_dir)
    warnings = list(dict.fromkeys(warnings + screenshot_warnings))

    capture = build_page_capture(
        url=args.url,
        page_title=args.page_title,
        html=html,
        text=text,
        accessibility_snapshot=accessibility_snapshot,
        selected_main_content=selected_main_content,
        canonical_url=args.canonical_url,
        site_name=args.site_name,
        capture_id=args.capture_id,
        capture_method="current_chrome_visible_page",
        browser_tool="current_chrome",
        login_state=args.login_state,
        requires_login=bool(args.requires_login or args.login_state in {"confirmed", "suspected"}),
        source_page_type=None if args.page_type == "auto" else args.page_type,
        user_visible_profile=True,
        current_page_approved=True,
        capture_scope="current_visible_page",
        region_or_locale=args.region_or_locale,
        viewport={"width": args.viewport_width, "height": args.viewport_height},
        screenshot_paths=screenshot_paths,
        screenshot_required=screenshot_required,
        screenshot_reason=screenshot_reason,
        screenshot_privacy_reviewed=args.screenshot_privacy_reviewed,
        contains_private_data=args.contains_private_data,
        redaction_applied=args.redaction_applied,
        redaction_notes=args.redaction_note,
        warnings=warnings,
    )
    report = validate_page_capture_contract(capture)

    write_json(run_dir / "input.json", input_record)
    write_json(run_dir / "capture" / "page_capture.json", capture)
    write_json(run_dir / "validation" / "capture-validation-report.json", report)
    write_capture_warnings(run_dir / "validation" / "warnings.md", report.get("warnings", []))
    write_capture_stage_manifest(
        run_dir,
        run_id=run_id,
        started_at=started_at,
        finished_at=utc_now(),
        input_record=input_record,
        report=report,
        capture_written=True,
    )
    print(run_dir)
    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Write page_capture.json from one user-approved currently visible Chrome page observation. "
            "This interface does not export profiles, cookies, tokens, storage, HAR, or unrelated tabs."
        )
    )
    parser.add_argument("--url", required=True, help="Visible URL of the approved current Chrome page.")
    parser.add_argument("--user-approved-current-page", action="store_true", help="Required approval boundary.")
    parser.add_argument("--output-root", default="browser-operator-runs")
    parser.add_argument("--run-id")
    parser.add_argument("--wrapper-ownership-token", help=argparse.SUPPRESS)
    parser.add_argument("--capture-id")
    parser.add_argument("--page-title", required=True)
    parser.add_argument("--canonical-url")
    parser.add_argument("--site-name")
    parser.add_argument("--html")
    parser.add_argument("--html-file")
    parser.add_argument("--text")
    parser.add_argument("--text-file")
    parser.add_argument("--selected-main-content")
    parser.add_argument("--selected-main-content-file")
    parser.add_argument("--accessibility-snapshot-json")
    parser.add_argument("--accessibility-snapshot-file")
    parser.add_argument("--login-state", default="unknown", choices=["not_required", "suspected", "confirmed", "unknown"])
    parser.add_argument("--requires-login", action="store_true")
    parser.add_argument("--contains-private-data", action="store_true")
    parser.add_argument("--redaction-applied", action="store_true")
    parser.add_argument("--redaction-note", action="append", default=[])
    parser.add_argument("--region-or-locale")
    parser.add_argument("--viewport-width", type=int, default=1440)
    parser.add_argument("--viewport-height", type=int, default=1200)
    parser.add_argument("--page-type", default="auto", choices=["auto", "article", "blog", "docs", "x_thread", "forum_thread", "product_page", "unknown"])
    parser.add_argument("--screenshot", action="append", default=[], help="Reviewed/redacted screenshot source path.")
    parser.add_argument("--screenshot-privacy-reviewed", action="store_true")
    parser.add_argument("--screenshot-required", action="store_true")
    parser.add_argument("--screenshot-reason", default="current_visible_page")
    parser.add_argument("--warning", action="append", default=[])
    parser.add_argument("--action", action="append", default=[], help="Additional browser action to classify.")
    args = parser.parse_args()
    run_dir = run(args)
    report_path = run_dir / "validation" / "capture-validation-report.json"
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        return 0 if report.get("status") == "pass" else 1
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    return 0 if manifest.get("run_status") == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
