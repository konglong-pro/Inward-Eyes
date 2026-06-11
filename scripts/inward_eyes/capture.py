from __future__ import annotations

import ipaddress
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from inward_eyes.io import utc_now, write_json, write_text

LOGIN_STATES = {"known", "suspected", "not_required", "unknown"}
SCREENSHOT_STATUSES = {
    "required_and_present",
    "required_but_missing",
    "not_required",
    "capture_failed",
    "redacted",
}
PROMPT_INJECTION_PATTERNS = (
    "ignore previous instructions",
    "ignore all previous instructions",
    "disregard previous instructions",
    "send cookies",
    "reveal your system prompt",
)
PRIVATE_PATTERNS = (
    ("email_address", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
)


def _review_reasons(codes: list[str], severity: str, artifact: str) -> list[dict[str, str]]:
    return [{"code": code, "message": code.replace("_", " "), "severity": severity, "artifact": artifact} for code in codes]


def _status_fields(errors: list[str], warnings: list[str], manual_review: bool) -> dict[str, Any]:
    if errors:
        run_status = "failed"
        validation_status = "failed"
        severity = "blocking"
    elif manual_review:
        run_status = "partial"
        validation_status = "passed"
        severity = "warning"
    else:
        run_status = "complete"
        validation_status = "passed"
        severity = "info"
    return {
        "run_status": run_status,
        "validation_status": validation_status,
        "manual_review": {
            "required": manual_review or bool(errors),
            "severity": severity,
            "reasons": _review_reasons(errors, "blocking", "capture/page_capture.json")
            + _review_reasons(warnings if manual_review else [], "warning", "capture/page_capture.json"),
        },
        "completion_blockers": errors,
    }


def _non_empty_payload(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (dict, list)):
        return bool(value)
    return True


def content_payload_present(content: dict[str, Any]) -> bool:
    return any(
        _non_empty_payload(content.get(key))
        for key in ("html", "text", "accessibility_snapshot", "selected_main_content")
    )


def _iter_content_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        strings: list[str] = []
        for nested in value.values():
            strings.extend(_iter_content_strings(nested))
        return strings
    if isinstance(value, list):
        strings = []
        for nested in value:
            strings.extend(_iter_content_strings(nested))
        return strings
    return []


def detect_prompt_injection_text(content: dict[str, Any]) -> bool:
    haystack = "\n".join(_iter_content_strings(content)).lower()
    return any(pattern in haystack for pattern in PROMPT_INJECTION_PATTERNS)


def redact_private_text(value: Any) -> tuple[Any, list[str]]:
    notes: list[str] = []
    if isinstance(value, str):
        redacted = value
        for label, pattern in PRIVATE_PATTERNS:
            if pattern.search(redacted):
                notes.append(f"redacted_{label}")
                redacted = pattern.sub(f"[redacted-{label}]", redacted)
        return redacted, notes
    if isinstance(value, dict):
        redacted_dict: dict[str, Any] = {}
        for key, nested in value.items():
            redacted_value, nested_notes = redact_private_text(nested)
            redacted_dict[key] = redacted_value
            notes.extend(nested_notes)
        return redacted_dict, notes
    if isinstance(value, list):
        redacted_list = []
        for nested in value:
            redacted_value, nested_notes = redact_private_text(nested)
            redacted_list.append(redacted_value)
            notes.extend(nested_notes)
        return redacted_list, notes
    return value, notes


def has_raw_private_text(content: dict[str, Any]) -> bool:
    haystack = "\n".join(_iter_content_strings(content))
    return any(pattern.search(haystack) for _, pattern in PRIVATE_PATTERNS)


def default_screenshot_policy(
    *,
    required: bool,
    reason: str,
    screenshot_paths: list[str],
) -> dict[str, Any]:
    if required:
        status = "required_and_present" if screenshot_paths else "required_but_missing"
    else:
        status = "not_required"
    return {"required": required, "reason": reason, "status": status}


def build_page_capture(
    *,
    url: str,
    page_title: str | None,
    html: str | None = None,
    text: str | None = None,
    accessibility_snapshot: Any = None,
    selected_main_content: str | None = None,
    canonical_url: str | None = None,
    site_name: str | None = None,
    captured_at: str | None = None,
    capture_id: str | None = None,
    capture_method: str = "playwright_mcp_dom_snapshot",
    browser_tool: str = "playwright_mcp",
    login_state: str = "not_required",
    requires_login: bool = False,
    user_visible_profile: bool = False,
    region_or_locale: str | None = None,
    viewport: dict[str, Any] | None = None,
    screenshot_paths: list[str] | None = None,
    screenshot_required: bool = False,
    screenshot_reason: str = "static_public_article",
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    captured_at = captured_at or utc_now()
    capture_id = capture_id or f"cap_{re.sub(r'[^0-9TZ]', '', captured_at)}"
    screenshot_paths = screenshot_paths or []
    content = {
        "html": html,
        "text": text,
        "accessibility_snapshot": accessibility_snapshot,
        "selected_main_content": selected_main_content,
    }
    redacted_content, redaction_notes = redact_private_text(content)
    redaction_notes = list(dict.fromkeys(redaction_notes))
    warnings = list(dict.fromkeys(warnings or []))
    if redaction_notes and "private_data_redacted" not in warnings:
        warnings.append("private_data_redacted")
    if detect_prompt_injection_text(redacted_content) and "prompt_injection_text_present" not in warnings:
        warnings.append("prompt_injection_text_present")

    return {
        "schema_version": "1.0",
        "capture_id": capture_id,
        "captured_at": captured_at,
        "capture_method": capture_method,
        "source": {
            "url": url,
            "canonical_url": canonical_url,
            "page_title": page_title,
            "site_name": site_name,
            "requires_login": requires_login,
        },
        "browser_context": {
            "tool": browser_tool,
            "login_state": login_state,
            "user_visible_profile": user_visible_profile,
            "region_or_locale": region_or_locale,
            "viewport": viewport,
        },
        "content": redacted_content,
        "assets": {
            "screenshots": [{"path": path} for path in screenshot_paths],
            "images": [],
        },
        "privacy": {
            "redaction_applied": bool(redaction_notes),
            "private_data_detected": bool(redaction_notes),
            "redaction_notes": redaction_notes,
        },
        "screenshot_policy": default_screenshot_policy(
            required=screenshot_required,
            reason=screenshot_reason,
            screenshot_paths=screenshot_paths,
        ),
        "warnings": warnings,
    }


def validate_page_capture_contract(capture: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = list(dict.fromkeys(capture.get("warnings") or []))
    manual_review = False

    for key in (
        "schema_version",
        "capture_id",
        "captured_at",
        "capture_method",
        "source",
        "browser_context",
        "content",
        "assets",
        "privacy",
        "screenshot_policy",
        "warnings",
    ):
        if key not in capture:
            errors.append(f"{key}_missing")

    source = capture.get("source") if isinstance(capture.get("source"), dict) else {}
    browser_context = capture.get("browser_context") if isinstance(capture.get("browser_context"), dict) else {}
    content = capture.get("content") if isinstance(capture.get("content"), dict) else {}
    assets = capture.get("assets") if isinstance(capture.get("assets"), dict) else {}
    privacy = capture.get("privacy") if isinstance(capture.get("privacy"), dict) else {}
    screenshot_policy = capture.get("screenshot_policy") if isinstance(capture.get("screenshot_policy"), dict) else {}

    url = source.get("url")
    if not isinstance(url, str) or not url.strip():
        errors.append("source.url_missing")
    else:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            errors.append("source.url_not_http")
        else:
            hostname = parsed.hostname or ""
            if hostname.lower() in {"localhost", "127.0.0.1", "::1"} or hostname.lower().endswith(".local"):
                errors.append("source.url_not_public")
            else:
                try:
                    address = ipaddress.ip_address(hostname)
                except ValueError:
                    address = None
                if address and (address.is_private or address.is_loopback or address.is_link_local or address.is_reserved):
                    errors.append("source.url_not_public")
    if not isinstance(source.get("page_title"), str) or not source.get("page_title", "").strip():
        errors.append("source.page_title_missing")
    if not isinstance(source.get("requires_login"), bool):
        errors.append("source.requires_login_missing")
    elif source.get("requires_login"):
        errors.append("source.requires_login_out_of_scope")

    if not isinstance(browser_context.get("tool"), str) or not browser_context.get("tool", "").strip():
        errors.append("browser_context.tool_missing")
    if browser_context.get("tool") != "playwright_mcp":
        warnings.append(f"browser_context.unexpected_tool:{browser_context.get('tool')}")
    login_state = browser_context.get("login_state")
    if login_state not in LOGIN_STATES:
        errors.append(f"browser_context.login_state_invalid:{login_state}")
    elif login_state != "not_required":
        errors.append(f"browser_context.login_state_out_of_scope:{login_state}")
    if browser_context.get("user_visible_profile"):
        errors.append("browser_context.user_visible_profile_forbidden")

    if not content_payload_present(content):
        errors.append("content.payload_missing")
    if detect_prompt_injection_text(content) and "prompt_injection_text_present" not in warnings:
        warnings.append("prompt_injection_text_present")

    screenshots = assets.get("screenshots") if isinstance(assets.get("screenshots"), list) else []
    for index, screenshot in enumerate(screenshots, start=1):
        if not isinstance(screenshot, dict):
            errors.append(f"assets.screenshots.{index}.not_object")
            continue
        path = screenshot.get("path")
        if not isinstance(path, str) or not path.strip():
            errors.append(f"assets.screenshots.{index}.path_missing")
    if not isinstance(screenshot_policy.get("required"), bool):
        errors.append("screenshot_policy.required_missing")
    if not isinstance(screenshot_policy.get("reason"), str):
        errors.append("screenshot_policy.reason_missing")
    status = screenshot_policy.get("status")
    if status not in SCREENSHOT_STATUSES:
        errors.append(f"screenshot_policy.status_invalid:{status}")
    elif screenshot_policy.get("required"):
        if status == "required_but_missing":
            errors.append("screenshot_required_but_missing")
        elif status == "required_and_present" and not screenshots:
            errors.append("screenshot_required_and_present_but_asset_missing")
        elif status in {"capture_failed", "redacted"}:
            manual_review = True
            warnings.append(f"screenshot_{status}")

    if not isinstance(privacy.get("redaction_applied"), bool):
        errors.append("privacy.redaction_applied_missing")
    if not isinstance(privacy.get("private_data_detected"), bool):
        errors.append("privacy.private_data_detected_missing")
    if not isinstance(privacy.get("redaction_notes"), list):
        errors.append("privacy.redaction_notes_missing")
    if privacy.get("private_data_detected"):
        manual_review = True
        if not privacy.get("redaction_applied"):
            errors.append("privacy.private_data_detected_without_redaction")
        if "private_data_redacted" not in warnings:
            warnings.append("private_data_redacted")
    elif has_raw_private_text(content):
        errors.append("privacy.raw_private_data_detected")

    warnings = list(dict.fromkeys(warnings))
    status_value = "fail" if errors else "pass"
    return {
        "schema_version": "1.0",
        "status": status_value,
        "errors": errors,
        "warnings": warnings,
        "requires_manual_review": manual_review or bool(errors),
        "screenshot_policy": screenshot_policy or {"required": False, "reason": "unknown", "status": "not_required"},
        **_status_fields(errors, warnings, manual_review),
    }


def write_capture_stage_manifest(
    run_dir: Path,
    *,
    run_id: str,
    started_at: str,
    finished_at: str,
    input_record: dict[str, Any],
    report: dict[str, Any],
    capture_written: bool,
    aborted_by_policy: bool = False,
) -> dict[str, Any]:
    run_status = report.get("run_status", "partial")
    if aborted_by_policy:
        run_status = "aborted_by_policy"
    evidence = []
    if capture_written:
        evidence.append({"id": "C001", "type": "page_capture", "path": "capture/page_capture.json"})
    manifest = {
        "run_id": run_id,
        "task": "page-to-md",
        "started_at": started_at,
        "finished_at": finished_at,
        "operator": "codex",
        "skill": "page-to-md",
        "inputs": input_record,
        "artifacts": [],
        "evidence": evidence,
        "validation": {
            "schema_valid": report.get("status") == "pass",
            "warnings": len(report.get("warnings", [])),
            "requires_manual_review": bool(report.get("requires_manual_review")),
            "report_path": "validation/capture-validation-report.json",
        },
        "warnings": report.get("warnings", []),
        "requires_manual_review": bool(report.get("requires_manual_review")),
        "run_status": run_status,
        "validation_status": report.get("validation_status", "failed"),
        "manual_review": report.get("manual_review", {"required": True, "severity": "blocking", "reasons": []}),
        "completion_blockers": report.get("completion_blockers", []),
        "screenshot_policy": report.get(
            "screenshot_policy",
            {"required": False, "reason": "unknown", "status": "capture_failed"},
        ),
    }
    write_json(run_dir / "manifest.json", manifest)
    return manifest


def write_capture_warnings(path: Path, warnings: list[str]) -> None:
    if not warnings:
        write_text(path, "No warnings.\n")
        return
    lines = ["# Capture Warnings", ""]
    lines.extend(f"- {warning}" for warning in warnings)
    write_text(path, "\n".join(lines) + "\n")
