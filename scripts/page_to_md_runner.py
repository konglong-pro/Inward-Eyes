from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from inward_eyes.html_extract import extract_html
from inward_eyes.io import read_json, relative_to, utc_now, write_bytes, write_json, write_text
from inward_eyes.capture import read_capture_admission_bundle, screenshot_file_is_valid
from inward_eyes.markdown import render_page_markdown
from inward_eyes.paths import prepare_run_dir, validate_run_id
from inward_eyes.validation import validate_page_to_md_run

SCREENSHOT_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
SCREENSHOT_REQUIRED_PAGE_TYPES = {"x_thread", "forum_thread", "product_page"}
SCREENSHOT_REQUIRED_WARNINGS = {
    "dynamic_page",
    "ambiguous_extraction",
    "personal_context",
    "private_data_warning",
    "thread_page",
    "forum_thread",
    "ecommerce_page",
}


def _slug_timestamp(timestamp: str) -> str:
    return re.sub(r"[^0-9TZ]", "", timestamp).replace("Z", "Z")


def classify_page_type(source_url: str, ast: dict[str, Any], explicit: str | None = None) -> str:
    if explicit and explicit != "auto":
        return explicit
    url = source_url.lower()
    text = " ".join(str(block.get("text", "")) for block in ast_blocks(ast)).lower()
    if "x.com/" in url or "twitter.com/" in url:
        return "x_thread"
    if "forum" in url or "thread" in url or "reply" in text:
        return "forum_thread"
    if "add to cart" in text or "buy now" in text or "shipping" in text:
        return "product_page"
    if "/docs/" in url or "documentation" in text:
        return "docs"
    return "article"


def _confidence_field(value: str | None, confidence: float, evidence: str) -> dict[str, Any]:
    return {"value": value, "confidence": confidence if value else 0, "evidence": evidence if value else "not_found"}


def ast_blocks(ast: dict[str, Any]) -> list[dict[str, Any]]:
    document = ast.get("document")
    if isinstance(document, dict):
        blocks = document.get("blocks")
        if isinstance(blocks, list):
            return blocks
    blocks = ast.get("blocks")
    return blocks if isinstance(blocks, list) else []


def ast_title(ast: dict[str, Any]) -> str | None:
    document = ast.get("document")
    if isinstance(document, dict):
        title = document.get("title")
        if isinstance(title, dict):
            return title.get("value")
        if isinstance(title, str):
            return title
    title = ast.get("title")
    return title if isinstance(title, str) else None


def is_page_capture(data: Any) -> bool:
    return (
        isinstance(data, dict)
        and isinstance(data.get("source"), dict)
        and isinstance(data.get("content"), dict)
        and "capture_id" in data
    )


def _capture_contains_private_data(capture: dict[str, Any]) -> bool:
    privacy = capture.get("privacy") if isinstance(capture.get("privacy"), dict) else {}
    return bool(
        capture.get("contains_private_data")
        or privacy.get("contains_private_data")
        or privacy.get("private_data_detected")
    )


def _screenshot_required_reasons(capture: dict[str, Any], page_type: str, requires_login: bool) -> list[str]:
    source = capture.get("source") if isinstance(capture.get("source"), dict) else {}
    browser_context = capture.get("browser_context") if isinstance(capture.get("browser_context"), dict) else {}
    warnings = set(capture.get("warnings") or [])
    reasons: list[str] = []
    if requires_login or source.get("requires_login") or browser_context.get("login_state") in {"confirmed", "suspected"}:
        reasons.append("logged_in_page")
    if _capture_contains_private_data(capture):
        reasons.append("private_data")
    if page_type in SCREENSHOT_REQUIRED_PAGE_TYPES:
        reasons.append(page_type)
    for warning in sorted(warnings.intersection(SCREENSHOT_REQUIRED_WARNINGS)):
        reasons.append(warning)
    return list(dict.fromkeys(reasons))


def screenshot_policy_for(
    capture: dict[str, Any],
    page_type: str,
    requires_login: bool,
) -> dict[str, Any]:
    assets = capture.get("assets") if isinstance(capture.get("assets"), dict) else {}
    raw_screenshots = assets.get("screenshots") if isinstance(assets.get("screenshots"), list) else []
    required_reasons = _screenshot_required_reasons(capture, page_type, requires_login)
    existing = capture.get("screenshot_policy")
    if isinstance(existing, dict):
        required = bool(existing.get("required")) or bool(required_reasons)
        status = str(existing.get("status") or ("required_but_missing" if required else "not_required"))
        reason = str(existing.get("reason") or "capture_policy")
        if required_reasons and not existing.get("required"):
            reason = "+".join(required_reasons)
            status = "required_and_present" if raw_screenshots else "required_but_missing"
        return {
            "required": required,
            "reason": reason,
            "status": status,
        }
    if required_reasons:
        return {
            "required": True,
            "reason": "+".join(required_reasons),
            "status": "required_and_present" if raw_screenshots else "required_but_missing",
        }
    return {"required": False, "reason": "static_public_article", "status": "not_required"}


def _safe_asset_name(raw_name: str, index: int) -> str:
    path = Path(raw_name)
    suffix = path.suffix.lower()
    if suffix not in SCREENSHOT_EXTENSIONS:
        suffix = ".png"
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", path.stem).strip(".-") or f"screenshot-{index:03d}"
    return f"{index:03d}-{stem}{suffix}"


def _capture_asset_roots(input_path: Path) -> list[Path]:
    roots = [input_path.parent]
    if input_path.parent.name == "capture":
        roots.append(input_path.parent.parent)
    return list(dict.fromkeys(root.resolve() for root in roots))


def _resolve_capture_asset(raw_path: str, input_path: Path) -> Path | None:
    if (
        not raw_path
        or "\\" in raw_path
        or ":" in raw_path
        or raw_path.startswith("/")
        or any(part in {"", ".", ".."} for part in raw_path.split("/"))
    ):
        return None
    path = Path(*raw_path.split("/"))
    for root in _capture_asset_roots(input_path):
        candidate = (root / path).resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            continue
        if candidate.is_file():
            return candidate
    return None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def stage_capture_screenshots(
    capture: dict[str, Any] | None,
    input_path: Path,
    run_dir: Path,
    accessed_at: str,
    warnings: list[str],
) -> list[dict[str, Any]]:
    if not capture:
        return []
    assets = capture.get("assets") if isinstance(capture.get("assets"), dict) else {}
    raw_screenshots = assets.get("screenshots") if isinstance(assets.get("screenshots"), list) else []
    staged: list[dict[str, Any]] = []
    for index, item in enumerate(raw_screenshots, start=1):
        if isinstance(item, str):
            raw_path = item
            captured_at = accessed_at
        elif isinstance(item, dict):
            raw_path = str(item.get("path") or "")
            captured_at = str(item.get("captured_at") or accessed_at)
        else:
            warnings.append(f"screenshot_asset_invalid:{index}")
            continue
        source_path = _resolve_capture_asset(raw_path, input_path)
        if source_path is None:
            warnings.append(f"screenshot_asset_missing:{raw_path}")
            continue
        if not screenshot_file_is_valid(source_path):
            warnings.append(f"screenshot_asset_missing_or_invalid:{raw_path}")
            continue
        destination = run_dir / "evidence" / "screenshots" / _safe_asset_name(raw_path, index)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source_path.resolve() != destination.resolve():
            write_bytes(destination, source_path.read_bytes())
        if not screenshot_file_is_valid(destination):
            destination.unlink(missing_ok=True)
            warnings.append(f"screenshot_asset_copy_invalid:{raw_path}")
            continue
        staged.append(
            {
                "type": "screenshot",
                "path": relative_to(destination, run_dir),
                "captured_at": captured_at,
                "source_path": raw_path,
                "sha256": _sha256_file(destination),
            }
        )
    return staged


def text_to_capture(text: str, source: dict[str, Any]) -> dict[str, Any]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    title = source.get("page_title") or (paragraphs[0] if paragraphs else None)
    blocks: list[dict[str, Any]] = []
    if title:
        blocks.append({"type": "heading", "level": 1, "text": title, "source_ref": "capture:selected_main_content:title"})
    for index, paragraph in enumerate(paragraphs[1:] if paragraphs and paragraphs[0] == title else paragraphs, start=1):
        blocks.append({"type": "paragraph", "text": paragraph, "source_ref": f"capture:selected_main_content:p{index}"})
    warnings = [] if len(blocks) > 1 else ["main_content_not_found"]
    return {
        "source": source,
        "document": {
            "title": _confidence_field(title, 0.7 if title else 0, "selected_main_content"),
            "author": _confidence_field(None, 0, "not_found"),
            "published_at": _confidence_field(None, 0, "not_found"),
            "language": None,
        },
        "document_ast": {
            "schema_version": "1.0",
            "document": {
                "title": _confidence_field(title, 0.7 if title else 0, "selected_main_content"),
                "blocks": blocks,
            },
            "warnings": warnings,
        },
        "warnings": warnings,
    }


def normalize_page_capture(raw_capture: dict[str, Any], source_url: str) -> dict[str, Any]:
    source = raw_capture.get("source", {})
    content = raw_capture.get("content", {})
    capture = dict(raw_capture)
    raw_warnings = list(raw_capture.get("warnings") or [])
    if "document_ast" not in capture and isinstance(content, dict) and content.get("html"):
        extracted = extract_html(str(content["html"]), source.get("url") or source_url)
        extracted["source"].update({key: value for key, value in source.items() if value is not None})
        capture.update(extracted)
        capture["warnings"] = list(dict.fromkeys(raw_warnings + (extracted.get("warnings") or [])))
    elif "document_ast" not in capture and isinstance(content, dict):
        text_content = content.get("selected_main_content") or content.get("text")
        if text_content:
            extracted = text_to_capture(str(text_content), source)
            capture.update(extracted)
            capture["warnings"] = list(dict.fromkeys(raw_warnings + (extracted.get("warnings") or [])))
    return capture


def normalize_capture(
    capture: dict[str, Any],
    source_url: str,
    page_type: str,
    requires_login: bool,
    accessed_at: str,
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    source = capture.get("source", {})
    document = capture.get("document", {})
    ast = capture.get("document_ast", {"schema_version": "1.0", "title": None, "blocks": [], "warnings": []})
    raw_ast_warnings = ast.get("warnings") or []
    warnings = list(dict.fromkeys((capture.get("warnings") or []) + raw_ast_warnings))

    title_field = document.get("title")
    if not isinstance(title_field, dict):
        title_value = ast_title(ast) or source.get("page_title")
        title_field = _confidence_field(title_value, 0.95 if title_value else 0, "capture_or_ast")
    author_field = document.get("author")
    if not isinstance(author_field, dict):
        author_field = _confidence_field(document.get("author"), 0.8 if document.get("author") else 0, "capture_author")
    published_field = document.get("published_at")
    if not isinstance(published_field, dict):
        published_field = _confidence_field(document.get("published_at"), 0.8 if document.get("published_at") else 0, "capture_published_at")

    if not title_field.get("value") and "title_not_found" not in warnings:
        warnings.append("title_not_found")
    if not author_field.get("value") and "author_not_found" not in warnings:
        warnings.append("author_not_found")
    if not published_field.get("value") and "published_at_not_found" not in warnings:
        warnings.append("published_at_not_found")
    if not source.get("canonical_url") and "canonical_url_not_found" not in warnings:
        warnings.append("canonical_url_not_found")

    effective_requires_login = bool(requires_login or source.get("requires_login"))
    screenshot_policy = screenshot_policy_for(capture, page_type, effective_requires_login)
    if screenshot_policy["status"] == "required_but_missing" and "screenshot_required_but_missing" not in warnings:
        warnings.append("screenshot_required_but_missing")
    capture_privacy = capture.get("privacy") if isinstance(capture.get("privacy"), dict) else {}
    contains_private_data = _capture_contains_private_data(capture)
    redaction_notes = capture.get("redaction_notes") or capture_privacy.get("redaction_notes") or []
    redaction_applied = bool(capture.get("redaction_applied") or capture_privacy.get("redaction_applied"))
    if contains_private_data and "private_data_warning" not in warnings and "private_data_redacted" not in warnings:
        warnings.append("private_data_warning")

    metadata = {
        "schema_version": "1.0",
        "task_type": "page-to-md",
        "source": {
            "url": source.get("url") or source_url,
            "canonical_url": source.get("canonical_url"),
            "page_title": source.get("page_title"),
            "site_name": source.get("site_name"),
            "accessed_at": accessed_at,
            "requires_login": effective_requires_login,
            "login_state": (capture.get("login_state") or capture.get("browser_context", {}).get("login_state"))
            if isinstance(capture.get("browser_context"), dict)
            else capture.get("login_state"),
        },
        "document": {
            "title": title_field,
            "author": author_field,
            "published_at": published_field,
            "language": document.get("language"),
            "page_type": page_type,
        },
        "extraction": {
            "method": capture.get("capture_method") or "local_html_structured_extraction",
            "tool_chain": ["local_html_parser", "document_ast", "markdown_renderer"],
            "excluded_blocks": ["navigation", "footer", "recommendations", "ads", "cookie_banners"],
            "warnings": warnings,
            "screenshot_policy": screenshot_policy,
        },
        "assets": [],
        "privacy": {
            "contains_private_data": contains_private_data,
            "redaction_applied": redaction_applied,
            "redaction_notes": redaction_notes if isinstance(redaction_notes, list) else [],
        },
    }
    normalized_ast = {
        "schema_version": ast.get("schema_version") or "1.0",
        "document": {
            "title": title_field,
            "blocks": ast_blocks(ast),
        },
        "warnings": warnings,
    }
    return metadata, normalized_ast, warnings


def build_source_record(metadata: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    source = metadata["source"]
    extraction = metadata["extraction"]
    page_type = metadata["document"]["page_type"]
    screenshot_assets = [asset for asset in metadata.get("assets", []) if asset.get("type") == "screenshot"]
    screenshot_path = screenshot_assets[0]["path"] if screenshot_assets else None
    return {
        "source_id": "S001",
        "url": source["url"],
        "canonical_url": source.get("canonical_url"),
        "title": source.get("page_title") or metadata["document"]["title"].get("value"),
        "site_name": source.get("site_name"),
        "page_type": page_type,
        "accessed_at": source["accessed_at"],
        "requires_login": source["requires_login"],
        "capture_method": extraction["method"],
        "evidence": {
            "screenshot": screenshot_path,
            "snapshot": None,
            "source_record": "evidence/source_record.json",
        },
        "screenshot_policy": metadata["extraction"]["screenshot_policy"],
        "content_scope": {
            "included": ["main_content"],
            "excluded": extraction["excluded_blocks"],
        },
        "warnings": extraction["warnings"],
    }


def write_warnings(path: Path, warnings: list[str]) -> None:
    if not warnings:
        write_text(path, "No warnings.\n")
        return
    lines = ["# Warnings", ""]
    lines.extend(f"- {warning}" for warning in warnings)
    write_text(path, "\n".join(lines) + "\n")


def create_manifest(
    run_dir: Path,
    run_id: str,
    started_at: str,
    finished_at: str,
    input_record: dict[str, Any],
    validation_report: dict[str, Any],
    warnings: list[str],
    capture_path: str | None = None,
    evidence_assets: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    validation = validation_report
    report_path = "validation/validation-report.json"
    evidence = []
    if capture_path:
        evidence.append({"id": "C001", "type": "page_capture", "path": capture_path})
    evidence.append({"id": "E001", "type": "source_record", "path": "evidence/source_record.json"})
    for index, asset in enumerate(evidence_assets or [], start=1):
        evidence.append(
            {
                "id": f"S{index:03d}",
                "type": asset.get("type", "screenshot"),
                "path": asset["path"],
                "captured_at": asset.get("captured_at"),
                **({"sha256": asset["sha256"]} if asset.get("sha256") else {}),
            }
        )
    evidence.append({"id": "V001", "type": "validation_report", "path": "validation/validation-report.json"})

    return {
        "run_id": run_id,
        "task": "page-to-md",
        "started_at": started_at,
        "finished_at": finished_at,
        "operator": "codex",
        "skill": "page-to-md",
        "inputs": input_record,
        "artifacts": [
            {"id": "A001", "type": "markdown", "path": "artifacts/page.md"},
            {"id": "A002", "type": "metadata", "path": "artifacts/metadata.json"},
            {"id": "A003", "type": "document_ast", "path": "artifacts/document_ast.json"},
        ],
        "evidence": evidence,
        "validation": {
            "schema_valid": validation.get("status") == "pass",
            "warnings": len(validation.get("warnings", [])),
            "requires_manual_review": bool(validation.get("requires_manual_review")),
            "report_path": report_path,
        },
        "warnings": warnings,
        "requires_manual_review": bool(validation.get("requires_manual_review")),
        "run_status": validation.get("run_status", "failed" if validation.get("status") == "fail" else "partial" if validation.get("requires_manual_review") else "complete"),
        "validation_status": validation.get("validation_status")
        if validation.get("validation_status") in {"passed", "failed"}
        else "failed",
        "manual_review": validation.get(
            "manual_review",
            {"required": bool(validation.get("requires_manual_review")), "severity": "warning" if validation.get("requires_manual_review") else "info", "reasons": []},
        ),
        "completion_blockers": validation.get("completion_blockers", []),
        "screenshot_policy": validation.get("screenshot_policy", input_record.get("screenshot_policy", {"required": False, "reason": "unknown", "status": "not_required"})),
    }


def run(args: argparse.Namespace) -> Path:
    input_path = Path(args.input).resolve()
    if not input_path.exists():
        raise SystemExit(f"input does not exist: {input_path}")

    started_at = utc_now()
    run_id = args.run_id or f"{_slug_timestamp(started_at)}-page-to-md"
    output_root = Path(args.output_root or "browser-operator-runs").resolve()
    continue_existing = bool(getattr(args, "continue_existing_run", False))
    continuation_artifact_sha256: dict[str, str] | None = None
    if continue_existing:
        run_id = validate_run_id(run_id)
        expected_input_path = (output_root / run_id / "capture" / "page_capture.json").resolve()
        if input_path != expected_input_path:
            raise SystemExit("continued page-to-md run must consume capture/page_capture.json from that run")

    raw_json: dict[str, Any] | None = None
    html_input: str | None = None
    if continue_existing:
        raw_json, _, _, continuation_artifact_sha256, admission_errors = read_capture_admission_bundle(
            output_root / run_id,
            expected_run_id=run_id,
            returncode=0,
        )
        if admission_errors:
            raise SystemExit(
                "continued capture admission failed: " + ", ".join(admission_errors)
            )
        if raw_json is None:
            raise SystemExit("continued capture admission did not return page_capture.json")
    elif input_path.suffix.lower() == ".json":
        loaded_json = read_json(input_path)
        if not isinstance(loaded_json, dict):
            raise SystemExit("JSON input must be an object")
        raw_json = loaded_json
    else:
        html_input = input_path.read_text(encoding=args.encoding)

    capture_input = raw_json if is_page_capture(raw_json) else None
    capture_source_url = None
    if capture_input:
        capture_source = capture_input.get("source", {})
        if isinstance(capture_source, dict):
            capture_source_url = capture_source.get("url")

    source_url = args.url or capture_source_url or input_path.as_uri()
    input_record = {
        "input_path": str(input_path),
        "source_url": source_url,
        "page_type": args.page_type,
        "requires_login": args.requires_login,
    }

    capture_path: str | None = None
    if raw_json is not None:
        if capture_input:
            capture_path = "capture/page_capture.json"
            input_record["capture_path"] = capture_path
        capture = normalize_page_capture(raw_json, source_url)
    else:
        capture = extract_html(html_input or "", source_url)

    ast_for_classification = capture.get("document_ast", {})
    page_type = classify_page_type(source_url, ast_for_classification, args.page_type)
    accessed_at = capture.get("captured_at") if capture_input and isinstance(capture.get("captured_at"), str) else started_at
    metadata, ast, warnings = normalize_capture(capture, source_url, page_type, args.requires_login, accessed_at)
    input_record["screenshot_policy"] = metadata["extraction"]["screenshot_policy"]

    run_dir = prepare_run_dir(
        output_root,
        run_id,
        continue_existing=continue_existing,
        continuation_required_paths=("capture/page_capture.json",) if continue_existing else (),
        continuation_manifest_tasks=("capture-adapter",) if continue_existing else (),
        continuation_manifest_path="validation/capture-stage-manifest.json",
        continuation_token=getattr(args, "continuation_token", None),
        continuation_stage="page-to-md-render" if continue_existing else None,
        continuation_input_path="capture/page_capture.json" if continue_existing else None,
        continuation_artifact_sha256=continuation_artifact_sha256,
    )
    (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    (run_dir / "evidence").mkdir(parents=True, exist_ok=True)
    (run_dir / "validation").mkdir(parents=True, exist_ok=True)
    write_json(run_dir / "input.json", input_record)
    if capture_path and capture_input:
        write_json(run_dir / capture_path, capture_input)

    staged_screenshots = stage_capture_screenshots(capture_input, input_path, run_dir, started_at, warnings)
    metadata["assets"] = staged_screenshots
    metadata["extraction"]["warnings"] = list(dict.fromkeys(warnings))
    ast["warnings"] = list(dict.fromkeys(warnings))

    source_record = build_source_record(metadata, run_dir)

    write_json(run_dir / "artifacts" / "metadata.json", metadata)
    write_json(run_dir / "artifacts" / "document_ast.json", ast)
    write_json(run_dir / "evidence" / "source_record.json", source_record)
    markdown = render_page_markdown(metadata, ast)
    write_text(run_dir / "artifacts" / "page.md", markdown)
    write_warnings(run_dir / "validation" / "warnings.md", warnings)

    final_validation_report = validate_page_to_md_run(
        run_dir,
        manifest_override={},
        skip_manifest_validation=True,
    )
    final_manifest: dict[str, Any] | None = None
    for _ in range(4):
        candidate_manifest = create_manifest(
            run_dir,
            run_id,
            started_at,
            utc_now(),
            input_record,
            final_validation_report,
            warnings,
            capture_path,
            staged_screenshots,
        )
        checked_report = validate_page_to_md_run(
            run_dir,
            manifest_override=candidate_manifest,
            pending_manifest_paths={"validation/validation-report.json"},
        )
        if checked_report == final_validation_report:
            final_manifest = candidate_manifest
            break
        final_validation_report = checked_report
    if final_manifest is None:
        raise RuntimeError("page-to-md manifest validation did not converge")
    write_json(run_dir / "validation" / "validation-report.json", final_validation_report)
    write_json(run_dir / "manifest.json", final_manifest)
    if continue_existing:
        (run_dir / "validation" / "capture-stage-manifest.json").unlink(missing_ok=True)
    print(run_dir)
    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert local HTML or page capture JSON to evidence-backed Markdown.")
    parser.add_argument("--input", required=True, help="Local HTML or page capture JSON path.")
    parser.add_argument("--url", help="Source URL to record in metadata.")
    parser.add_argument("--output-root", default="browser-operator-runs", help="Directory where run outputs are written.")
    parser.add_argument("--run-id", help="Optional run id.")
    parser.add_argument("--page-type", default="auto", choices=["auto", "article", "blog", "docs", "x_thread", "forum_thread", "product_page", "unknown"])
    parser.add_argument("--requires-login", action="store_true", help="Mark the page as requiring login.")
    parser.add_argument("--encoding", default="utf-8", help="Input file encoding.")
    parser.add_argument(
        "--continue-existing-run",
        action="store_true",
        help="Continue an adapter-created page-to-md run after validating its manifest and capture path.",
    )
    parser.add_argument("--continuation-token", help=argparse.SUPPRESS)
    args = parser.parse_args()
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
