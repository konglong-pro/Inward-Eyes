from __future__ import annotations

import argparse
import secrets
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = ROOT / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from inward_eyes.capture import (  # noqa: E402
    finalize_page_workflow_failure,
    read_capture_admission_bundle,
    release_page_workflow_ownership,
)
from inward_eyes.paths import create_continuation_handoff, validate_run_id  # noqa: E402


def _append_optional(command: list[str], flag: str, value: str | None) -> None:
    if value is not None:
        command.extend([flag, value])


def _append_repeated(command: list[str], flag: str, values: list[str]) -> None:
    for value in values:
        command.extend([flag, value])


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, text=True)


def _run_claimed(
    args: argparse.Namespace,
    *,
    output_root: Path,
    run_id: str,
    run_dir: Path,
    ownership_token: str,
) -> int:
    capture_command = [
        sys.executable,
        str(ROOT / "scripts" / "capture" / "playwright_mcp_capture.py"),
        "--url",
        args.url,
        "--output-root",
        str(output_root),
    ]
    _append_optional(capture_command, "--run-id", run_id)
    capture_command.append(f"--wrapper-ownership-token={ownership_token}")
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
        finalize_page_workflow_failure(
            output_root / run_id,
            run_id=run_id,
            failure_code=f"capture_process_failed:{capture_result.returncode}",
            ownership_token=ownership_token,
        )
        return capture_result.returncode

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
        finalize_page_workflow_failure(
            run_dir,
            run_id=run_id,
            failure_code=f"capture_validation_failed:{capture_validation.returncode}",
            ownership_token=ownership_token,
        )
        return capture_validation.returncode

    _, _, _, artifact_sha256, admission_errors = read_capture_admission_bundle(
        run_dir,
        expected_run_id=run_id,
        returncode=capture_result.returncode,
    )
    if admission_errors:
        for error in admission_errors:
            print(f"capture admission failed: {error}", file=sys.stderr)
        finalize_page_workflow_failure(
            run_dir,
            run_id=run_id,
            failure_code="capture_admission_failed",
            ownership_token=ownership_token,
        )
        return 1

    continuation_token = create_continuation_handoff(
        run_dir,
        run_id=run_id,
        from_stage="playwright-capture",
        to_stage="page-to-md-render",
        input_path="capture/page_capture.json",
        artifact_sha256=artifact_sha256,
    )

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
            "--continue-existing-run",
            f"--continuation-token={continuation_token}",
            "--page-type",
            args.page_type,
        ]
    )
    if render_result.returncode != 0:
        finalize_page_workflow_failure(
            run_dir,
            run_id=run_id,
            failure_code=f"page_render_failed:{render_result.returncode}",
            ownership_token=ownership_token,
        )
        return render_result.returncode

    return _run(
        [
            sys.executable,
            str(ROOT / "scripts" / "validation" / "validate_page_to_md.py"),
            str(run_dir),
        ]
    ).returncode


def run(args: argparse.Namespace) -> int:
    output_root = Path(args.output_root).resolve()
    run_id = validate_run_id(args.run_id)
    run_dir = output_root / run_id
    if run_dir.exists() or run_dir.is_symlink():
        print(f"run directory already exists; choose a new run_id: {run_dir}", file=sys.stderr)
        return 1
    ownership_token = secrets.token_urlsafe(32)
    try:
        return _run_claimed(
            args,
            output_root=output_root,
            run_id=run_id,
            run_dir=run_dir,
            ownership_token=ownership_token,
        )
    finally:
        release_page_workflow_ownership(
            run_dir,
            run_id=run_id,
            ownership_token=ownership_token,
        )


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
