from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from inward_eyes.io import read_json, utc_now, write_bytes, write_json, write_text  # noqa: E402
from inward_eyes.capture import capture_admissibility_errors, screenshot_file_is_valid  # noqa: E402
from inward_eyes.paths import (  # noqa: E402
    create_continuation_handoff,
    prepare_run_dir,
    resolve_run_relative,
    validate_run_id,
    validate_source_id,
)
from inward_eyes.research import source_dir_name  # noqa: E402
from inward_eyes.validation import validate_browser_research_run  # noqa: E402

SCREENSHOT_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
RESEARCH_RENDER_STAGE_MANIFEST = "validation/browser-research-stage-manifest.json"
RESEARCH_CAPTURE_STAGE_MANIFEST = "validation/research-capture-stage-manifest.json"


def _slug_timestamp(timestamp: str) -> str:
    return re.sub(r"[^0-9TZ]", "", timestamp)


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _strings(value: Any) -> list[str]:
    return [str(item) for item in _as_list(value) if str(item).strip()]


def _safe_asset_name(raw_name: str, index: int) -> str:
    path = Path(raw_name)
    suffix = path.suffix.lower()
    if suffix not in SCREENSHOT_EXTENSIONS:
        suffix = ".png"
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", path.stem).strip(".-") or f"screenshot-{index:03d}"
    return f"{index:03d}-{stem}{suffix}"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _sha256_bytes(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _append_optional(command: list[str], flag: str, value: Any) -> None:
    if value is not None:
        command.extend([flag, str(value)])


def _append_repeated(command: list[str], flag: str, values: list[Any]) -> None:
    for value in values:
        command.extend([flag, str(value)])


def _load_spec(args: argparse.Namespace, *, input_bytes: bytes | None = None) -> dict[str, Any]:
    spec: dict[str, Any] = {}
    if args.input:
        if input_bytes is None:
            input_bytes = Path(args.input).resolve().read_bytes()
        loaded = json.loads(input_bytes.decode("utf-8"))
        if not isinstance(loaded, dict):
            raise SystemExit("M8 input JSON must be an object")
        spec.update(loaded)
    if args.topic:
        spec["topic"] = args.topic
    if args.question:
        spec["question"] = args.question
    if args.url:
        spec.setdefault("sources", [])
        spec["sources"].extend({"url": url, "approved": True} for url in args.url)
    if args.claims_file:
        claims_doc = read_json(Path(args.claims_file).resolve())
        if not isinstance(claims_doc, dict):
            raise SystemExit("--claims-file must point to a JSON object")
        for key in ("summary", "claims", "unknowns", "warnings"):
            if key in claims_doc:
                spec[key] = claims_doc[key]
    return spec


def _validate_source_scope(sources: list[dict[str, Any]], *, min_sources: int, max_sources: int) -> None:
    if len(sources) < min_sources:
        raise SystemExit(f"M8 requires at least {min_sources} approved source URLs by default")
    if len(sources) > max_sources:
        raise SystemExit(f"M8 accepts at most {max_sources} approved source URLs for one run")
    for index, source in enumerate(sources, start=1):
        if not source.get("url"):
            raise SystemExit(f"source {index} missing url")
        if source.get("approved") is False:
            raise SystemExit(f"source {index} is not approved")


def _source_capture_backend(source: dict[str, Any]) -> str:
    backend = str(source.get("capture_backend") or source.get("backend") or "public_url")
    if backend not in {"public_url", "current_chrome"}:
        raise SystemExit(f"unsupported source capture backend: {backend}")
    return backend


def _source_screenshot_values(source: dict[str, Any]) -> list[str]:
    screenshots = source.get("screenshots")
    if isinstance(screenshots, list):
        return [str(item) for item in screenshots]
    if source.get("screenshot"):
        return [str(source["screenshot"])]
    return []


def _preflight_source_input(source: dict[str, Any], index: int) -> None:
    validate_source_id(str(source.get("source_id") or f"S{index:03d}"))
    _source_capture_backend(source)
    for field in (
        "url",
        "capture_id",
        "page_title",
        "title",
        "canonical_url",
        "site_name",
        "failure_reason",
        "screenshot_reason",
        "login_state",
        "page_type",
    ):
        value = source.get(field)
        if value is not None and "\x00" in str(value):
            raise ValueError(f"source {index} {field} must not contain NUL")
    for field in ("screenshots", "warnings", "actions", "redaction_notes"):
        for value in _as_list(source.get(field)):
            if "\x00" in str(value):
                raise ValueError(f"source {index} {field} must not contain NUL")
    if source.get("screenshot") is not None and "\x00" in str(source["screenshot"]):
        raise ValueError(f"source {index} screenshot must not contain NUL")
    for field in (
        "html_file",
        "text_file",
        "selected_main_content_file",
        "accessibility_snapshot_file",
    ):
        if source.get(field):
            value = str(source[field])
            if "\x00" in value:
                raise ValueError(f"source {index} {field} must not contain NUL")
            Path(value).resolve()


def _write_observation_file(source_dir: Path, name: str, value: Any) -> str | None:
    if value is None:
        return None
    path = source_dir / name
    if isinstance(value, (dict, list)):
        write_json(path, value)
    else:
        write_text(path, str(value))
    return str(path)


def _observation_file(source: dict[str, Any], source_dir: Path, key: str, file_key: str, filename: str) -> str | None:
    if source.get(file_key):
        return str(Path(str(source[file_key])).resolve())
    return _write_observation_file(source_dir, filename, source.get(key))


def _capture_command(
    *,
    source: dict[str, Any],
    source_index: int,
    adapter_output_root: Path,
    final_source_dir: Path,
) -> list[str]:
    backend = _source_capture_backend(source)
    script_name = "current_chrome_capture.py" if backend == "current_chrome" else "playwright_mcp_capture.py"
    command = [
        sys.executable,
        str(SCRIPT_ROOT / "capture" / script_name),
        "--url",
        str(source["url"]),
        "--output-root",
        str(adapter_output_root),
        "--run-id",
        f"source-{source_index:03d}",
    ]
    if source.get("capture_id"):
        command.extend(["--capture-id", str(source["capture_id"])])

    title = source.get("page_title") or source.get("title")
    if title:
        command.extend(["--page-title", str(title)])
    _append_optional(command, "--canonical-url", source.get("canonical_url"))
    _append_optional(command, "--site-name", source.get("site_name"))

    html_file = _observation_file(source, final_source_dir, "html", "html_file", "observed.html")
    text_file = _observation_file(source, final_source_dir, "text", "text_file", "observed.txt")
    selected_file = _observation_file(
        source,
        final_source_dir,
        "selected_main_content",
        "selected_main_content_file",
        "selected-main-content.txt",
    )
    snapshot_file = _observation_file(
        source,
        final_source_dir,
        "accessibility_snapshot",
        "accessibility_snapshot_file",
        "accessibility-snapshot.json",
    )
    _append_optional(command, "--html-file", html_file)
    _append_optional(command, "--text-file", text_file)
    _append_optional(command, "--selected-main-content-file", selected_file)
    snapshot_flag = (
        "--accessibility-snapshot-json"
        if isinstance(source.get("accessibility_snapshot"), (dict, list))
        else "--accessibility-snapshot-file"
    )
    _append_optional(command, snapshot_flag, snapshot_file)

    if backend == "public_url" and source.get("failure_reason"):
        _append_optional(command, "--failure-reason", source.get("failure_reason"))
    if source.get("requires_login"):
        command.append("--requires-login")
    if source.get("screenshot_required"):
        command.append("--screenshot-required")
    _append_optional(command, "--screenshot-reason", source.get("screenshot_reason"))
    _append_repeated(command, "--screenshot", _source_screenshot_values(source))
    _append_repeated(command, "--warning", _strings(source.get("warnings")))
    _append_repeated(command, "--action", _strings(source.get("actions")))

    if backend == "current_chrome":
        if source.get("user_approved_current_page"):
            command.append("--user-approved-current-page")
        _append_optional(command, "--login-state", source.get("login_state"))
        if source.get("contains_private_data"):
            command.append("--contains-private-data")
        if source.get("redaction_applied"):
            command.append("--redaction-applied")
        if source.get("screenshot_privacy_reviewed"):
            command.append("--screenshot-privacy-reviewed")
        _append_repeated(command, "--redaction-note", _strings(source.get("redaction_notes")))
        if source.get("page_type"):
            _append_optional(command, "--page-type", source.get("page_type"))
    return command


def _read_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        loaded = read_json(path)
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return loaded if isinstance(loaded, dict) else None


def _capture_asset_roots(capture_path: Path) -> list[Path]:
    return list(dict.fromkeys([capture_path.parent.resolve(), capture_path.parent.parent.resolve()]))


def _resolve_capture_asset(raw_path: str, capture_path: Path) -> Path | None:
    if (
        not raw_path
        or "\x00" in raw_path
        or "\\" in raw_path
        or ":" in raw_path
        or raw_path.startswith("/")
        or any(part in {"", ".", ".."} for part in raw_path.split("/"))
    ):
        return None
    path = Path(*raw_path.split("/"))
    for root in _capture_asset_roots(capture_path):
        try:
            candidate = (root / path).resolve()
        except OSError:
            continue
        try:
            candidate.relative_to(root)
        except ValueError:
            continue
        if candidate.is_file():
            return candidate
    return None


def _stage_source_screenshots(
    *,
    capture: dict[str, Any],
    capture_path: Path,
    run_dir: Path,
    source_id: str,
    warnings: list[str],
) -> list[dict[str, Any]]:
    assets = capture.get("assets") if isinstance(capture.get("assets"), dict) else {}
    raw_screenshots = assets.get("screenshots") if isinstance(assets.get("screenshots"), list) else []
    staged: list[dict[str, Any]] = []
    for index, item in enumerate(raw_screenshots, start=1):
        if isinstance(item, str):
            raw_path = item
            captured_at = capture.get("captured_at")
        elif isinstance(item, dict):
            raw_path = str(item.get("path") or "")
            captured_at = item.get("captured_at") or capture.get("captured_at")
        else:
            warnings.append(f"{source_id}:screenshot_asset_invalid:{index}")
            continue
        source_path = _resolve_capture_asset(raw_path, capture_path)
        if source_path is None or not screenshot_file_is_valid(source_path):
            warnings.append(f"{source_id}:screenshot_asset_missing:{raw_path}")
            continue
        destination = run_dir / "evidence" / source_dir_name(source_id) / "screenshots" / _safe_asset_name(raw_path, index)
        destination.parent.mkdir(parents=True, exist_ok=True)
        write_bytes(destination, source_path.read_bytes())
        if not screenshot_file_is_valid(destination):
            destination.unlink(missing_ok=True)
            warnings.append(f"{source_id}:screenshot_asset_copy_invalid:{raw_path}")
            continue
        staged.append(
            {
                "type": "screenshot",
                "path": destination.relative_to(run_dir).as_posix(),
                "captured_at": str(captured_at or capture.get("captured_at") or ""),
                "sha256": _sha256_file(destination),
            }
        )
    return staged


def _default_independence(source: dict[str, Any]) -> dict[str, Any]:
    independence = source.get("independence")
    if isinstance(independence, dict):
        return independence
    source_type = str(source.get("source_type") or "web_page")
    return {
        "status": "primary_source" if source_type in {"primary", "project_contract", "project_plan"} else "unknown",
        "related_to": None,
        "reason": source.get("independence_note") or "not_declared",
    }


def _source_summary_from_capture(
    *,
    source: dict[str, Any],
    source_id: str,
    capture: dict[str, Any] | None,
    capture_report: dict[str, Any] | None,
    staged_screenshots: list[dict[str, Any]],
    source_warnings: list[str],
    accessed_at: str,
) -> dict[str, Any]:
    capture_source = capture.get("source") if isinstance(capture, dict) and isinstance(capture.get("source"), dict) else {}
    screenshot_policy = (
        capture.get("screenshot_policy")
        if isinstance(capture, dict) and isinstance(capture.get("screenshot_policy"), dict)
        else {"required": False, "reason": "capture_failed", "status": "capture_failed"}
    )
    evidence_dir = source_dir_name(source_id)
    screenshot = staged_screenshots[0]["path"] if staged_screenshots else None
    if screenshot_policy.get("status") == "required_and_present" and screenshot is None:
        screenshot_policy = {**screenshot_policy, "status": "required_but_missing"}

    return {
        "source_id": source_id,
        "url": str(capture_source.get("url") or source.get("url") or ""),
        "canonical_url": capture_source.get("canonical_url") or source.get("canonical_url"),
        "title": capture_source.get("page_title") or source.get("title") or source.get("page_title") or "Capture failed",
        "site_name": capture_source.get("site_name") or source.get("site_name"),
        "source_type": str(source.get("source_type") or "web_page"),
        "page_type": str(source.get("page_type") or capture_source.get("page_type") or "unknown"),
        "accessed_at": str((capture or {}).get("captured_at") or accessed_at),
        "requires_login": bool(capture_source.get("requires_login") or source.get("requires_login")),
        "capture_method": str((capture or {}).get("capture_method") or "capture_failed"),
        "evidence_status": "source_record_present" if capture else "capture_failed",
        "evidence_path": f"evidence/{evidence_dir}/source_record.json",
        "screenshot": screenshot,
        "snapshot": f"capture/{evidence_dir}/page_capture.json" if capture else None,
        "screenshot_policy": screenshot_policy,
        "content_scope": source.get("content_scope")
        if isinstance(source.get("content_scope"), dict)
        else {
            "included": _strings(source.get("included")) or ["task_relevant_content"],
            "excluded": _strings(source.get("excluded"))
            or ["ads", "navigation", "recommendations", "comments_unless_relevant"],
        },
        "independence": _default_independence(source),
        "independence_note": source.get("independence_note"),
        "notes": source.get("notes"),
        "warnings": list(dict.fromkeys(source_warnings + _strings((capture_report or {}).get("warnings")))),
    }


def _fallback_unknown_claim(question: str, sources: list[dict[str, Any]]) -> dict[str, Any]:
    source_ids = [source["source_id"] for source in sources]
    return {
        "claim_id": "U001",
        "text": "No supported key claims were generated because no claim ledger was provided.",
        "claim_type": "unknown",
        "claim_role": "unknown",
        "is_key_finding": True,
        "source_ids": [],
        "support": [],
        "single_source": False,
        "confidence": "unknown",
        "sources_checked": source_ids,
        "notes": f"Captured sources for the question but did not synthesize claims: {question}",
    }


def _write_warnings(path: Path, warnings: list[str]) -> None:
    if not warnings:
        write_text(path, "No warnings.\n")
        return
    lines = ["# Warnings", ""]
    lines.extend(f"- {warning}" for warning in warnings)
    write_text(path, "\n".join(lines) + "\n")


def _manual_review_reason(code: str, severity: str = "warning") -> dict[str, str]:
    return {
        "code": code,
        "message": code.replace("_", " "),
        "severity": severity,
        "artifact": "validation/claim-coverage-report.json",
    }


def _augment_validation_report(
    report: dict[str, Any],
    *,
    capture_warnings: list[str],
    capture_failures: list[str],
    captured_source_count: int,
) -> dict[str, Any]:
    augmented = dict(report)
    warnings = list(dict.fromkeys(list(augmented.get("warnings") or []) + capture_warnings + capture_failures))
    errors = list(augmented.get("errors") or [])
    manual_review = bool(augmented.get("requires_manual_review") or capture_warnings or capture_failures)
    if captured_source_count == 0 and "all_source_captures_failed" not in errors:
        errors.append("all_source_captures_failed")
    status = "fail" if errors else str(augmented.get("status") or "pass")
    run_status = "failed" if status == "fail" else "partial" if manual_review else "complete"
    reasons = list(augmented.get("manual_review", {}).get("reasons") or [])
    reasons.extend(_manual_review_reason(warning) for warning in capture_warnings)
    reasons.extend(_manual_review_reason(failure, "blocking" if captured_source_count == 0 else "warning") for failure in capture_failures)
    blockers = list(dict.fromkeys(list(augmented.get("completion_blockers") or []) + errors))

    augmented.update(
        {
            "status": status,
            "errors": errors,
            "warnings": warnings,
            "requires_manual_review": manual_review or bool(errors),
            "run_status": run_status,
            "validation_status": "passed" if status == "pass" else "failed",
            "manual_review": {
                "required": manual_review or bool(errors),
                "severity": "blocking" if status == "fail" else "warning" if manual_review else "info",
                "reasons": reasons,
            },
            "completion_blockers": blockers,
        }
    )
    return augmented


def _build_augmented_manifest(
    base_manifest: dict[str, Any],
    *,
    input_record: dict[str, Any],
    capture_evidence: list[dict[str, Any]],
    screenshot_evidence: list[dict[str, Any]],
    validation_report: dict[str, Any],
    warnings: list[str],
) -> dict[str, Any]:
    manifest = dict(base_manifest)
    evidence = list(manifest.get("evidence") or [])
    seen_paths = {item.get("path") for item in evidence if isinstance(item, dict)}
    for item in capture_evidence + screenshot_evidence:
        if item["path"] not in seen_paths:
            evidence.append(item)
            seen_paths.add(item["path"])
    manifest["inputs"] = input_record
    manifest["evidence"] = evidence
    manifest["warnings"] = list(dict.fromkeys(list(manifest.get("warnings") or []) + warnings + list(validation_report.get("warnings") or [])))
    manifest["requires_manual_review"] = bool(validation_report.get("requires_manual_review"))
    manifest["run_status"] = validation_report.get("run_status", manifest.get("run_status"))
    manifest["validation_status"] = validation_report.get("validation_status", manifest.get("validation_status"))
    manifest["manual_review"] = validation_report.get("manual_review", manifest.get("manual_review"))
    manifest["completion_blockers"] = validation_report.get("completion_blockers", manifest.get("completion_blockers", []))
    manifest["validation"] = {
        **(manifest.get("validation") or {}),
        "schema_valid": validation_report.get("status") == "pass",
        "warnings": len(validation_report.get("warnings", [])),
        "requires_manual_review": bool(validation_report.get("requires_manual_review")),
        "report_path": "validation/claim-coverage-report.json",
        "missing_sources_path": "validation/missing-sources.md",
    }
    manifest["finished_at"] = utc_now()
    return manifest


def run(args: argparse.Namespace) -> Path:
    started_at = utc_now()
    run_id = validate_run_id(args.run_id or f"{_slug_timestamp(started_at)}-research-capture")
    output_root = Path(args.output_root or "browser-operator-runs").resolve()
    expected_run_dir = resolve_run_relative(output_root, run_id)
    continue_existing = bool(getattr(args, "continue_existing_run", False))
    defer_manifest = bool(getattr(args, "defer_manifest", False))
    if continue_existing and not defer_manifest:
        raise SystemExit("authenticated continuation requires --defer-manifest")
    if defer_manifest and not continue_existing:
        raise SystemExit("deferred research-capture manifest requires authenticated continuation")
    input_path = Path(args.input).resolve() if args.input else None
    input_bytes = input_path.read_bytes() if input_path is not None else None
    spec = _load_spec(args, input_bytes=input_bytes)
    question = str(spec.get("question") or "").strip()
    if not question:
        raise SystemExit("M8 requires a research question")
    topic = str(spec.get("topic") or question)
    sources = [source for source in _as_list(spec.get("sources")) if isinstance(source, dict)]
    _validate_source_scope(sources, min_sources=args.min_sources, max_sources=args.max_sources)
    for index, source in enumerate(sources, start=1):
        _preflight_source_input(source, index)
    if continue_existing and (
        input_path is None
        or input_path != (expected_run_dir / "capture" / "discovery-selected-sources.json").resolve()
    ):
        raise SystemExit("continued research capture must consume capture/discovery-selected-sources.json")
    run_dir = prepare_run_dir(
        output_root,
        run_id,
        continue_existing=continue_existing,
        continuation_required_paths=("capture/discovery-selected-sources.json",) if continue_existing else (),
        continuation_token=getattr(args, "continuation_token", None),
        continuation_stage="research-capture" if continue_existing else None,
        continuation_input_path="capture/discovery-selected-sources.json" if continue_existing else None,
        continuation_artifact_sha256=(
            {"capture/discovery-selected-sources.json": _sha256_bytes(input_bytes)}
            if continue_existing and input_bytes is not None
            else None
        ),
    )
    (run_dir / "capture").mkdir(parents=True, exist_ok=True)
    (run_dir / "evidence").mkdir(parents=True, exist_ok=True)
    (run_dir / "validation").mkdir(parents=True, exist_ok=True)

    adapter_stage_root = run_dir / "capture" / "_adapter-stage"
    source_summaries: list[dict[str, Any]] = []
    capture_evidence: list[dict[str, Any]] = []
    screenshot_evidence: list[dict[str, Any]] = []
    capture_warnings: list[str] = []
    capture_failures: list[str] = []
    admissible_source_count = 0

    try:
        for index, source in enumerate(sources[: args.max_sources], start=1):
            source_id = validate_source_id(str(source.get("source_id") or f"S{index:03d}"))
            source_dir = run_dir / "capture" / source_dir_name(source_id)
            source_dir.mkdir(parents=True, exist_ok=True)
            adapter_input_dir = adapter_stage_root / "_inputs" / source_dir_name(source_id)
            command = _capture_command(
                source=source,
                source_index=index,
                adapter_output_root=adapter_stage_root,
                final_source_dir=adapter_input_dir,
            )
            completed = subprocess.run(command, cwd=Path(__file__).resolve().parents[1], text=True, capture_output=True)
            adapter_run_dir = adapter_stage_root / f"source-{index:03d}"
            adapter_capture_path = adapter_run_dir / "capture" / "page_capture.json"
            adapter_report_path = adapter_run_dir / "validation" / "capture-validation-report.json"
            final_capture_path = source_dir / "page_capture.json"
            final_report_path = source_dir / "capture-validation-report.json"
            capture = _read_json_if_exists(adapter_capture_path)
            capture_report = _read_json_if_exists(adapter_report_path)
            adapter_manifest = _read_json_if_exists(adapter_run_dir / "validation" / "capture-stage-manifest.json")
            source_warnings: list[str] = []
            admissibility_errors = capture_admissibility_errors(
                capture=capture,
                report=capture_report,
                manifest=adapter_manifest,
                returncode=completed.returncode,
                run_dir=adapter_run_dir,
                expected_run_id=f"source-{index:03d}",
            )
            admissible_capture = capture if not admissibility_errors else None
            admissible_report = capture_report if admissible_capture is not None else None
            if admissible_capture is not None:
                admissible_source_count += 1
                write_json(final_capture_path, admissible_capture)
                capture_evidence.append(
                    {
                        "id": f"C{index:03d}",
                        "type": "page_capture",
                        "path": final_capture_path.relative_to(run_dir).as_posix(),
                        "url": admissible_capture.get("source", {}).get("url"),
                        "captured_at": admissible_capture.get("captured_at"),
                    }
                )
                staged_screenshots = _stage_source_screenshots(
                    capture=admissible_capture,
                    capture_path=adapter_capture_path,
                    run_dir=run_dir,
                    source_id=source_id,
                    warnings=source_warnings,
                )
                for screenshot_index, screenshot in enumerate(staged_screenshots, start=1):
                    screenshot_evidence.append(
                        {
                            "id": f"SS{index:03d}-{screenshot_index:03d}",
                            "type": "screenshot",
                            "path": screenshot["path"],
                            "captured_at": screenshot.get("captured_at"),
                            "sha256": screenshot.get("sha256"),
                        }
                    )
            else:
                staged_screenshots = []
            if admissibility_errors:
                staged_screenshots = []
                generic_failure = f"{source_id}:capture_failed"
                capture_failures.append(generic_failure)
                source_warnings.append(generic_failure)
                for error in admissibility_errors:
                    failure_code = f"{source_id}:{error}"
                    capture_failures.append(failure_code)
                    source_warnings.append(failure_code)
            if admissible_report is not None:
                write_json(final_report_path, admissible_report)
            capture_warnings.extend(source_warnings)
            source_summaries.append(
                _source_summary_from_capture(
                    source=source,
                    source_id=source_id,
                    capture=admissible_capture,
                    capture_report=admissible_report,
                    staged_screenshots=staged_screenshots,
                    source_warnings=source_warnings,
                    accessed_at=started_at,
                )
            )
    finally:
        if adapter_stage_root.exists():
            shutil.rmtree(adapter_stage_root)

    claims = [claim for claim in _as_list(spec.get("claims")) if isinstance(claim, dict)]
    unknowns = [unknown for unknown in _as_list(spec.get("unknowns")) if isinstance(unknown, dict)]
    warnings = list(dict.fromkeys(_strings(spec.get("warnings")) + capture_warnings))
    if not claims and not unknowns:
        unknowns = [_fallback_unknown_claim(question, source_summaries)]
        warnings.append("claim_ledger_missing_no_synthesis_performed")

    research_input = {
        "schema_version": "1.0",
        "topic": topic,
        "question": question,
        "summary": spec.get("summary"),
        "sources": source_summaries,
        "claims": claims,
        "unknowns": unknowns,
        "warnings": list(dict.fromkeys(warnings)),
    }
    research_input_path = run_dir / "capture" / "research-input.json"
    write_json(research_input_path, research_input)
    input_record = {
        "input_path": str(args.input) if args.input else None,
        "generated_research_input": "capture/research-input.json",
        "topic": topic,
        "question": question,
        "approved_source_urls": [source.get("url") for source in sources],
        "source_count": len(sources),
        "captured_source_count": admissible_source_count,
        "max_sources": args.max_sources,
        "workflow": "browser-research",
        "capture_stage": "provided_url_browser_capture",
    }
    write_json(run_dir / "input.json", input_record)
    continuation_token = create_continuation_handoff(
        run_dir,
        run_id=run_id,
        from_stage="research-capture",
        to_stage="browser-research-render",
        input_path="capture/research-input.json",
        artifact_sha256={
            "capture/research-input.json": _sha256_file(research_input_path),
        },
    )

    runner_command = [
        sys.executable,
        str(SCRIPT_ROOT / "browser_research_runner.py"),
        "--input",
        str(research_input_path),
        "--output-root",
        str(output_root),
        "--run-id",
        run_id,
        "--continue-existing-run",
        f"--continuation-token={continuation_token}",
        "--defer-manifest",
    ]
    completed_runner = subprocess.run(runner_command, cwd=Path(__file__).resolve().parents[1], text=True, capture_output=True)
    if completed_runner.returncode != 0:
        failure_code = f"browser_research_renderer_failed:{completed_runner.returncode}"
        blockers = [failure_code]
        failed_report = {
            "schema_version": "1.0",
            "status": "fail",
            "errors": blockers,
            "warnings": list(dict.fromkeys(warnings + blockers)),
            "requires_manual_review": True,
            "run_status": "failed",
            "validation_status": "failed",
            "manual_review": {
                "required": True,
                "severity": "blocking",
                "reasons": [_manual_review_reason(failure_code, "blocking")],
            },
            "completion_blockers": blockers,
            "screenshot_policy": {"required": False, "reason": "per_source_policy", "status": "capture_failed"},
        }
        write_json(run_dir / "validation" / "claim-coverage-report.json", failed_report)
        write_text(run_dir / "validation" / "missing-sources.md", "# Missing Sources\n\nResearch rendering failed.\n")
        _write_warnings(run_dir / "validation" / "warnings.md", failed_report["warnings"])
        manifest_output = RESEARCH_CAPTURE_STAGE_MANIFEST if defer_manifest else "manifest.json"
        write_json(
            resolve_run_relative(run_dir, manifest_output),
            {
                "run_id": run_id,
                "task": "browser-research",
                "started_at": started_at,
                "finished_at": utc_now(),
                "operator": "codex",
                "skill": "browser-research",
                "inputs": input_record,
                "artifacts": [],
                "evidence": capture_evidence
                + screenshot_evidence
                + [{"id": "RI001", "type": "research_input", "path": "capture/research-input.json"}],
                "validation": {
                    "schema_valid": False,
                    "warnings": len(failed_report["warnings"]),
                    "requires_manual_review": True,
                    "report_path": "validation/claim-coverage-report.json",
                    "missing_sources_path": "validation/missing-sources.md",
                },
                "warnings": failed_report["warnings"],
                "requires_manual_review": True,
                "run_status": "failed",
                "validation_status": "failed",
                "manual_review": failed_report["manual_review"],
                "completion_blockers": blockers,
                "screenshot_policy": failed_report["screenshot_policy"],
            },
        )
        raise SystemExit(completed_runner.stderr.strip() or "browser_research_runner.py failed")
    validation_path = run_dir / "validation" / "claim-coverage-report.json"
    stage_manifest_path = resolve_run_relative(run_dir, RESEARCH_RENDER_STAGE_MANIFEST, must_exist=True)
    base_manifest = read_json(stage_manifest_path)
    augmented_report = _augment_validation_report(
        read_json(validation_path),
        capture_warnings=list(dict.fromkeys(capture_warnings)),
        capture_failures=list(dict.fromkeys(capture_failures)),
        captured_source_count=admissible_source_count,
    )
    final_manifest: dict[str, Any] | None = None
    for _ in range(4):
        candidate_manifest = _build_augmented_manifest(
            base_manifest,
            input_record=input_record,
            capture_evidence=capture_evidence
            + [{"id": "RI001", "type": "research_input", "path": "capture/research-input.json"}],
            screenshot_evidence=screenshot_evidence,
            validation_report=augmented_report,
            warnings=list(dict.fromkeys(warnings)),
        )
        checked_report = _augment_validation_report(
            validate_browser_research_run(run_dir, manifest_override=candidate_manifest),
            capture_warnings=list(dict.fromkeys(capture_warnings)),
            capture_failures=list(dict.fromkeys(capture_failures)),
            captured_source_count=admissible_source_count,
        )
        if checked_report == augmented_report:
            final_manifest = candidate_manifest
            break
        augmented_report = checked_report
    if final_manifest is None:
        raise RuntimeError("research-capture manifest validation did not converge")
    write_json(validation_path, augmented_report)
    _write_warnings(
        run_dir / "validation" / "warnings.md",
        list(dict.fromkeys(warnings + augmented_report.get("warnings", []))),
    )
    manifest_output = RESEARCH_CAPTURE_STAGE_MANIFEST if defer_manifest else "manifest.json"
    manifest_output_path = resolve_run_relative(run_dir, manifest_output)
    write_json(manifest_output_path, final_manifest)
    if stage_manifest_path != manifest_output_path:
        stage_manifest_path.unlink()
    print(run_dir)
    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Capture user-approved provided URLs, build browser-research input, run existing research pipeline."
    )
    parser.add_argument("--input", help="M8 research capture JSON spec.")
    parser.add_argument("--question", help="Research question.")
    parser.add_argument("--topic", help="Report topic.")
    parser.add_argument("--url", action="append", default=[], help="Approved source URL. May be repeated.")
    parser.add_argument("--claims-file", help="Optional claim ledger JSON with claims/unknowns/summary.")
    parser.add_argument("--output-root", default="browser-operator-runs")
    parser.add_argument("--run-id")
    parser.add_argument("--max-sources", type=int, default=10)
    parser.add_argument("--min-sources", type=int, default=2)
    parser.add_argument("--continue-existing-run", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--continuation-token", help=argparse.SUPPRESS)
    parser.add_argument("--defer-manifest", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
