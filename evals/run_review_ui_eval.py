from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "evals" / ".tmp" / "review-ui"
FIXTURE_ROOT = ROOT / "evals" / "fixtures" / "page-to-md"
VALIDATION_PASS_TEXT = json.dumps(
    {
        "schema_version": "1.0",
        "status": "pass",
        "errors": [],
        "warnings": [],
        "requires_manual_review": False,
        "run_status": "complete",
        "validation_status": "passed",
        "manual_review": {"required": False, "severity": "info", "reasons": []},
        "completion_blockers": [],
    }
)


def _review_command(run_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "review_run.py"), str(run_dir)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )


def _base_manifest(run_id: str, *, status: str = "complete", warning: str | None = None) -> dict[str, object]:
    review_required = status != "complete"
    reason = (
        [{"code": "MANUAL_REVIEW_REASON", "message": "fixture", "severity": "warning", "artifact": "validation/report.json"}]
        if review_required
        else []
    )
    return {
        "run_id": run_id,
        "task": "page-to-md",
        "started_at": "2026-01-01T00:00:00Z",
        "finished_at": "2026-01-01T00:00:01Z",
        "operator": "eval",
        "skill": "page-to-md",
        "inputs": {"fixture": run_id},
        "artifacts": [{"id": "A001", "type": "fixture", "path": "artifacts/output.txt"}],
        "evidence": [{"id": "V001", "type": "validation_report", "path": "validation/report.json"}],
        "validation": {
            "schema_valid": True,
            "warnings": 1 if warning else 0,
            "requires_manual_review": review_required,
            "report_path": "validation/report.json",
        },
        "warnings": [warning] if warning else [],
        "requires_manual_review": review_required,
        "run_status": status,
        "validation_status": "passed",
        "manual_review": {
            "required": review_required,
            "severity": "warning" if review_required else "info",
            "reasons": reason,
        },
        "completion_blockers": [],
        "screenshot_policy": {"required": False, "reason": "eval_fixture", "status": "not_required"},
    }


def _create_run(
    run_id: str,
    manifest: dict[str, object],
    *,
    validation_text: str | None = VALIDATION_PASS_TEXT,
) -> Path:
    run_dir = OUTPUT_ROOT / run_id
    (run_dir / "artifacts").mkdir(parents=True)
    (run_dir / "validation").mkdir()
    (run_dir / "artifacts" / "output.txt").write_text("fixture", encoding="utf-8")
    if validation_text is not None:
        (run_dir / "validation" / "report.json").write_text(validation_text, encoding="utf-8")
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return run_dir


def _check_happy_review(errors: list[str]) -> None:
    page_command = [
        sys.executable,
        str(ROOT / "scripts" / "page_to_md_runner.py"),
        "--input",
        str(FIXTURE_ROOT / "public-article.html"),
        "--url",
        "https://example.test/public-article",
        "--output-root",
        str(OUTPUT_ROOT),
        "--run-id",
        "eval-review-source",
        "--page-type",
        "article",
    ]
    page_completed = subprocess.run(page_command, cwd=ROOT, text=True, capture_output=True)
    if page_completed.returncode != 0:
        errors.append(f"page fixture failed: {page_completed.stderr.strip()}")
        return
    run_dir = OUTPUT_ROOT / "eval-review-source"
    reviewed = _review_command(run_dir)
    if reviewed.returncode != 0:
        errors.append(f"clean review should pass: {reviewed.stderr.strip()} {reviewed.stdout.strip()}".strip())
        return
    review = json.loads((run_dir / "review" / "review.json").read_text(encoding="utf-8"))
    if review.get("review_status") != "pass" or review.get("review_required"):
        errors.append("clean run review did not produce an unambiguous pass")
    review_md = run_dir / "review" / "review.md"
    if "Run status" not in review_md.read_text(encoding="utf-8"):
        errors.append("review markdown missing run status")
    original_manifest = (run_dir / "manifest.json").read_bytes()
    overwrite = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "review_run.py"),
            str(run_dir),
            "--output",
            str(run_dir / "manifest.json"),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if overwrite.returncode == 0 or (run_dir / "manifest.json").read_bytes() != original_manifest:
        errors.append("review output was allowed to overwrite the canonical manifest")

    other_run = _create_run("cross-run-review-target", _base_manifest("cross-run-review-target"))
    other_manifest = other_run / "manifest.json"
    original_other_manifest = other_manifest.read_bytes()
    cross_run_overwrite = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "review_run.py"),
            str(run_dir),
            "--output",
            str(other_run / "manifest.md"),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if cross_run_overwrite.returncode == 0 or other_manifest.read_bytes() != original_other_manifest:
        errors.append("review output was allowed to overwrite another run's canonical manifest")

    review_dir = run_dir / "review"
    shutil.rmtree(review_dir)
    outside_review = OUTPUT_ROOT / "outside-review-symlink-target"
    outside_review.mkdir()
    symlink_supported = True
    try:
        review_dir.symlink_to(outside_review, target_is_directory=True)
    except OSError:
        symlink_supported = False
    if symlink_supported:
        symlink_review = _review_command(run_dir)
        if symlink_review.returncode == 0:
            errors.append("review output followed a symlinked review/ directory outside the run")
        if any(outside_review.iterdir()):
            errors.append("review output wrote through a symlinked review/ directory")


def _check_manual_review(errors: list[str]) -> None:
    manifest = _base_manifest("manual-review", status="partial", warning="MANIFEST_WARNING")
    manual = manifest["manual_review"]
    assert isinstance(manual, dict)
    manual["reasons"] = [
        {
            "code": "PRIVATE_DATA_REDACTED",
            "message": "fixture",
            "severity": "warning",
            "artifact": "validation/report.json",
        }
    ]
    run_dir = _create_run("manual-review", manifest)
    reviewed = _review_command(run_dir)
    if reviewed.returncode != 2:
        errors.append(f"manual-review run should return exit 2, got {reviewed.returncode}")
        return
    review = json.loads((run_dir / "review" / "review.json").read_text(encoding="utf-8"))
    if review.get("status") != "review_required" or review.get("review_status") != "review_required":
        errors.append("manual-review run was silently passed or treated as a blocker")
    if not {"MANIFEST_WARNING", "PRIVATE_DATA_REDACTED"}.issubset(set(review.get("warnings", []))):
        errors.append("review did not merge manifest warnings and manual-review reasons")
    markdown = (run_dir / "review" / "review.md").read_text(encoding="utf-8")
    if "No blockers or warnings found." in markdown:
        errors.append("manual-review markdown incorrectly claimed there were no warnings")


def _check_report_manual_review(errors: list[str]) -> None:
    report = {
        "schema_version": "1.0",
        "status": "pass",
        "errors": [],
        "warnings": [],
        "requires_manual_review": True,
        "run_status": "partial",
        "validation_status": "passed",
        "manual_review": {"required": True, "severity": "warning", "reasons": []},
        "completion_blockers": [],
    }
    run_dir = _create_run("report-review-required", _base_manifest("report-review-required"), validation_text=json.dumps(report))
    reviewed = _review_command(run_dir)
    if reviewed.returncode != 2:
        errors.append(f"validation-report review requirement should return exit 2, got {reviewed.returncode}")
        return
    review = json.loads((run_dir / "review" / "review.json").read_text(encoding="utf-8"))
    if review.get("review_status") != "review_required":
        errors.append("validation report manual-review state was silently passed")
    if review.get("status") != "review_required":
        errors.append("validation report manual-review state retained an ambiguous pass status")


def _check_research_review(errors: list[str]) -> None:
    run_id = "eval-review-research"
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "browser_research_runner.py"),
            "--input",
            str(ROOT / "evals" / "fixtures" / "browser-research" / "evidence-backed-research.json"),
            "--output-root",
            str(OUTPUT_ROOT),
            "--run-id",
            run_id,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        errors.append(f"research review fixture failed: {completed.stderr.strip()}")
        return
    run_dir = OUTPUT_ROOT / run_id
    reviewed = _review_command(run_dir)
    if reviewed.returncode == 1:
        errors.append(f"valid research run was treated as a blocking review failure: {reviewed.stderr.strip()}")
        return
    review = json.loads((run_dir / "review" / "review.json").read_text(encoding="utf-8"))
    if any("missing-sources.md" in str(item) for item in review.get("blockers", [])):
        errors.append("research missing_sources_path was incorrectly treated as a validation report")


def _check_blocking_cases(errors: list[str]) -> None:
    missing_report = _create_run(
        "missing-report",
        _base_manifest("missing-report"),
        validation_text=None,
    )
    corrupt_report = _create_run(
        "corrupt-report",
        _base_manifest("corrupt-report"),
        validation_text="{not-json",
    )
    invalid_shape_report = _create_run(
        "invalid-shape-report",
        _base_manifest("invalid-shape-report"),
        validation_text="{}",
    )
    non_json_manifest = _base_manifest("non-json-report")
    non_json_manifest["evidence"] = [{"id": "V001", "type": "validation_report", "path": "validation/report.txt"}]
    non_json_manifest["validation"] = {"report_path": "validation/report.txt"}
    non_json_report = _create_run("non-json-report", non_json_manifest, validation_text=None)
    (non_json_report / "validation" / "report.txt").write_text(VALIDATION_PASS_TEXT, encoding="utf-8")
    escape_manifest = _base_manifest("escape-path")
    escape_manifest["evidence"] = [{"id": "V001", "type": "validation_report", "path": "../outside.json"}]
    escape_manifest["validation"] = {}
    escape_path = _create_run("escape-path", escape_manifest)

    undeclared_manifest = _base_manifest("undeclared-report")
    undeclared_manifest["evidence"] = []
    undeclared_manifest["validation"] = {
        "schema_valid": True,
        "warnings": 0,
        "requires_manual_review": False,
    }
    undeclared_report = _create_run("undeclared-report", undeclared_manifest, validation_text=None)

    corrupt_manifest = OUTPUT_ROOT / "corrupt-manifest"
    corrupt_manifest.mkdir()
    (corrupt_manifest / "manifest.json").write_text("{not-json", encoding="utf-8")

    empty_manifest = OUTPUT_ROOT / "empty-manifest"
    empty_manifest.mkdir()
    (empty_manifest / "manifest.json").write_text("{}", encoding="utf-8")

    incomplete_manifest = _create_run(
        "incomplete-manifest",
        {
            "run_id": "incomplete-manifest",
            "run_status": "complete",
            "validation_status": "passed",
            "requires_manual_review": False,
            "manual_review": {"required": False, "severity": "info", "reasons": []},
            "completion_blockers": [],
        },
    )

    symlink_manifest = OUTPUT_ROOT / "symlink-manifest"
    symlink_manifest.mkdir()
    symlink_target = OUTPUT_ROOT / "outside-review-manifest.json"
    symlink_target.write_text(json.dumps(_base_manifest("symlink-manifest")), encoding="utf-8")
    symlink_supported = True
    try:
        (symlink_manifest / "manifest.json").symlink_to(symlink_target)
    except OSError:
        symlink_supported = False

    inconsistent_manifest = _base_manifest("inconsistent-complete")
    inconsistent_manifest["requires_manual_review"] = True
    inconsistent_manifest["manual_review"] = {
        "required": True,
        "severity": "warning",
        "reasons": [{"code": "REVIEW_REQUIRED", "message": "fixture", "severity": "warning", "artifact": "manifest.json"}],
    }
    inconsistent = _create_run("inconsistent-complete", inconsistent_manifest)

    expected_fragments = {
        missing_report: "manifest.validation.report_path_missing_on_disk",
        corrupt_report: "REVIEW_VALIDATION_REPORT_INVALID_JSON",
        invalid_shape_report: "REVIEW_VALIDATION_REPORT_REQUIRED_FIELD_MISSING",
        non_json_report: "REVIEW_VALIDATION_REPORT_NOT_JSON",
        escape_path: "path_invalid",
        undeclared_report: "REVIEW_VALIDATION_REPORT_UNDECLARED",
        corrupt_manifest: "REVIEW_MANIFEST_INVALID_JSON",
        empty_manifest: "REVIEW_MANIFEST_EMPTY",
        incomplete_manifest: "REVIEW_MANIFEST_SHAPE:required_field_missing",
        inconsistent: "manifest.complete_requires_manual_review",
    }
    if symlink_supported:
        expected_fragments[symlink_manifest] = "REVIEW_MANIFEST_SYMLINK"
    for run_dir, expected_fragment in expected_fragments.items():
        reviewed = _review_command(run_dir)
        if reviewed.returncode != 1:
            errors.append(f"{run_dir.name} should be a blocking review failure")
            continue
        review_path = run_dir / "review" / "review.json"
        if not review_path.exists():
            errors.append(f"{run_dir.name} did not produce an auditable review result")
            continue
        review = json.loads(review_path.read_text(encoding="utf-8"))
        if review.get("review_status") != "fail":
            errors.append(f"{run_dir.name} did not record review_status=fail")
        if not any(expected_fragment in str(item) for item in review.get("blockers", [])):
            errors.append(f"{run_dir.name} missing blocker diagnostic {expected_fragment}")


def main() -> int:
    if OUTPUT_ROOT.exists():
        shutil.rmtree(OUTPUT_ROOT)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    _check_happy_review(errors)
    _check_manual_review(errors)
    _check_report_manual_review(errors)
    _check_research_review(errors)
    _check_blocking_cases(errors)
    if errors:
        print("FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
