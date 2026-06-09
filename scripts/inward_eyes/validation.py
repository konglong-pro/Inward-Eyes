from __future__ import annotations

import re
from pathlib import Path
from typing import Any

BOILERPLATE_PATTERNS = (
    "sign in",
    "subscribe",
    "recommended",
    "more like this",
    "advertisement",
    "cookie policy",
)


def _field(data: dict[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def validate_page_to_md_run(run_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    manual_review = False

    metadata_path = run_dir / "artifacts" / "metadata.json"
    ast_path = run_dir / "artifacts" / "document_ast.json"
    markdown_path = run_dir / "artifacts" / "page.md"
    manifest_path = run_dir / "manifest.json"
    source_record_path = run_dir / "evidence" / "source_record.json"

    import json

    def load(path: Path) -> dict[str, Any] | None:
        if not path.exists():
            errors.append(f"missing_file:{path.relative_to(run_dir).as_posix()}")
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"invalid_json:{path.relative_to(run_dir).as_posix()}:{exc}")
            return None

    metadata = load(metadata_path)
    ast = load(ast_path)
    source_record = load(source_record_path)

    if not markdown_path.exists():
        errors.append("missing_file:artifacts/page.md")
        markdown = ""
    else:
        markdown = markdown_path.read_text(encoding="utf-8")

    manifest = load(manifest_path)

    if metadata:
        if not _field(metadata, "source.url"):
            errors.append("metadata.source.url_missing")
        if not _field(metadata, "source.accessed_at"):
            errors.append("metadata.source.accessed_at_missing")
        title = _field(metadata, "document.title.value")
        title_warnings = _field(metadata, "extraction.warnings") or []
        if not title and "title_not_found" not in title_warnings:
            errors.append("title_missing_without_warning")
        if _field(metadata, "document.author.value") is None and "author_not_found" not in title_warnings:
            warnings.append("author_unknown_without_standard_warning")
        if _field(metadata, "document.published_at.value") is None and "published_at_not_found" not in title_warnings:
            warnings.append("published_at_unknown_without_standard_warning")
        if not _field(metadata, "extraction.method"):
            errors.append("metadata.extraction.method_missing")
        screenshot_policy = _field(metadata, "extraction.screenshot_policy") or {}
        screenshot_assets = [asset for asset in metadata.get("assets", []) if asset.get("type") == "screenshot"]
        if screenshot_policy.get("required"):
            status = screenshot_policy.get("status")
            if status == "required_and_present":
                if not screenshot_assets:
                    errors.append("screenshot_required_and_present_but_asset_missing")
                    manual_review = True
            elif status == "required_but_missing":
                errors.append("screenshot_required_but_missing")
                manual_review = True
            elif status in {"capture_failed", "redacted"}:
                warnings.append(f"screenshot_{status}")
                manual_review = True

    if ast:
        ast_document = ast.get("document", {})
        blocks = ast_document.get("blocks", [])
        if not blocks:
            errors.append("document_ast.blocks_empty")
        image_blocks = [block for block in blocks if block.get("type") == "image"]
        for index, block in enumerate(image_blocks, start=1):
            if not block.get("alt"):
                warnings.append(f"image_{index}_no_caption")

    h1_count = len(re.findall(r"(?m)^# [^\n]+", markdown))
    if h1_count != 1:
        errors.append(f"markdown.h1_count:{h1_count}")

    body_text = re.sub(r"(?s)^---.*?---", "", markdown).strip()
    if len(body_text) < 120:
        warnings.append("markdown_body_suspiciously_short")
        manual_review = True

    lower_markdown = markdown.lower()
    for pattern in BOILERPLATE_PATTERNS:
        if pattern in lower_markdown:
            warnings.append(f"possible_boilerplate:{pattern}")

    url_count = len(re.findall(r"https?://", markdown))
    if url_count > 50:
        warnings.append("markdown_url_count_high")
        manual_review = True

    if metadata and source_record:
        if metadata["source"].get("url") != source_record.get("url"):
            errors.append("source_record.url_mismatch")

    if manifest:
        for section in ("artifacts", "evidence"):
            records = manifest.get(section, [])
            if not isinstance(records, list):
                errors.append(f"manifest.{section}_not_list")
                continue
            for index, record in enumerate(records):
                if not isinstance(record, dict):
                    errors.append(f"manifest.{section}[{index}]_not_object")
                    continue
                raw_path = record.get("path")
                if not raw_path:
                    errors.append(f"manifest.{section}[{index}].path_missing")
                    continue
                if not (run_dir / raw_path).exists():
                    errors.append(f"manifest.{section}[{index}].path_missing_on_disk:{raw_path}")

        manifest_source = _field(manifest, "inputs.source_url")
        if metadata and manifest_source and manifest_source != metadata["source"].get("url"):
            errors.append("manifest.inputs.source_url_mismatch")

    status = "fail" if errors else "pass"
    return {
        "schema_version": "1.0",
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "requires_manual_review": manual_review,
        "screenshot_policy": _field(metadata or {}, "extraction.screenshot_policy") or {"required": False, "reason": "unknown", "status": "not_required"},
    }
