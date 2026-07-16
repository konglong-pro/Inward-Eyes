from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "evals" / ".tmp" / "exports"
FIXTURE_ROOT = ROOT / "evals" / "fixtures" / "page-to-md"


def _export(run_dir: Path, output_dir: Path | None = None) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(ROOT / "scripts" / "export_run.py"), str(run_dir)]
    if output_dir is not None:
        command.extend(["--output-dir", str(output_dir)])
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=True)


def _copy_run(source: Path, name: str) -> Path:
    destination = OUTPUT_ROOT / name
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns("exports", "review"))
    manifest_path = destination / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return destination
    if isinstance(manifest, dict):
        manifest["run_id"] = name
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return destination


def _check_happy_export(errors: list[str]) -> Path | None:
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
        "eval-export-source",
        "--page-type",
        "article",
    ]
    page_completed = subprocess.run(page_command, cwd=ROOT, text=True, capture_output=True)
    if page_completed.returncode != 0:
        errors.append(f"page fixture failed: {page_completed.stderr.strip()}")
        return None
    run_dir = OUTPUT_ROOT / "eval-export-source"
    exported = _export(run_dir)
    if exported.returncode != 0:
        errors.append(f"export runner failed: {exported.stderr.strip()}")
        return run_dir
    for relative in (
        "exports/run-summary.json",
        "exports/artifact-index.csv",
        "exports/source-index.csv",
        "exports/run-summary.md",
    ):
        if not (run_dir / relative).exists():
            errors.append(f"export missing {relative}")
    summary = json.loads((run_dir / "exports" / "run-summary.json").read_text(encoding="utf-8"))
    sources = summary.get("source_records", [])
    if summary.get("source_count") != 1 or len(sources) != 1:
        errors.append("export summary did not consume the canonical source record")
    else:
        source = sources[0]
        record = source.get("record", {})
        if source.get("source_record_path") != "evidence/source_record.json":
            errors.append("export summary lost source-record path traceability")
        if record.get("source_id") != "S001" or record.get("url") != "https://example.test/public-article":
            errors.append("export summary source identity does not match canonical evidence")
    source_csv = (run_dir / "exports" / "source-index.csv").read_text(encoding="utf-8")
    if "source_record_path" not in source_csv or "S001" not in source_csv:
        errors.append("source index CSV lacks canonical source traceability")
    markdown = (run_dir / "exports" / "run-summary.md").read_text(encoding="utf-8")
    if "## Canonical Sources" not in markdown or "S001" not in markdown:
        errors.append("Markdown export lacks canonical source traceability")
    return run_dir


def _expect_export_failure(
    errors: list[str],
    run_dir: Path,
    expected_fragment: str,
    *,
    output_dir: Path | None = None,
) -> None:
    destination = output_dir or run_dir / "negative-export"
    exported = _export(run_dir, destination)
    if exported.returncode == 0:
        errors.append(f"{run_dir.name} export should have failed")
        return
    diagnostic = f"{exported.stdout}\n{exported.stderr}"
    if expected_fragment not in diagnostic:
        errors.append(f"{run_dir.name} missing clear export diagnostic {expected_fragment}")
    if not destination.exists() and output_dir is None:
        return
    if destination.is_dir() and any(destination.glob("run-summary.*")):
        errors.append(f"{run_dir.name} wrote a partial summary despite export failure")


def _check_negative_exports(errors: list[str], source_run: Path) -> None:
    source_relative = "evidence/source_record.json"

    missing_source = _copy_run(source_run, "missing-source")
    (missing_source / source_relative).unlink()
    _expect_export_failure(errors, missing_source, "source record missing")

    corrupt_source = _copy_run(source_run, "corrupt-source")
    (corrupt_source / source_relative).write_text("{not-json", encoding="utf-8")
    _expect_export_failure(errors, corrupt_source, "source record is not valid JSON")

    invalid_source = _copy_run(source_run, "invalid-source")
    source_record = json.loads((invalid_source / source_relative).read_text(encoding="utf-8"))
    source_record.pop("url")
    (invalid_source / source_relative).write_text(json.dumps(source_record), encoding="utf-8")
    _expect_export_failure(errors, invalid_source, "source record missing required fields")

    invalid_evidence_type = _copy_run(source_run, "invalid-evidence-type")
    source_record = json.loads((invalid_evidence_type / source_relative).read_text(encoding="utf-8"))
    source_record["evidence"]["screenshot"] = 123
    (invalid_evidence_type / source_relative).write_text(json.dumps(source_record), encoding="utf-8")
    _expect_export_failure(errors, invalid_evidence_type, "invalid evidence.screenshot")

    missing_nested_evidence = _copy_run(source_run, "missing-nested-evidence")
    source_record = json.loads((missing_nested_evidence / source_relative).read_text(encoding="utf-8"))
    source_record["evidence"]["snapshot"] = "evidence/missing.snapshot.json"
    (missing_nested_evidence / source_relative).write_text(json.dumps(source_record), encoding="utf-8")
    _expect_export_failure(errors, missing_nested_evidence, "source record evidence path missing")

    undeclared_nested_evidence = _copy_run(source_run, "undeclared-nested-evidence")
    source_record = json.loads((undeclared_nested_evidence / source_relative).read_text(encoding="utf-8"))
    source_record["evidence"]["snapshot"] = "artifacts/page.md"
    (undeclared_nested_evidence / source_relative).write_text(json.dumps(source_record), encoding="utf-8")
    _expect_export_failure(errors, undeclared_nested_evidence, "source record evidence path is not declared by manifest")

    missing_required_screenshot = _copy_run(source_run, "missing-required-screenshot")
    source_record = json.loads((missing_required_screenshot / source_relative).read_text(encoding="utf-8"))
    source_record["screenshot_policy"] = {
        "required": True,
        "reason": "manual_challenge",
        "status": "required_and_present",
    }
    source_record["evidence"]["screenshot"] = None
    (missing_required_screenshot / source_relative).write_text(json.dumps(source_record), encoding="utf-8")
    _expect_export_failure(errors, missing_required_screenshot, "required screenshot evidence missing")

    wrong_screenshot_type = _copy_run(source_run, "wrong-screenshot-type")
    source_record = json.loads((wrong_screenshot_type / source_relative).read_text(encoding="utf-8"))
    screenshot_path = "evidence/fake-screenshot.png"
    (wrong_screenshot_type / screenshot_path).write_bytes(b"not-a-real-png")
    source_record["screenshot_policy"] = {
        "required": True,
        "reason": "manual_challenge",
        "status": "required_and_present",
    }
    source_record["evidence"]["screenshot"] = screenshot_path
    (wrong_screenshot_type / source_relative).write_text(json.dumps(source_record), encoding="utf-8")
    manifest = json.loads((wrong_screenshot_type / "manifest.json").read_text(encoding="utf-8"))
    manifest["evidence"].append({"id": "S001", "type": "snapshot", "path": screenshot_path})
    (wrong_screenshot_type / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    _expect_export_failure(errors, wrong_screenshot_type, "screenshot expected screenshot")

    corrupt_manifest = _copy_run(source_run, "corrupt-manifest")
    (corrupt_manifest / "manifest.json").write_text("{not-json", encoding="utf-8")
    _expect_export_failure(errors, corrupt_manifest, "manifest is not valid JSON")

    escaped_source = _copy_run(source_run, "escaped-source")
    manifest = json.loads((escaped_source / "manifest.json").read_text(encoding="utf-8"))
    source_entry = next(item for item in manifest["evidence"] if item.get("type") == "source_record")
    source_entry["path"] = "../outside-source.json"
    (escaped_source / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    _expect_export_failure(errors, escaped_source, "source record path escapes run directory")

    undeclared_source = _copy_run(source_run, "undeclared-source")
    manifest = json.loads((undeclared_source / "manifest.json").read_text(encoding="utf-8"))
    manifest["evidence"] = [item for item in manifest["evidence"] if item.get("type") != "source_record"]
    (undeclared_source / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    _expect_export_failure(errors, undeclared_source, "declares no canonical source records")

    inconsistent = _copy_run(source_run, "inconsistent-status")
    manifest = json.loads((inconsistent / "manifest.json").read_text(encoding="utf-8"))
    manifest["requires_manual_review"] = True
    manifest["manual_review"] = {
        "required": True,
        "severity": "warning",
        "reasons": [{"code": "REVIEW_REQUIRED", "message": "fixture", "severity": "warning", "artifact": "manifest.json"}],
    }
    manifest["validation"]["requires_manual_review"] = True
    (inconsistent / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    _expect_export_failure(errors, inconsistent, "manifest status is inconsistent")

    missing_task = _copy_run(source_run, "missing-task")
    manifest = json.loads((missing_task / "manifest.json").read_text(encoding="utf-8"))
    manifest.pop("task")
    (missing_task / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    _expect_export_failure(errors, missing_task, "manifest shape is invalid: required_field_missing:task")

    unknown_task = _copy_run(source_run, "unknown-task")
    manifest = json.loads((unknown_task / "manifest.json").read_text(encoding="utf-8"))
    manifest["task"] = "unknown-workflow"
    (unknown_task / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    _expect_export_failure(errors, unknown_task, "manifest task is not exportable")

    mismatched_run_id = _copy_run(source_run, "mismatched-run-id")
    manifest = json.loads((mismatched_run_id / "manifest.json").read_text(encoding="utf-8"))
    manifest["run_id"] = "different-run-id"
    (mismatched_run_id / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    _expect_export_failure(errors, mismatched_run_id, "manifest shape is invalid: run_id_mismatch")

    invalid_skill = _copy_run(source_run, "invalid-skill")
    manifest = json.loads((invalid_skill / "manifest.json").read_text(encoding="utf-8"))
    manifest["skill"] = 123
    (invalid_skill / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    _expect_export_failure(errors, invalid_skill, "manifest shape is invalid: field_invalid:skill")

    symlink_manifest = _copy_run(source_run, "symlink-manifest")
    (symlink_manifest / "manifest.json").unlink()
    symlink_supported = True
    try:
        (symlink_manifest / "manifest.json").symlink_to(source_run / "manifest.json")
    except OSError:
        symlink_supported = False
    if symlink_supported:
        _expect_export_failure(errors, symlink_manifest, "manifest must not be a symlink")

    canonical_output = source_run / "evidence"
    _expect_export_failure(
        errors,
        source_run,
        "must stay under the derived exports/ directory",
        output_dir=canonical_output,
    )
    if (canonical_output / "run-summary.json").exists():
        errors.append("exporter modified the canonical evidence directory")

    cross_run_target = _copy_run(source_run, "cross-run-export-target")
    cross_run_manifest = cross_run_target / "manifest.json"
    original_cross_run_manifest = cross_run_manifest.read_bytes()
    _expect_export_failure(
        errors,
        source_run,
        "must not modify another canonical run",
        output_dir=cross_run_target / "artifacts",
    )
    if cross_run_manifest.read_bytes() != original_cross_run_manifest:
        errors.append("exporter modified another run's canonical manifest")

    exports_dir = source_run / "exports"
    if exports_dir.exists():
        shutil.rmtree(exports_dir)
    outside_exports = OUTPUT_ROOT / "outside-export-symlink-target"
    outside_exports.mkdir()
    symlink_supported = True
    try:
        exports_dir.symlink_to(outside_exports, target_is_directory=True)
    except OSError:
        symlink_supported = False
    if symlink_supported:
        _expect_export_failure(
            errors,
            source_run,
            "must not traverse a symlink",
            output_dir=exports_dir,
        )
        if any(outside_exports.iterdir()):
            errors.append("exporter wrote through a symlinked exports/ directory")


def _check_multi_source_export(errors: list[str]) -> None:
    run_command = [
        sys.executable,
        str(ROOT / "scripts" / "browser_research_runner.py"),
        "--input",
        str(ROOT / "evals" / "fixtures" / "browser-research" / "evidence-backed-research.json"),
        "--output-root",
        str(OUTPUT_ROOT),
        "--run-id",
        "eval-export-research",
    ]
    completed = subprocess.run(run_command, cwd=ROOT, text=True, capture_output=True)
    if completed.returncode != 0:
        errors.append(f"research export fixture failed: {completed.stderr.strip()}")
        return
    run_dir = OUTPUT_ROOT / "eval-export-research"
    exported = _export(run_dir)
    if exported.returncode != 0:
        errors.append(f"multi-source export failed: {exported.stderr.strip()}")
        return
    summary = json.loads((run_dir / "exports" / "run-summary.json").read_text(encoding="utf-8"))
    source_records = summary.get("source_records", [])
    source_ids = {item.get("record", {}).get("source_id") for item in source_records}
    source_paths = {item.get("source_record_path") for item in source_records}
    if summary.get("source_count") != 2 or source_ids != {"S001", "S002"}:
        errors.append("multi-source export did not preserve both canonical source identities")
    if source_paths != {
        "evidence/source-001/source_record.json",
        "evidence/source-002/source_record.json",
    }:
        errors.append("multi-source export did not preserve source-directory traceability")

    mismatched_source_dir = _copy_run(run_dir, "mismatched-source-directory")
    manifest = json.loads((mismatched_source_dir / "manifest.json").read_text(encoding="utf-8"))
    source_entry = next(
        item
        for item in manifest["evidence"]
        if item.get("type") == "source_record" and item.get("path") == "evidence/source-001/source_record.json"
    )
    original_source_path = mismatched_source_dir / source_entry["path"]
    wrong_relative_path = "evidence/source-099/source_record.json"
    wrong_source_path = mismatched_source_dir / wrong_relative_path
    wrong_source_path.parent.mkdir(parents=True)
    source_record = json.loads(original_source_path.read_text(encoding="utf-8"))
    source_record["evidence"]["source_record"] = wrong_relative_path
    wrong_source_path.write_text(json.dumps(source_record), encoding="utf-8")
    source_entry["path"] = wrong_relative_path
    (mismatched_source_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    _expect_export_failure(errors, mismatched_source_dir, "source record path does not match source_id")


def main() -> int:
    if OUTPUT_ROOT.exists():
        shutil.rmtree(OUTPUT_ROOT)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []
    source_run = _check_happy_export(errors)
    if source_run is not None:
        _check_negative_exports(errors, source_run)
    _check_multi_source_export(errors)
    if errors:
        print("FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
