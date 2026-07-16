from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

import batch_runner
from inward_eyes.run_index import build_retry_plan

OUTPUT_ROOT = ROOT / "evals" / ".tmp" / "batch-retry"
FIXTURE_ROOT = ROOT / "evals" / "fixtures" / "page-to-md"


def _run_real_batch(errors: list[str]) -> None:
    real_root = OUTPUT_ROOT / "real"
    real_root.mkdir(parents=True, exist_ok=True)
    spec_path = real_root / "batch-spec.json"
    spec_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "max_retries": 1,
                "jobs": [
                    {
                        "job_id": "article",
                        "task": "page-to-md",
                        "input": str(FIXTURE_ROOT / "public-article.html"),
                        "url": "https://example.test/public-article",
                        "page_type": "article",
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    command = [
        sys.executable,
        str(ROOT / "scripts" / "batch_runner.py"),
        "--spec",
        str(spec_path),
        "--output-root",
        str(real_root),
        "--run-id",
        "eval-batch",
    ]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    if completed.returncode != 0:
        errors.append(f"batch runner failed: {completed.stderr.strip()} {completed.stdout.strip()}".strip())
        return
    batch_dir = real_root / "eval-batch"
    results_path = batch_dir / "artifacts" / "batch-results.json"
    results = json.loads(results_path.read_text(encoding="utf-8"))["jobs"]
    expected_attempt_id = "article-job-001-attempt-001"
    if results[0].get("attempts") != 1 or results[0].get("attempt_runs", [{}])[0].get("run_id") != expected_attempt_id:
        errors.append("real batch did not record its unique attempt run_id")
    if not (batch_dir / "runs" / expected_attempt_id / "manifest.json").exists():
        errors.append("real batch child manifest missing from unique attempt directory")
    original_manifest = (batch_dir / "manifest.json").read_bytes()
    repeated = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    if repeated.returncode == 0:
        errors.append("reusing an existing batch run_id should fail")
    if (batch_dir / "manifest.json").read_bytes() != original_manifest:
        errors.append("reusing an existing batch run_id overwrote the original manifest")

    valid_child = batch_dir / "runs" / expected_attempt_id
    semantic_corrupt_dir = real_root / "semantic-corrupt-run"
    shutil.copytree(valid_child, semantic_corrupt_dir)
    semantic_manifest_path = semantic_corrupt_dir / "manifest.json"
    semantic_manifest = json.loads(semantic_manifest_path.read_text(encoding="utf-8"))
    semantic_manifest["run_id"] = semantic_corrupt_dir.name
    semantic_manifest["validation_status"] = "failed"
    semantic_manifest_path.write_text(json.dumps(semantic_manifest), encoding="utf-8")

    type_corrupt_dir = real_root / "type-corrupt-run"
    shutil.copytree(valid_child, type_corrupt_dir)
    type_manifest_path = type_corrupt_dir / "manifest.json"
    type_manifest = json.loads(type_manifest_path.read_text(encoding="utf-8"))
    type_manifest["run_id"] = type_corrupt_dir.name
    type_manifest["warnings"] = "not-an-array"
    type_manifest_path.write_text(json.dumps(type_manifest), encoding="utf-8")

    corrupt_dir = real_root / "corrupt-run"
    corrupt_dir.mkdir()
    (corrupt_dir / "manifest.json").write_text("{not-json", encoding="utf-8")
    symlink_dir = real_root / "symlink-manifest-run"
    symlink_dir.mkdir()
    symlink_supported = True
    try:
        (symlink_dir / "manifest.json").symlink_to(valid_child / "manifest.json")
    except OSError:
        symlink_supported = False
        symlink_dir.rmdir()
    db_index_path = real_root / "run-index.jsonl"
    db_command = [
        sys.executable,
        str(ROOT / "scripts" / "run_database.py"),
        "index",
        "--output-root",
        str(real_root),
        "--index",
        str(db_index_path),
    ]
    db_completed = subprocess.run(db_command, cwd=ROOT, text=True, capture_output=True)
    if db_completed.returncode != 0:
        errors.append(f"run database index failed: {db_completed.stderr.strip()}")
        return
    indexed = [json.loads(line) for line in db_index_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    corrupt_record = next((item for item in indexed if item.get("run_id") == "corrupt-run"), None)
    if not corrupt_record or corrupt_record.get("index_error") != "RUN_INDEX_MANIFEST_INVALID_JSON":
        errors.append("corrupt manifest was silently dropped instead of indexed with a diagnostic")
    semantic_record = next((item for item in indexed if item.get("run_id") == "semantic-corrupt-run"), None)
    if not semantic_record or not str(semantic_record.get("index_error", "")).startswith(
        "RUN_INDEX_MANIFEST_STATUS_INCONSISTENT:"
    ):
        errors.append("status-inconsistent manifest was not indexed as a failed diagnostic record")
    type_record = next((item for item in indexed if item.get("run_id") == "type-corrupt-run"), None)
    if not type_record or type_record.get("index_error") != "RUN_INDEX_MANIFEST_FIELD_INVALID:warnings":
        errors.append("field-type-corrupt manifest was not indexed as a failed diagnostic record")
    if symlink_supported:
        symlink_record = next((item for item in indexed if item.get("run_id") == "symlink-manifest-run"), None)
        if not symlink_record or symlink_record.get("index_error") != "RUN_INDEX_MANIFEST_SYMLINK":
            errors.append("symlinked canonical manifest was not rejected by the run index")
    retry_path = real_root / "retry-plan.json"
    retry_command = [
        sys.executable,
        str(ROOT / "scripts" / "run_database.py"),
        "retry-plan",
        "--index",
        str(db_index_path),
        "--output",
        str(retry_path),
    ]
    retry_completed = subprocess.run(retry_command, cwd=ROOT, text=True, capture_output=True)
    if retry_completed.returncode != 0:
        errors.append(f"retry plan failed: {retry_completed.stderr.strip()}")
    else:
        retry_plan = json.loads(retry_path.read_text(encoding="utf-8"))
        if any(item.get("run_id") == "corrupt-run" for item in retry_plan.get("retryable_runs", [])):
            errors.append("corrupt manifest was incorrectly marked retryable")
        invalid_ids = {"semantic-corrupt-run", "type-corrupt-run"}
        retryable_ids = {item.get("run_id") for item in retry_plan.get("retryable_runs", [])}
        if invalid_ids & retryable_ids:
            errors.append("semantically or structurally invalid manifests were incorrectly marked retryable")

    protected_manifest = valid_child / "manifest.json"
    original_protected_manifest = protected_manifest.read_bytes()
    index_overwrite = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "run_database.py"),
            "index",
            "--output-root",
            str(real_root),
            "--index",
            str(protected_manifest),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if index_overwrite.returncode == 0 or protected_manifest.read_bytes() != original_protected_manifest:
        errors.append("run database index was allowed to overwrite a canonical manifest")
    retry_overwrite = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "run_database.py"),
            "retry-plan",
            "--index",
            str(db_index_path),
            "--output",
            str(protected_manifest),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if retry_overwrite.returncode == 0 or protected_manifest.read_bytes() != original_protected_manifest:
        errors.append("run database retry plan was allowed to overwrite a canonical manifest")


def _write_fake_runner(path: Path) -> None:
    path.write_text(
        """from __future__ import annotations
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--output-root', required=True)
parser.add_argument('--run-id', required=True)
parser.add_argument('--input', required=True)
parser.add_argument('--url')
parser.add_argument('--page-type')
args = parser.parse_args()
mode = Path(args.input).name
run_dir = Path(args.output_root) / args.run_id
run_dir.mkdir(parents=True)
if mode == 'missing':
    print(run_dir)
    raise SystemExit(0)
if mode == 'invalid':
    (run_dir / 'manifest.json').write_text('{not-json', encoding='utf-8')
    print(run_dir)
    raise SystemExit(0)
attempt = int(args.run_id.rsplit('-attempt-', 1)[1])
if mode == 'retry' and attempt == 1:
    status, validation_status, review, blockers, returncode = 'failed', 'failed', True, ['TRANSIENT_ADAPTER_FAILURE'], 1
elif mode == 'partial':
    status, validation_status, review, blockers, returncode = 'partial', 'passed', True, [], 0
elif mode == 'policy':
    status, validation_status, review, blockers, returncode = 'aborted_by_policy', 'failed', True, ['SAFETY_RED_ACTION'], 1
elif mode == 'nonzero-complete':
    status, validation_status, review, blockers, returncode = 'complete', 'passed', False, [], 1
else:
    status, validation_status, review, blockers, returncode = 'complete', 'passed', False, [], 0
(run_dir / 'artifacts').mkdir()
(run_dir / 'validation').mkdir()
(run_dir / 'artifacts' / 'output.txt').write_text('fixture', encoding='utf-8')
(run_dir / 'validation' / 'report.json').write_text('{}', encoding='utf-8')
severity = 'blocking' if status in {'failed', 'aborted_by_policy'} else 'warning' if review else 'info'
reasons = [] if not review else [{'code': blockers[0] if blockers else 'MANUAL_REVIEW', 'message': 'fixture', 'severity': severity, 'artifact': 'validation/report.json'}]
manifest = {
    'run_id': args.run_id,
    'task': 'browser-research' if mode == 'wrong-task' else 'page-to-md',
    'started_at': '2026-01-01T00:00:00Z',
    'finished_at': '2026-01-01T00:00:01Z',
    'operator': 'eval',
    'skill': 'page-to-md',
    'inputs': {'fixture': mode},
    'artifacts': [{'id': 'A001', 'type': 'fixture', 'path': 'artifacts/output.txt'}],
    'evidence': [{'id': 'V001', 'type': 'validation_report', 'path': 'validation/report.json'}],
    'validation': {'schema_valid': status != 'failed', 'warnings': 1 if status == 'partial' else 0, 'requires_manual_review': review, 'report_path': 'validation/report.json'},
    'warnings': ['MANUAL_REVIEW'] if status == 'partial' else [],
    'requires_manual_review': review,
    'run_status': status,
    'validation_status': validation_status,
    'manual_review': {'required': review, 'severity': severity, 'reasons': reasons},
    'completion_blockers': blockers,
    'screenshot_policy': {'required': False, 'reason': 'eval_fixture', 'status': 'not_required'},
}
if mode == 'malformed-warnings':
    manifest['warnings'] = [123]
elif mode == 'malformed-validation':
    manifest['validation']['schema_valid'] = 'yes'
elif mode == 'malformed-schema-valid':
    manifest['validation']['schema_valid'] = False
elif mode == 'malformed-validation-review':
    manifest['validation']['requires_manual_review'] = True
elif mode == 'malformed-validation-warning-count':
    manifest['validation']['warnings'] = 1
elif mode == 'malformed-reason':
    manifest['manual_review']['reasons'] = [{'code': 123, 'message': 'fixture', 'severity': 'info', 'artifact': 'validation/report.json'}]
elif mode == 'malformed-screenshot':
    manifest['screenshot_policy']['required'] = 'false'
elif mode == 'malformed-evidence-type':
    manifest['evidence'][0].pop('type')
(run_dir / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
print(run_dir)
raise SystemExit(returncode)
""",
        encoding="utf-8",
    )


def _run_negative_batch(errors: list[str]) -> None:
    negative_root = OUTPUT_ROOT / "negative"
    negative_root.mkdir(parents=True, exist_ok=True)
    fake_runner = negative_root / "fake_runner.py"
    _write_fake_runner(fake_runner)
    spec_path = negative_root / "batch-spec.json"
    modes = [
        "retry",
        "missing",
        "invalid",
        "wrong-task",
        "malformed-warnings",
        "malformed-validation",
        "malformed-schema-valid",
        "malformed-validation-review",
        "malformed-validation-warning-count",
        "malformed-reason",
        "malformed-screenshot",
        "malformed-evidence-type",
        "partial",
        "policy",
    ]
    spec_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "max_retries": 1,
                "jobs": [
                    {
                        "job_id": mode,
                        "run_id": "explicit",
                        "task": "page-to-md",
                        "input": mode,
                        "url": f"https://example.test/{mode}",
                        "page_type": "article",
                    }
                    for mode in modes
                ],
            }
        ),
        encoding="utf-8",
    )
    partial_spec_path = negative_root / "partial-spec.json"
    partial_spec_path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "max_retries": 1,
                "jobs": [
                    {
                        "job_id": mode,
                        "run_id": "explicit",
                        "task": "page-to-md",
                        "input": mode,
                        "url": f"https://example.test/{mode}",
                        "page_type": "article",
                    }
                    for mode in ("partial", "nonzero-complete")
                ],
            }
        ),
        encoding="utf-8",
    )
    invalid_spec_path = negative_root / "invalid-max-retries-spec.json"
    invalid_spec_path.write_text(
        json.dumps({"schema_version": "1.0", "max_retries": {"invalid": True}, "jobs": []}),
        encoding="utf-8",
    )
    orphan_safe_run_id = "orphan-safe-batch"
    try:
        batch_runner.run_batch(
            argparse.Namespace(
                spec=str(invalid_spec_path),
                output_root=str(negative_root),
                run_id=orphan_safe_run_id,
            )
        )
        errors.append("invalid max_retries unexpectedly created a batch run")
    except ValueError:
        pass
    if (negative_root / orphan_safe_run_id).exists():
        errors.append("invalid max_retries left an orphan batch run directory")
    original_runner = batch_runner.TASK_RUNNERS["page-to-md"]
    batch_runner.TASK_RUNNERS["page-to-md"] = str(fake_runner)
    try:
        run_dir = batch_runner.run_batch(
            argparse.Namespace(spec=str(spec_path), output_root=str(negative_root), run_id="negative-batch")
        )
        partial_run_dir = batch_runner.run_batch(
            argparse.Namespace(spec=str(partial_spec_path), output_root=str(negative_root), run_id=orphan_safe_run_id)
        )
    finally:
        batch_runner.TASK_RUNNERS["page-to-md"] = original_runner
    jobs = json.loads((run_dir / "artifacts" / "batch-results.json").read_text(encoding="utf-8"))["jobs"]
    by_id = {item["job_id"]: item for item in jobs}
    retry_job = by_id["retry"]
    retry_ids = [item.get("run_id") for item in retry_job.get("attempt_runs", [])]
    if retry_job.get("status") != "complete" or retry_job.get("attempts") != 2:
        errors.append("retryable failure did not complete on its second attempt")
    if len(retry_ids) != len(set(retry_ids)) or not all(retry_ids):
        errors.append("retry attempts did not use unique run IDs")
    if retry_ids and not all((run_dir / "runs" / run_id / "manifest.json").exists() for run_id in retry_ids):
        errors.append("retry attempt manifests were not retained in separate directories")
    for job_id, expected_code in (
        ("missing", "BATCH_CHILD_MANIFEST_MISSING"),
        ("invalid", "BATCH_CHILD_MANIFEST_INVALID_JSON"),
        ("wrong-task", "BATCH_CHILD_MANIFEST_TASK_MISMATCH"),
        ("malformed-warnings", "BATCH_CHILD_MANIFEST_FIELD_INVALID:warnings"),
        ("malformed-validation", "BATCH_CHILD_MANIFEST_FIELD_INVALID:validation"),
        ("malformed-schema-valid", "BATCH_CHILD_MANIFEST_FIELD_INVALID:validation.schema_valid"),
        (
            "malformed-validation-review",
            "BATCH_CHILD_MANIFEST_FIELD_INVALID:validation.requires_manual_review",
        ),
        ("malformed-validation-warning-count", "BATCH_CHILD_MANIFEST_FIELD_INVALID:validation.warnings"),
        ("malformed-reason", "BATCH_CHILD_MANIFEST_FIELD_INVALID:manual_review.reasons"),
        ("malformed-screenshot", "BATCH_CHILD_MANIFEST_FIELD_INVALID:screenshot_policy"),
        ("malformed-evidence-type", "BATCH_CHILD_MANIFEST_FIELD_INVALID:evidence"),
    ):
        item = by_id[job_id]
        if item.get("status") != "failed" or item.get("attempts") != 1 or item.get("failure_code") != expected_code:
            errors.append(f"{job_id} child manifest was not a non-retryable batch failure")
    if by_id["partial"].get("status") != "partial" or by_id["partial"].get("attempts") != 1:
        errors.append("manual-review partial child was retried or misclassified")
    if by_id["policy"].get("status") != "failed" or by_id["policy"].get("attempts") != 1:
        errors.append("policy-aborted child was retried or misclassified")
    all_attempt_ids = [
        attempt.get("run_id")
        for item in jobs
        for attempt in item.get("attempt_runs", [])
        if attempt.get("run_id")
    ]
    if len(all_attempt_ids) != len(set(all_attempt_ids)):
        errors.append("explicit job run_id caused attempt directory reuse across jobs")
    report = json.loads((run_dir / "validation" / "batch-validation-report.json").read_text(encoding="utf-8"))
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    if report.get("status") != "fail" or manifest.get("run_status") != "failed":
        errors.append("failed children did not aggregate to a failed parent")
    index_records = [
        json.loads(line)
        for line in (run_dir / "artifacts" / "run-index.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not any(item.get("index_error") == "RUN_INDEX_MANIFEST_INVALID_JSON" for item in index_records):
        errors.append("batch child with corrupt manifest disappeared from the batch run index")
    partial_jobs = json.loads((partial_run_dir / "artifacts" / "batch-results.json").read_text(encoding="utf-8"))["jobs"]
    partial_by_id = {item["job_id"]: item for item in partial_jobs}
    partial_report = json.loads(
        (partial_run_dir / "validation" / "batch-validation-report.json").read_text(encoding="utf-8")
    )
    partial_manifest = json.loads((partial_run_dir / "manifest.json").read_text(encoding="utf-8"))
    if (
        partial_report.get("status") != "pass"
        or partial_manifest.get("run_status") != "partial"
        or partial_manifest.get("validation_status") != "passed"
        or partial_manifest.get("completion_blockers")
    ):
        errors.append("review-only children did not aggregate to a schema-valid partial parent")
    if partial_by_id["partial"].get("attempts") != 1:
        errors.append("manual-review partial child was retried in partial-only batch")
    nonzero = partial_by_id["nonzero-complete"]
    if nonzero.get("status") != "complete" or nonzero.get("attempts") != 1:
        errors.append("complete child manifest was overridden by its secondary process exit code")


def _check_retry_classifier(errors: list[str]) -> None:
    def record(run_id: str, status: str, blockers: list[str], *, review: bool = True, **extra: object) -> dict[str, object]:
        return {
            "run_id": run_id,
            "task": "page-to-md",
            "path": run_id,
            "run_status": status,
            "completion_blockers": blockers,
            "warnings": [],
            "requires_manual_review": review,
            "manual_review": {"required": review},
            **extra,
        }

    records = [
        record("transient", "failed", ["ADAPTER_TIMEOUT"]),
        record("private", "failed", ["PRIVACY_RAW_PRIVATE_DATA"]),
        record("scope", "failed", ["DISCOVERY_SCOPE_VIOLATION"]),
        record("policy", "aborted_by_policy", ["SAFETY_RED_ACTION"]),
        record("manual", "partial", [], review=True),
        record("explicit", "failed", ["ADAPTER_TIMEOUT"], non_retryable=True),
        record("invalid", "failed", ["RUN_INDEX_MANIFEST_INVALID_JSON"], index_error="RUN_INDEX_MANIFEST_INVALID_JSON"),
        record("unknown", "unknown", []),
        record(
            "privacy-reason",
            "failed",
            ["ADAPTER_TIMEOUT"],
            manual_review={
                "required": True,
                "reasons": [
                    {
                        "code": "PRIVACY_RAW_PRIVATE_DATA",
                        "message": "private data exposure",
                        "severity": "blocking",
                        "artifact": "validation/report.json",
                    }
                ],
            },
        ),
        {
            "run_id": "bad-types",
            "task": "page-to-md",
            "path": "bad-types",
            "run_status": "failed",
            "completion_blockers": None,
            "warnings": [],
            "requires_manual_review": True,
            "manual_review": {"required": True},
        },
        {
            "run_id": "bad-complete-types",
            "task": "page-to-md",
            "path": "bad-complete-types",
            "run_status": "complete",
            "completion_blockers": [],
            "warnings": "not-an-array",
            "requires_manual_review": False,
            "manual_review": {"required": False},
        },
        [],
    ]
    plan = build_retry_plan(records)  # type: ignore[arg-type]
    retryable_ids = {item.get("run_id") for item in plan.get("retryable_runs", [])}
    if retryable_ids != {"transient"}:
        errors.append(f"retry classifier was not conservative: {sorted(str(item) for item in retryable_ids)}")
    non_retryable = {item.get("run_id"): item.get("classification") for item in plan.get("non_retryable_runs", [])}
    expected = {
        "private",
        "scope",
        "policy",
        "manual",
        "explicit",
        "invalid",
        "unknown",
        "bad-types",
        "bad-complete-types",
        "privacy-reason",
    }
    if not expected.issubset(non_retryable):
        errors.append("retry plan omitted classified non-retryable failures")
    if not any(item.get("classification") == "record_invalid_shape" for item in plan.get("non_retryable_runs", [])):
        errors.append("retry plan did not retain a non-object index record as non-retryable")


def main() -> int:
    if OUTPUT_ROOT.exists():
        shutil.rmtree(OUTPUT_ROOT)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    _run_real_batch(errors)
    _run_negative_batch(errors)
    _check_retry_classifier(errors)
    if errors:
        print("FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
