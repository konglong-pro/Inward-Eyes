from __future__ import annotations

import csv
import io
from typing import Any


CLAIM_TYPES = {"fact", "inference", "unknown"}
SUPPORT_TYPES = {"direct", "inferred"}


def source_dir_name(source_id: str) -> str:
    if source_id.startswith("S") and source_id[1:].isdigit():
        return f"source-{int(source_id[1:]):03d}"
    return source_id.lower().replace("_", "-")


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _strings(value: Any) -> list[str]:
    return [str(item) for item in _as_list(value) if str(item).strip()]


def default_screenshot_policy(page_type: str, requires_login: bool) -> dict[str, Any]:
    if requires_login:
        return {"required": True, "reason": "requires_login", "status": "required_but_missing"}
    if page_type in {"x_thread", "forum_thread", "product_page"}:
        return {"required": True, "reason": page_type, "status": "required_but_missing"}
    return {"required": False, "reason": "research_source_static", "status": "not_required"}


def normalize_source(raw_source: dict[str, Any], index: int, accessed_at: str) -> dict[str, Any]:
    source_id = str(raw_source.get("source_id") or f"S{index:03d}")
    page_type = str(raw_source.get("page_type") or "unknown")
    requires_login = bool(raw_source.get("requires_login"))
    screenshot_policy = raw_source.get("screenshot_policy")
    if not isinstance(screenshot_policy, dict):
        screenshot_policy = default_screenshot_policy(page_type, requires_login)

    evidence_dir = source_dir_name(source_id)
    screenshot = raw_source.get("screenshot")
    if screenshot is None and screenshot_policy.get("status") == "required_and_present":
        screenshot = f"evidence/{evidence_dir}/screenshot.png"

    return {
        "source_id": source_id,
        "url": str(raw_source.get("url") or ""),
        "canonical_url": raw_source.get("canonical_url"),
        "title": raw_source.get("title"),
        "site_name": raw_source.get("site_name"),
        "source_type": str(raw_source.get("source_type") or "unknown"),
        "page_type": page_type,
        "accessed_at": str(raw_source.get("accessed_at") or accessed_at),
        "requires_login": requires_login,
        "capture_method": str(raw_source.get("capture_method") or "research_input"),
        "evidence_status": str(raw_source.get("evidence_status") or "source_record_present"),
        "evidence_path": f"evidence/{evidence_dir}/source_record.json",
        "evidence": {
            "screenshot": screenshot,
            "snapshot": raw_source.get("snapshot"),
            "source_record": f"evidence/{evidence_dir}/source_record.json",
        },
        "screenshot_policy": screenshot_policy,
        "content_scope": raw_source.get("content_scope")
        if isinstance(raw_source.get("content_scope"), dict)
        else {
            "included": _strings(raw_source.get("included")) or ["task_relevant_content"],
            "excluded": _strings(raw_source.get("excluded"))
            or ["ads", "navigation", "recommendations", "comments_unless_relevant"],
        },
        "independence_note": raw_source.get("independence_note"),
        "notes": raw_source.get("notes"),
        "warnings": _strings(raw_source.get("warnings")),
    }


def source_record_from_summary(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_id": source["source_id"],
        "url": source["url"],
        "canonical_url": source.get("canonical_url"),
        "title": source.get("title"),
        "site_name": source.get("site_name"),
        "source_type": source.get("source_type"),
        "page_type": source.get("page_type") or "unknown",
        "accessed_at": source["accessed_at"],
        "requires_login": bool(source.get("requires_login")),
        "capture_method": source.get("capture_method") or "research_input",
        "evidence_status": source.get("evidence_status"),
        "evidence": source.get("evidence") or {},
        "screenshot_policy": source.get("screenshot_policy")
        or {"required": False, "reason": "unknown", "status": "not_required"},
        "content_scope": source.get("content_scope")
        or {"included": ["task_relevant_content"], "excluded": []},
        "independence_note": source.get("independence_note"),
        "warnings": _strings(source.get("warnings")),
    }


def normalize_claim(raw_claim: dict[str, Any], index: int) -> dict[str, Any]:
    claim_type = str(raw_claim.get("claim_type") or "fact")
    source_ids = _strings(raw_claim.get("source_ids"))
    support: list[dict[str, Any]] = []
    for item in _as_list(raw_claim.get("support")):
        if not isinstance(item, dict):
            continue
        support.append(
            {
                "source_id": str(item.get("source_id") or ""),
                "support_type": str(item.get("support_type") or item.get("type") or "direct"),
                "excerpt": item.get("excerpt"),
                "note": item.get("note"),
            }
        )

    return {
        "claim_id": str(raw_claim.get("claim_id") or f"C{index:03d}"),
        "text": str(raw_claim.get("text") or ""),
        "claim_type": claim_type,
        "is_key_finding": bool(raw_claim.get("is_key_finding", True)),
        "source_ids": source_ids,
        "support": support,
        "single_source": bool(raw_claim.get("single_source", len(source_ids) == 1)),
        "confidence": str(raw_claim.get("confidence") or ("unknown" if claim_type == "unknown" else "medium")),
        "notes": raw_claim.get("notes"),
    }


def unknown_to_claim(raw_unknown: dict[str, Any], index: int) -> dict[str, Any]:
    claim_id = str(raw_unknown.get("claim_id") or raw_unknown.get("unknown_id") or f"U{index:03d}")
    return normalize_claim(
        {
            "claim_id": claim_id,
            "text": raw_unknown.get("text"),
            "claim_type": "unknown",
            "is_key_finding": True,
            "source_ids": raw_unknown.get("source_ids") or raw_unknown.get("related_source_ids") or [],
            "support": raw_unknown.get("support") or [],
            "single_source": False,
            "confidence": "unknown",
            "notes": raw_unknown.get("notes") or raw_unknown.get("reason"),
        },
        index,
    )


def build_research_model(input_record: dict[str, Any], generated_at: str) -> dict[str, Any]:
    raw_sources = [item for item in _as_list(input_record.get("sources")) if isinstance(item, dict)]
    sources = [normalize_source(source, index, generated_at) for index, source in enumerate(raw_sources, start=1)]

    raw_claims = [item for item in _as_list(input_record.get("claims")) if isinstance(item, dict)]
    claims = [normalize_claim(claim, index) for index, claim in enumerate(raw_claims, start=1)]
    raw_unknowns = [item for item in _as_list(input_record.get("unknowns")) if isinstance(item, dict)]
    for index, unknown in enumerate(raw_unknowns, start=1):
        claims.append(unknown_to_claim(unknown, index))

    warnings = _strings(input_record.get("warnings"))
    return {
        "schema_version": "1.0",
        "task_type": "browser-research",
        "topic": str(input_record.get("topic") or "Untitled research"),
        "question": input_record.get("question"),
        "summary": input_record.get("summary"),
        "generated_at": generated_at,
        "sources": sources,
        "claims": claims,
        "warnings": warnings,
    }


def render_sources_csv(sources: list[dict[str, Any]]) -> str:
    output = io.StringIO()
    fieldnames = [
        "source_id",
        "url",
        "title",
        "site_name",
        "source_type",
        "accessed_at",
        "evidence_status",
        "requires_login",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for source in sources:
        writer.writerow({field: source.get(field) for field in fieldnames})
    return output.getvalue()


def _source_marker(source_ids: list[str]) -> str:
    return ", ".join(f"[{source_id}]" for source_id in source_ids) if source_ids else "[unsupported]"


def render_research_report(model: dict[str, Any]) -> str:
    lines: list[str] = [
        "---",
        f'title: "{model["topic"]}"',
        'task_type: "browser-research"',
        f'generated_at: "{model["generated_at"]}"',
        "---",
        "",
        f"# {model['topic']}",
        "",
    ]
    if model.get("question"):
        lines.extend([f"**Question:** {model['question']}", ""])
    if model.get("summary"):
        lines.extend(["## Summary", "", str(model["summary"]), ""])

    findings = [claim for claim in model["claims"] if claim["claim_type"] != "unknown"]
    if findings:
        lines.extend(["## Key Findings", ""])
        for claim in findings:
            source_ids = claim.get("source_ids") or []
            single_source = " single-source" if claim.get("single_source") else ""
            lines.append(
                f"- **{claim['claim_id']}** ({claim['claim_type']}, {claim['confidence']}{single_source}) "
                f"{claim['text']} {_source_marker(source_ids)}"
            )
            for support in claim.get("support") or []:
                source_id = support.get("source_id") or "unknown"
                support_type = support.get("support_type") or "unknown"
                excerpt = support.get("excerpt")
                detail = f"  - {support_type} support from [{source_id}]"
                if excerpt:
                    detail += f": {excerpt}"
                lines.append(detail)
        lines.append("")

    unknowns = [claim for claim in model["claims"] if claim["claim_type"] == "unknown"]
    if unknowns:
        lines.extend(["## Unknowns", ""])
        for claim in unknowns:
            lines.append(f"- **{claim['claim_id']}** {claim['text']} {_source_marker(claim.get('source_ids') or [])}")
            if claim.get("notes"):
                lines.append(f"  - Note: {claim['notes']}")
        lines.append("")

    lines.extend(["## Sources", ""])
    lines.append("| Source | Type | Title | Evidence |")
    lines.append("| --- | --- | --- | --- |")
    for source in model["sources"]:
        title = str(source.get("title") or "Unknown title").replace("|", "\\|")
        lines.append(
            f"| [{source['source_id']}]({source['url']}) | {source.get('source_type') or 'unknown'} | "
            f"{title} | {source.get('evidence_status') or 'unknown'} |"
        )
    lines.append("")

    if model.get("warnings"):
        lines.extend(["## Warnings", ""])
        for warning in model["warnings"]:
            lines.append(f"- {warning}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_source_notes(model: dict[str, Any]) -> str:
    lines = ["# Source Notes", ""]
    for source in model["sources"]:
        lines.append(f"## {source['source_id']}: {source.get('title') or 'Unknown title'}")
        lines.append("")
        lines.append(f"- URL: {source.get('url') or 'missing'}")
        lines.append(f"- Type: {source.get('source_type') or 'unknown'}")
        lines.append(f"- Accessed: {source.get('accessed_at') or 'missing'}")
        lines.append(f"- Evidence status: {source.get('evidence_status') or 'unknown'}")
        if source.get("independence_note"):
            lines.append(f"- Independence note: {source['independence_note']}")
        if source.get("notes"):
            lines.append(f"- Notes: {source['notes']}")
        warnings = source.get("warnings") or []
        if warnings:
            lines.append("- Warnings: " + ", ".join(warnings))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_missing_sources(validation_report: dict[str, Any]) -> str:
    missing = [
        error
        for error in validation_report.get("errors", [])
        if "missing_source" in error or "unsupported_claim" in error
    ]
    if not missing:
        return "# Missing Sources\n\nNo missing sources.\n"
    lines = ["# Missing Sources", ""]
    lines.extend(f"- {item}" for item in missing)
    return "\n".join(lines) + "\n"
