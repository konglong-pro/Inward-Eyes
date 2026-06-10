from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from inward_eyes.html_extract import extract_html
from inward_eyes.io import read_json, relative_to, utc_now, write_json, write_text
from inward_eyes.markdown import render_page_markdown
from inward_eyes.validation import validate_page_to_md_run


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


def screenshot_policy_for(
    capture: dict[str, Any],
    page_type: str,
    requires_login: bool,
) -> dict[str, Any]:
    existing = capture.get("screenshot_policy")
    if isinstance(existing, dict):
        return {
            "required": bool(existing.get("required")),
            "reason": str(existing.get("reason") or "capture_policy"),
            "status": str(existing.get("status") or ("required_but_missing" if existing.get("required") else "not_required")),
        }
    if requires_login:
        return {"required": True, "reason": "requires_login", "status": "required_but_missing"}
    if page_type in {"x_thread", "forum_thread", "product_page"}:
        return {"required": True, "reason": page_type, "status": "required_but_missing"}
    return {"required": False, "reason": "static_public_article", "status": "not_required"}


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
            "screenshot": None,
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
    validation_report: dict[str, Any] | None,
    warnings: list[str],
) -> dict[str, Any]:
    validation = validation_report or {
        "status": "pending",
        "warnings": warnings,
        "requires_manual_review": bool(warnings),
        "run_status": "partial" if warnings else "complete",
        "validation_status": "pending",
        "manual_review": {
            "required": bool(warnings),
            "severity": "warning" if warnings else "info",
            "reasons": [],
        },
        "completion_blockers": [],
    }
    report_path = "validation/validation-report.json"
    evidence = [
        {"id": "E001", "type": "source_record", "path": "evidence/source_record.json"},
    ]
    if validation_report is not None:
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
        "validation_status": validation.get("validation_status", "passed" if validation.get("status") == "pass" else "failed" if validation.get("status") == "fail" else "pending"),
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
    run_dir = output_root / run_id
    (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    (run_dir / "evidence").mkdir(parents=True, exist_ok=True)
    (run_dir / "validation").mkdir(parents=True, exist_ok=True)

    source_url = args.url or input_path.as_uri()
    input_record = {
        "input_path": str(input_path),
        "source_url": source_url,
        "page_type": args.page_type,
        "requires_login": args.requires_login,
    }
    write_json(run_dir / "input.json", input_record)

    if input_path.suffix.lower() == ".json":
        capture = normalize_page_capture(read_json(input_path), source_url)
    else:
        html = input_path.read_text(encoding=args.encoding)
        capture = extract_html(html, source_url)

    ast_for_classification = capture.get("document_ast", {})
    page_type = classify_page_type(source_url, ast_for_classification, args.page_type)
    metadata, ast, warnings = normalize_capture(capture, source_url, page_type, args.requires_login, started_at)
    input_record["screenshot_policy"] = metadata["extraction"]["screenshot_policy"]

    source_record = build_source_record(metadata, run_dir)

    write_json(run_dir / "artifacts" / "metadata.json", metadata)
    write_json(run_dir / "artifacts" / "document_ast.json", ast)
    write_json(run_dir / "evidence" / "source_record.json", source_record)
    markdown = render_page_markdown(metadata, ast)
    write_text(run_dir / "artifacts" / "page.md", markdown)
    write_warnings(run_dir / "validation" / "warnings.md", warnings)

    draft_manifest = create_manifest(run_dir, run_id, started_at, utc_now(), input_record, None, warnings)
    write_json(run_dir / "manifest.json", draft_manifest)

    validation_report = validate_page_to_md_run(run_dir)
    write_json(run_dir / "validation" / "validation-report.json", validation_report)

    final_manifest = create_manifest(run_dir, run_id, started_at, utc_now(), input_record, validation_report, warnings)
    write_json(run_dir / "manifest.json", final_manifest)
    final_validation_report = validate_page_to_md_run(run_dir)
    write_json(run_dir / "validation" / "validation-report.json", final_validation_report)
    final_manifest = create_manifest(run_dir, run_id, started_at, utc_now(), input_record, final_validation_report, warnings)
    write_json(run_dir / "manifest.json", final_manifest)
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
    args = parser.parse_args()
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
