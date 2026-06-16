from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _append_optional(command: list[str], flag: str, value: str | None) -> None:
    if value is not None:
        command.extend([flag, value])


def _append_repeated(command: list[str], flag: str, values: list[str]) -> None:
    for value in values:
        command.extend([flag, value])


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, text=True)


def run(args: argparse.Namespace) -> int:
    output_root = Path(args.output_root).resolve()
    run_id = args.run_id
    capture_command = [
        sys.executable,
        str(ROOT / "scripts" / "capture" / "current_chrome_capture.py"),
        "--url",
        args.url,
        "--page-title",
        args.page_title,
        "--output-root",
        str(output_root),
        "--run-id",
        run_id,
        "--login-state",
        args.login_state,
        "--page-type",
        args.page_type,
    ]
    if args.user_approved_current_page:
        capture_command.append("--user-approved-current-page")
    if args.requires_login:
        capture_command.append("--requires-login")
    if args.contains_private_data:
        capture_command.append("--contains-private-data")
    if args.redaction_applied:
        capture_command.append("--redaction-applied")
    if args.screenshot_privacy_reviewed:
        capture_command.append("--screenshot-privacy-reviewed")
    if args.screenshot_required:
        capture_command.append("--screenshot-required")
    _append_optional(capture_command, "--capture-id", args.capture_id)
    _append_optional(capture_command, "--canonical-url", args.canonical_url)
    _append_optional(capture_command, "--site-name", args.site_name)
    _append_optional(capture_command, "--html-file", args.html_file)
    _append_optional(capture_command, "--text-file", args.text_file)
    _append_optional(capture_command, "--selected-main-content-file", args.selected_main_content_file)
    _append_optional(capture_command, "--accessibility-snapshot-json", args.accessibility_snapshot_json)
    _append_optional(capture_command, "--accessibility-snapshot-file", args.accessibility_snapshot_file)
    _append_optional(capture_command, "--region-or-locale", args.region_or_locale)
    _append_optional(capture_command, "--screenshot-reason", args.screenshot_reason)
    _append_repeated(capture_command, "--redaction-note", args.redaction_note)
    _append_repeated(capture_command, "--screenshot", args.screenshot)
    _append_repeated(capture_command, "--warning", args.warning)
    _append_repeated(capture_command, "--action", args.action)

    capture_result = _run(capture_command)
    if capture_result.returncode != 0:
        return capture_result.returncode

    run_dir = output_root / run_id
    capture_path = run_dir / "capture" / "page_capture.json"
    capture_report_path = run_dir / "validation" / "capture-validation-report.json"

    capture_validation = _run(
        [
            sys.executable,
            str(ROOT / "scripts" / "validation" / "validate_page_capture.py"),
            str(capture_path),
            "--write-report",
            str(capture_report_path),
        ]
    )
    if capture_validation.returncode != 0:
        return capture_validation.returncode

    render_result = _run(
        [
            sys.executable,
            str(ROOT / "scripts" / "page_to_md_runner.py"),
            "--input",
            str(capture_path),
            "--output-root",
            str(output_root),
            "--run-id",
            run_id,
            "--page-type",
            args.page_type,
        ]
    )
    if render_result.returncode != 0:
        return render_result.returncode

    return _run(
        [
            sys.executable,
            str(ROOT / "scripts" / "validation" / "validate_page_to_md.py"),
            str(run_dir),
        ]
    ).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Run M7 current Chrome capture -> page-to-md -> validation.")
    parser.add_argument("--url", required=True)
    parser.add_argument("--user-approved-current-page", action="store_true")
    parser.add_argument("--output-root", default="browser-operator-runs")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--page-title", required=True)
    parser.add_argument("--page-type", default="auto", choices=["auto", "article", "blog", "docs", "x_thread", "forum_thread", "product_page", "unknown"])
    parser.add_argument("--capture-id")
    parser.add_argument("--canonical-url")
    parser.add_argument("--site-name")
    parser.add_argument("--html-file")
    parser.add_argument("--text-file")
    parser.add_argument("--selected-main-content-file")
    parser.add_argument("--accessibility-snapshot-json")
    parser.add_argument("--accessibility-snapshot-file")
    parser.add_argument("--login-state", default="unknown", choices=["not_required", "suspected", "confirmed", "unknown"])
    parser.add_argument("--requires-login", action="store_true")
    parser.add_argument("--contains-private-data", action="store_true")
    parser.add_argument("--redaction-applied", action="store_true")
    parser.add_argument("--redaction-note", action="append", default=[])
    parser.add_argument("--region-or-locale")
    parser.add_argument("--screenshot", action="append", default=[])
    parser.add_argument("--screenshot-privacy-reviewed", action="store_true")
    parser.add_argument("--screenshot-required", action="store_true")
    parser.add_argument("--screenshot-reason", default="current_visible_page")
    parser.add_argument("--warning", action="append", default=[])
    parser.add_argument("--action", action="append", default=[])
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
