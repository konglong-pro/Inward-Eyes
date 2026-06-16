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
from inward_eyes.run_index import write_run_index


TASK_RUNNERS = {
    "page-to-md": "scripts/page_to_md_runner.py",
    "browser-research": "scripts/browser_research_runner.py",
    "price-compare": "scripts/price_compare_runner.py",
    "adapter-matrix": "scripts/adapter_matrix_runner.py",
    "site-profiles": "scripts/site_profile_runner.py",
}


def _slug_timestamp(timestamp: str) -> str:
    return re.sub(r"[^0-9TZ]", "", timestamp)


def _job_command(root: Path, batch_output_root: Path, job: dict[str, Any], attempt: int) -> list[str]:
    task = str(job.get("task") or "")
    if task not in TASK_RUNNERS:
        raise ValueError(f"unsupported task: {task}")
    run_id = str(job.get("run_id") or f"{job.get('job_id', task)}-attempt-{attempt}")
    command = [sys.executable, str(root / TASK_RUNNERS[task]), "--output-root", str(batch_output_root), "--run-id", run_id]
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


def _load_child_manifest(batch_output_root: Path, job: dict[str, Any], attempt: int) -> dict[str, Any] | None:
    run_id = str(job.get("run_id") or f"{job.get('job_id', job.get('task'))}-attempt-{attempt}")
    manifest_path = batch_output_root / run_id / "manifest.json"
    if not manifest_path.exists():
        return None
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def run_batch(args: argparse.Namespace) -> Path:
    root = Path(__file__).resolve().parents[1]
    spec_path = Path(args.spec).resolve()
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    jobs = spec.get("jobs") if isinstance(spec.get("jobs"), list) else []
    started_at = utc_now()
    run_id = args.run_id or f"{_slug_timestamp(started_at)}-batch"
    output_root = Path(args.output_root or "browser-operator-runs").resolve()
    run_dir = output_root / run_id
    batch_runs_root = run_dir / "runs"
    max_retries = int(spec.get("max_retries", 0))
    results: list[dict[str, Any]] = []

    for job in jobs:
        if not isinstance(job, dict):
            continue
        attempts = 0
        final_returncode = 1
        final_stdout = ""
        final_stderr = ""
        while attempts <= max_retries:
            attempts += 1
            command = _job_command(root, batch_runs_root, job, attempts)
            completed = subprocess.run(command, cwd=root, text=True, capture_output=True)
            final_returncode = completed.returncode
            stdout_lines = [line for line in completed.stdout.splitlines() if line.strip()]
            final_stdout = stdout_lines[-1] if stdout_lines else ""
            final_stderr = "present" if completed.stderr.strip() else ""
            child_manifest = _load_child_manifest(batch_runs_root, job, attempts)
            child_status = child_manifest.get("run_status") if child_manifest else None
            if final_returncode == 0 and child_status in {None, "complete"}:
                break
            if child_status == "aborted_by_policy":
                break
            if child_status == "partial" and child_manifest and child_manifest.get("requires_manual_review"):
                break
        child_manifest = _load_child_manifest(batch_runs_root, job, attempts)
        semantic_status = child_manifest.get("run_status") if child_manifest else None
        job_failed = final_returncode != 0 or semantic_status in {"failed", "aborted_by_policy"}
        results.append(
            {
                "job_id": job.get("job_id"),
                "task": job.get("task"),
                "attempts": attempts,
                "returncode": final_returncode,
                "reported_run_dir": final_stdout,
                "stderr_present": bool(final_stderr),
                "child_run_status": semantic_status,
                "status": "failed" if job_failed else "partial" if semantic_status == "partial" else "complete",
            }
        )

    errors = [f"BATCH_JOB_FAILED:{item.get('job_id')}" for item in results if item["status"] == "failed"]
    report = {
        "schema_version": "1.0",
        "status": "fail" if errors else "pass",
        "errors": errors,
        "warnings": [],
        "requires_manual_review": bool(errors),
        "run_status": "failed" if errors else "complete",
        "validation_status": "failed" if errors else "passed",
        "manual_review": {
            "required": bool(errors),
            "severity": "blocking" if errors else "info",
            "reasons": [
                {
                    "code": error,
                    "message": error.replace("_", " ").replace(":", ": "),
                    "severity": "blocking",
                    "artifact": "artifacts/batch-results.json",
                }
                for error in errors
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
                "schema_valid": report["status"] == "pass",
                "warnings": 0,
                "requires_manual_review": bool(report["requires_manual_review"]),
                "report_path": "validation/batch-validation-report.json",
            },
            "warnings": [],
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
    run_dir = run_batch(args)
    report = (run_dir / "validation" / "batch-validation-report.json").read_text(encoding="utf-8")
    return 0 if '"status": "pass"' in report else 1


if __name__ == "__main__":
    raise SystemExit(main())
