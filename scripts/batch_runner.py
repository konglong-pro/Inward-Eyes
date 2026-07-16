from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from inward_eyes.io import utc_now, write_json
from inward_eyes.paths import prepare_run_dir, resolve_run_relative, validate_run_id
from inward_eyes.run_index import canonical_manifest_shape_error, classify_retryability, write_run_index
from inward_eyes.validation import validate_manifest_paths, validate_manifest_status


TASK_RUNNERS = {
    "page-to-md": "scripts/page_to_md_runner.py",
    "browser-research": "scripts/browser_research_runner.py",
    "price-compare": "scripts/price_compare_runner.py",
    "adapter-matrix": "scripts/adapter_matrix_runner.py",
    "site-profiles": "scripts/site_profile_runner.py",
}
def _slug_timestamp(timestamp: str) -> str:
    return re.sub(r"[^0-9TZ]", "", timestamp)


def _attempt_run_id(job: dict[str, Any], job_index: int, attempt: int) -> str:
    base = validate_run_id(str(job.get("run_id") or job.get("job_id") or job.get("task") or "job"))
    suffix = f"-job-{job_index:03d}-attempt-{attempt:03d}"
    return validate_run_id(f"{base[: 128 - len(suffix)]}{suffix}")


def _job_command(
    root: Path,
    batch_output_root: Path,
    job: dict[str, Any],
    attempt_run_id: str,
) -> list[str]:
    task = str(job.get("task") or "")
    if task not in TASK_RUNNERS:
        raise ValueError(f"unsupported task: {task}")
    runner_path = Path(TASK_RUNNERS[task])
    if not runner_path.is_absolute():
        runner_path = root / runner_path
    command = [sys.executable, str(runner_path), "--output-root", str(batch_output_root), "--run-id", attempt_run_id]
    if task in {"page-to-md", "browser-research", "price-compare"}:
        command.extend(["--input", str(Path(str(job["input"])).resolve())])
    if task == "page-to-md" and job.get("url"):
        command.extend(["--url", str(job["url"])])
    if task == "page-to-md" and job.get("page_type"):
        command.extend(["--page-type", str(job["page_type"])])
    if task == "site-profiles" and job.get("url"):
        command.extend(["--url", str(job["url"])])
        command.extend(["--page-type", str(job.get("page_type", "unknown"))])
    return command


def _child_manifest_error(manifest: dict[str, Any], attempt_run_id: str, expected_task: str) -> str | None:
    shape_error = canonical_manifest_shape_error(
        manifest,
        expected_run_id=attempt_run_id,
        expected_task=expected_task,
    )
    if shape_error == "run_id_mismatch":
        return "BATCH_CHILD_MANIFEST_RUN_ID_MISMATCH"
    if shape_error == "task_mismatch":
        return "BATCH_CHILD_MANIFEST_TASK_MISMATCH"
    if shape_error:
        category, _, field = shape_error.partition(":")
        if category == "required_field_missing":
            return f"BATCH_CHILD_MANIFEST_REQUIRED_FIELD_MISSING:{field}"
        return f"BATCH_CHILD_MANIFEST_FIELD_INVALID:{field or category}"
    errors = validate_manifest_status(manifest)
    if errors:
        return f"BATCH_CHILD_MANIFEST_STATUS_INCONSISTENT:{errors[0]}"
    return None


def _load_child_manifest(
    batch_output_root: Path,
    attempt_run_id: str,
    expected_task: str,
) -> tuple[dict[str, Any] | None, str | None]:
    child_run_dir = batch_output_root.resolve() / attempt_run_id
    if child_run_dir.is_symlink():
        return None, "BATCH_CHILD_RUN_DIR_SYMLINK"
    manifest_path = child_run_dir / "manifest.json"
    if manifest_path.is_symlink():
        return None, "BATCH_CHILD_MANIFEST_SYMLINK"
    if not manifest_path.exists():
        return None, "BATCH_CHILD_MANIFEST_MISSING"
    if not manifest_path.is_file():
        return None, "BATCH_CHILD_MANIFEST_NOT_FILE"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None, "BATCH_CHILD_MANIFEST_INVALID_JSON"
    if not isinstance(manifest, dict):
        return None, "BATCH_CHILD_MANIFEST_INVALID_SHAPE"
    error = _child_manifest_error(manifest, attempt_run_id, expected_task)
    if not error:
        path_errors = validate_manifest_paths(child_run_dir, manifest)
        if path_errors:
            error = f"BATCH_CHILD_MANIFEST_PATH_INCONSISTENT:{path_errors[0]}"
    return (None, error) if error else (manifest, None)


def run_batch(args: argparse.Namespace) -> Path:
    root = Path(__file__).resolve().parents[1]
    spec_path = Path(args.spec).resolve()
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    if not isinstance(spec, dict):
        raise ValueError("batch spec must be a JSON object")
    raw_jobs = spec.get("jobs", [])
    if not isinstance(raw_jobs, list):
        raise ValueError("batch spec jobs must be an array")
    jobs = raw_jobs
    raw_max_retries = spec.get("max_retries", 0)
    if isinstance(raw_max_retries, bool) or not isinstance(raw_max_retries, int):
        raise ValueError("batch spec max_retries must be an integer")
    max_retries = max(0, raw_max_retries)
    started_at = utc_now()
    run_id = args.run_id or f"{_slug_timestamp(started_at)}-batch"
    output_root = Path(args.output_root or "browser-operator-runs").resolve()
    run_dir = prepare_run_dir(output_root, run_id)
    batch_runs_root = run_dir / "runs"
    batch_runs_root.mkdir()
    results: list[dict[str, Any]] = []

    for job_index, job in enumerate(jobs, start=1):
        if not isinstance(job, dict):
            results.append(
                {
                    "job_id": None,
                    "task": None,
                    "attempts": 0,
                    "attempt_runs": [],
                    "returncode": 1,
                    "reported_run_dir": "",
                    "stderr_present": False,
                    "child_run_status": None,
                    "status": "failed",
                    "failure_code": "BATCH_JOB_INVALID_SHAPE",
                    "warnings": [],
                }
            )
            continue
        attempts = 0
        final_returncode = 1
        final_stdout = ""
        final_stderr = ""
        final_manifest: dict[str, Any] | None = None
        final_manifest_error: str | None = None
        attempt_runs: list[dict[str, Any]] = []
        while attempts <= max_retries:
            attempts += 1
            try:
                attempt_run_id = _attempt_run_id(job, job_index, attempts)
                attempt_dir = resolve_run_relative(batch_runs_root, attempt_run_id)
                if attempt_dir.exists():
                    final_manifest_error = "BATCH_CHILD_RUN_DIR_EXISTS"
                    attempt_runs.append(
                        {
                            "run_id": attempt_run_id,
                            "returncode": 1,
                            "child_run_status": None,
                            "manifest_error": final_manifest_error,
                            "retryable": False,
                            "retry_classification": "existing_attempt_directory",
                        }
                    )
                    break
                command = _job_command(root, batch_runs_root, job, attempt_run_id)
            except (KeyError, TypeError, ValueError) as exc:
                final_manifest_error = "BATCH_JOB_CONFIGURATION_INVALID"
                attempt_runs.append(
                    {
                        "run_id": None,
                        "returncode": 1,
                        "child_run_status": None,
                        "manifest_error": final_manifest_error,
                        "retryable": False,
                        "retry_classification": type(exc).__name__,
                    }
                )
                break
            try:
                completed = subprocess.run(command, cwd=root, text=True, capture_output=True)
            except OSError:
                final_manifest_error = "BATCH_CHILD_PROCESS_START_FAILED"
                attempt_runs.append(
                    {
                        "run_id": attempt_run_id,
                        "returncode": 1,
                        "child_run_status": None,
                        "manifest_error": final_manifest_error,
                        "retryable": False,
                        "retry_classification": "process_start_failed",
                    }
                )
                break
            final_returncode = completed.returncode
            stdout_lines = [line for line in completed.stdout.splitlines() if line.strip()]
            final_stdout = stdout_lines[-1] if stdout_lines else ""
            final_stderr = "present" if completed.stderr.strip() else ""
            child_manifest, manifest_error = _load_child_manifest(batch_runs_root, attempt_run_id, str(job.get("task") or ""))
            final_manifest = child_manifest
            final_manifest_error = manifest_error
            child_status = child_manifest.get("run_status") if child_manifest else None
            retryable = False
            retry_classification = "invalid_or_missing_manifest"
            if child_manifest:
                retryable, retry_classification = classify_retryability(child_manifest)
            attempt_runs.append(
                {
                    "run_id": attempt_run_id,
                    "returncode": final_returncode,
                    "child_run_status": child_status,
                    "manifest_error": manifest_error,
                    "retryable": retryable,
                    "retry_classification": retry_classification,
                }
            )
            if manifest_error or child_status in {"complete", "aborted_by_policy"} or not retryable:
                break
            if attempts > max_retries:
                break
        semantic_status = final_manifest.get("run_status") if final_manifest else None
        if final_manifest_error:
            job_status = "failed"
            failure_code = final_manifest_error
        elif semantic_status == "complete":
            job_status = "complete"
            failure_code = None
        elif semantic_status == "partial":
            job_status = "partial"
            failure_code = None
        else:
            job_status = "failed"
            failure_code = "BATCH_JOB_ABORTED_BY_POLICY" if semantic_status == "aborted_by_policy" else "BATCH_JOB_FAILED"
        job_warnings: list[str] = []
        if semantic_status == "complete" and final_returncode != 0:
            job_warnings.append("BATCH_CHILD_PROCESS_NONZERO_COMPLETE")
        results.append(
            {
                "job_id": job.get("job_id"),
                "task": job.get("task"),
                "attempts": attempts,
                "attempt_runs": attempt_runs,
                "returncode": final_returncode,
                "reported_run_dir": final_stdout,
                "stderr_present": bool(final_stderr),
                "child_run_status": semantic_status,
                "status": job_status,
                "failure_code": failure_code,
                "warnings": job_warnings,
            }
        )

    if not results:
        results.append(
            {
                "job_id": None,
                "task": None,
                "attempts": 0,
                "attempt_runs": [],
                "returncode": 1,
                "reported_run_dir": "",
                "stderr_present": False,
                "child_run_status": None,
                "status": "failed",
                "failure_code": "BATCH_NO_JOBS",
                "warnings": [],
            }
        )
    errors = [
        f"{item.get('failure_code') or 'BATCH_JOB_FAILED'}:{item.get('job_id') or 'unknown'}"
        for item in results
        if item["status"] == "failed"
    ]
    warnings = [
        f"BATCH_JOB_PARTIAL:{item.get('job_id') or 'unknown'}"
        for item in results
        if item["status"] == "partial"
    ]
    warnings.extend(
        f"{warning}:{item.get('job_id') or 'unknown'}"
        for item in results
        for warning in item.get("warnings", [])
    )
    review_required = bool(errors or warnings)
    report_status = "fail" if errors else "pass"
    report = {
        "schema_version": "1.0",
        "status": report_status,
        "errors": errors,
        "warnings": warnings,
        "requires_manual_review": review_required,
        "run_status": "failed" if errors else "partial" if warnings else "complete",
        "validation_status": "failed" if errors else "passed",
        "manual_review": {
            "required": review_required,
            "severity": "blocking" if errors else "warning" if warnings else "info",
            "reasons": [
                {
                    "code": code,
                    "message": code.replace("_", " ").replace(":", ": "),
                    "severity": "blocking" if code in errors else "warning",
                    "artifact": "artifacts/batch-results.json",
                }
                for code in errors + warnings
            ],
        },
        "completion_blockers": errors,
    }
    write_json(run_dir / "input.json", {"spec": str(spec_path)})
    write_json(run_dir / "artifacts" / "batch-results.json", {"schema_version": "1.0", "jobs": results})
    write_json(run_dir / "validation" / "batch-validation-report.json", report)
    write_run_index(batch_runs_root, run_dir / "artifacts" / "run-index.jsonl")
    write_json(
        run_dir / "manifest.json",
        {
            "run_id": run_id,
            "task": "batch",
            "started_at": started_at,
            "finished_at": utc_now(),
            "operator": "codex",
            "skill": "internal",
            "inputs": {"spec": str(spec_path)},
            "artifacts": [
                {"id": "A001", "type": "batch_results", "path": "artifacts/batch-results.json"},
                {"id": "A002", "type": "run_index", "path": "artifacts/run-index.jsonl"},
            ],
            "evidence": [{"id": "V001", "type": "validation_report", "path": "validation/batch-validation-report.json"}],
            "validation": {
                "schema_valid": not errors,
                "warnings": len(warnings),
                "requires_manual_review": bool(report["requires_manual_review"]),
                "report_path": "validation/batch-validation-report.json",
            },
            "warnings": warnings,
            "requires_manual_review": bool(report["requires_manual_review"]),
            "run_status": report["run_status"],
            "validation_status": report["validation_status"],
            "manual_review": report["manual_review"],
            "completion_blockers": report["completion_blockers"],
            "screenshot_policy": {"required": False, "reason": "batch_orchestration", "status": "not_required"},
        },
    )
    print(run_dir)
    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a deterministic local batch of supported Inward Eyes tasks.")
    parser.add_argument("--spec", required=True)
    parser.add_argument("--output-root", default="browser-operator-runs")
    parser.add_argument("--run-id")
    args = parser.parse_args()
    try:
        run_dir = run_batch(args)
    except (FileExistsError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"batch failed: {exc}") from exc
    report = json.loads((run_dir / "validation" / "batch-validation-report.json").read_text(encoding="utf-8"))
    return 1 if report.get("status") == "fail" else 2 if report.get("run_status") == "partial" else 0


if __name__ == "__main__":
    raise SystemExit(main())
