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
        str(ROOT / "scripts" / "capture" / "playwright_mcp_capture.py"),
        "--url",
        args.url,
        "--output-root",
        str(output_root),
    ]
    _append_optional(capture_command, "--run-id", run_id)
    _append_optional(capture_command, "--capture-id", args.capture_id)
    _append_optional(capture_command, "--page-title", args.page_title)
    _append_optional(capture_command, "--canonical-url", args.canonical_url)
    _append_optional(capture_command, "--site-name", args.site_name)
    _append_optional(capture_command, "--html-file", args.html_file)
    _append_optional(capture_command, "--text-file", args.text_file)
    _append_optional(capture_command, "--selected-main-content-file", args.selected_main_content_file)
    _append_optional(capture_command, "--accessibility-snapshot-json", args.accessibility_snapshot_json)
    _append_optional(capture_command, "--accessibility-snapshot-file", args.accessibility_snapshot_file)
    _append_optional(capture_command, "--capture-method", args.capture_method)
    _append_repeated(capture_command, "--screenshot", args.screenshot)
    _append_repeated(capture_command, "--warning", args.warning)
    _append_repeated(capture_command, "--action", args.action)
    if args.screenshot_required:
        capture_command.append("--screenshot-required")
    _append_optional(capture_command, "--screenshot-reason", args.screenshot_reason)
    if args.requires_login:
        capture_command.append("--requires-login")

    capture_result = _run(capture_command)
    if capture_result.returncode != 0:
        return capture_result.returncode

    if not run_id:
        raise SystemExit("--run-id is required for the wrapper so later stages target the same run directory")
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
    parser = argparse.ArgumentParser(description="Run M6 capture -> page-to-md -> validation for one public URL.")
    parser.add_argument("--url", required=True)
    parser.add_argument("--output-root", default="browser-operator-runs")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--page-type", default="auto", choices=["auto", "article", "blog", "docs", "unknown"])
    parser.add_argument("--capture-id")
    parser.add_argument("--page-title")
    parser.add_argument("--canonical-url")
    parser.add_argument("--site-name")
    parser.add_argument("--html-file")
    parser.add_argument("--text-file")
    parser.add_argument("--selected-main-content-file")
    parser.add_argument("--accessibility-snapshot-json")
    parser.add_argument("--accessibility-snapshot-file")
    parser.add_argument("--capture-method", default="playwright_mcp_dom_snapshot")
    parser.add_argument("--screenshot", action="append", default=[])
    parser.add_argument("--screenshot-required", action="store_true")
    parser.add_argument("--screenshot-reason", default="static_public_article")
    parser.add_argument("--warning", action="append", default=[])
    parser.add_argument("--action", action="append", default=[])
    parser.add_argument("--requires-login", action="store_true")
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
