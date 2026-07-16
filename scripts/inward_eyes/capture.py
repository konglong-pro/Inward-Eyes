from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from inward_eyes.io import read_json, utc_now, write_json, write_text
from inward_eyes.paths import CONTINUATION_HANDOFF_PATH, resolve_run_relative, validate_run_id

LOGIN_STATES = {"confirmed", "suspected", "not_required", "unknown"}
SCREENSHOT_STATUSES = {
    "required_and_present",
    "required_but_missing",
    "not_required",
    "capture_failed",
    "redacted",
}
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
FORBIDDEN_CAPTURE_KEYS = {
    "cookies",
    "cookie",
    "tokens",
    "token",
    "har",
    "network_log",
    "local_storage",
    "session_storage",
    "browser_profile",
    "browser_profiles",
    "password",
    "passwords",
    "payment_details",
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
SCREENSHOT_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
CAPTURE_STAGE_MANIFEST_PATH = "validation/capture-stage-manifest.json"
PAGE_WORKFLOW_OWNERSHIP_PATH = ".inward-eyes-page-workflow-owner.json"
CAPTURE_REPORT_REQUIRED_FIELDS = {
    "schema_version",
    "status",
    "errors",
    "warnings",
    "requires_manual_review",
    "run_status",
    "validation_status",
    "manual_review",
    "completion_blockers",
    "screenshot_policy",
}
OWNERSHIP_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{32,256}$")
CAPTURE_ADMISSION_PATHS = (
    "capture/page_capture.json",
    "validation/capture-validation-report.json",
    CAPTURE_STAGE_MANIFEST_PATH,
)


def _review_reasons(codes: list[str], severity: str, artifact: str) -> list[dict[str, str]]:
    return [{"code": code, "message": code.replace("_", " "), "severity": severity, "artifact": artifact} for code in codes]


def screenshot_file_is_valid(path: Path) -> bool:
    if not path.is_file() or path.suffix.lower() not in SCREENSHOT_EXTENSIONS:
        return False
    try:
        header = path.read_bytes()[:12]
    except OSError:
        return False
    suffix = path.suffix.lower()
    if suffix == ".png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    if suffix in {".jpg", ".jpeg"}:
        return header.startswith(b"\xff\xd8\xff")
    if suffix == ".gif":
        return header.startswith((b"GIF87a", b"GIF89a"))
    return len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP"


def _ownership_token_sha256(ownership_token: str) -> str:
    if not isinstance(ownership_token, str) or not OWNERSHIP_TOKEN_PATTERN.fullmatch(ownership_token):
        raise ValueError("workflow ownership token must be 32-256 URL-safe characters")
    return hashlib.sha256(ownership_token.encode("utf-8")).hexdigest()


def claim_page_workflow_ownership(
    run_dir: Path,
    *,
    run_id: str,
    ownership_token: str | None,
) -> None:
    if ownership_token is None:
        return
    safe_run_id = validate_run_id(run_id)
    token_sha256 = _ownership_token_sha256(ownership_token)
    if run_dir.is_symlink() or not run_dir.is_dir() or run_dir.name != safe_run_id:
        raise ValueError("workflow ownership can only be claimed for the newly created run directory")
    marker_path = run_dir / PAGE_WORKFLOW_OWNERSHIP_PATH
    payload = json.dumps(
        {
            "schema_version": "1.0",
            "run_id": safe_run_id,
            "token_sha256": token_sha256,
        },
        ensure_ascii=False,
        indent=2,
    ) + "\n"
    handle = marker_path.open("x", encoding="utf-8", newline="\n")
    try:
        with handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        marker_path.unlink(missing_ok=True)
        raise


def page_workflow_ownership_matches(
    run_dir: Path,
    *,
    run_id: str,
    ownership_token: str,
) -> bool:
    try:
        safe_run_id = validate_run_id(run_id)
        token_sha256 = _ownership_token_sha256(ownership_token)
    except ValueError:
        return False
    if run_dir.is_symlink() or not run_dir.is_dir() or run_dir.name != safe_run_id:
        return False
    marker_path = run_dir / PAGE_WORKFLOW_OWNERSHIP_PATH
    if marker_path.is_symlink() or not marker_path.is_file():
        return False
    try:
        marker = read_json(marker_path)
    except (OSError, ValueError):
        return False
    return (
        isinstance(marker, dict)
        and marker.get("schema_version") == "1.0"
        and marker.get("run_id") == safe_run_id
        and isinstance(marker.get("token_sha256"), str)
        and hmac.compare_digest(marker["token_sha256"], token_sha256)
    )


def release_page_workflow_ownership(
    run_dir: Path,
    *,
    run_id: str,
    ownership_token: str,
) -> bool:
    if not page_workflow_ownership_matches(
        run_dir,
        run_id=run_id,
        ownership_token=ownership_token,
    ):
        return False
    (run_dir / PAGE_WORKFLOW_OWNERSHIP_PATH).unlink(missing_ok=True)
    return True


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


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


def _normalize_login_state(login_state: str) -> str:
    return "confirmed" if login_state == "known" else login_state


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
    source_page_type: str | None = None,
    user_visible_profile: bool = False,
    current_page_approved: bool = False,
    capture_scope: str | None = None,
    region_or_locale: str | None = None,
    viewport: dict[str, Any] | None = None,
    screenshot_paths: list[str] | None = None,
    screenshot_required: bool = False,
    screenshot_reason: str = "static_public_article",
    screenshot_privacy_reviewed: bool = False,
    contains_private_data: bool = False,
    redaction_applied: bool = False,
    redaction_notes: list[str] | None = None,
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
    login_state = _normalize_login_state(login_state)
    redacted_content, detected_redaction_notes = redact_private_text(content)
    redaction_notes = list(dict.fromkeys(detected_redaction_notes + (redaction_notes or [])))
    warnings = list(dict.fromkeys(warnings or []))
    detected_private_data = bool(contains_private_data or redaction_notes)
    effective_redaction_applied = bool(redaction_applied or detected_redaction_notes)
    if detected_redaction_notes and "private_data_redacted" not in warnings:
        warnings.append("private_data_redacted")
    elif detected_private_data and "private_data_warning" not in warnings:
        warnings.append("private_data_warning")
    if detect_prompt_injection_text(redacted_content) and "prompt_injection_text_present" not in warnings:
        warnings.append("prompt_injection_text_present")

    source = {
        "url": url,
        "canonical_url": canonical_url,
        "page_title": page_title,
        "site_name": site_name,
        "requires_login": requires_login,
    }
    if source_page_type:
        source["page_type"] = source_page_type

    browser_context = {
        "tool": browser_tool,
        "login_state": login_state,
        "user_visible_profile": user_visible_profile,
        "region_or_locale": region_or_locale,
        "viewport": viewport,
    }
    if current_page_approved:
        browser_context["user_approved_current_page"] = True
    if capture_scope:
        browser_context["scope"] = capture_scope

    return {
        "schema_version": "1.0",
        "capture_id": capture_id,
        "captured_at": captured_at,
        "capture_method": capture_method,
        "login_state": login_state,
        "contains_private_data": detected_private_data,
        "redaction_applied": effective_redaction_applied,
        "redaction_notes": redaction_notes,
        "source": source,
        "browser_context": browser_context,
        "content": redacted_content,
        "assets": {
            "screenshots": [{"path": path} for path in screenshot_paths],
            "images": [],
        },
        "privacy": {
            "redaction_applied": effective_redaction_applied,
            "private_data_detected": detected_private_data,
            "contains_private_data": detected_private_data,
            "redaction_notes": redaction_notes,
            "screenshot_privacy_reviewed": screenshot_privacy_reviewed,
        },
        "screenshot_policy": default_screenshot_policy(
            required=screenshot_required,
            reason=screenshot_reason,
            screenshot_paths=screenshot_paths,
        ),
        "warnings": warnings,
    }


def _capture_is_current_browser(capture: dict[str, Any]) -> bool:
    browser_context = capture.get("browser_context") if isinstance(capture.get("browser_context"), dict) else {}
    capture_method = str(capture.get("capture_method") or "")
    return browser_context.get("tool") == "current_chrome" or capture_method.startswith("current_chrome")


def _iter_dict_keys(value: Any) -> list[str]:
    if isinstance(value, dict):
        keys = list(value.keys())
        for nested in value.values():
            keys.extend(_iter_dict_keys(nested))
        return keys
    if isinstance(value, list):
        keys: list[str] = []
        for nested in value:
            keys.extend(_iter_dict_keys(nested))
        return keys
    return []


def _screenshot_required_reasons(capture: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    source = capture.get("source") if isinstance(capture.get("source"), dict) else {}
    browser_context = capture.get("browser_context") if isinstance(capture.get("browser_context"), dict) else {}
    privacy = capture.get("privacy") if isinstance(capture.get("privacy"), dict) else {}
    raw_warnings = capture.get("warnings")
    warnings = set(raw_warnings) if isinstance(raw_warnings, list) and all(
        isinstance(item, str) for item in raw_warnings
    ) else set()
    page_type = source.get("page_type")

    if source.get("requires_login") or browser_context.get("login_state") in {"confirmed", "suspected"}:
        reasons.append("logged_in_page")
    if bool(capture.get("contains_private_data") or privacy.get("contains_private_data") or privacy.get("private_data_detected")):
        reasons.append("private_data")
    if page_type in SCREENSHOT_REQUIRED_PAGE_TYPES:
        reasons.append(str(page_type))
    for warning in sorted(warnings.intersection(SCREENSHOT_REQUIRED_WARNINGS)):
        reasons.append(warning)
    return list(dict.fromkeys(reasons))


def _page_capture_shape_errors(capture: Any) -> list[str]:
    if not isinstance(capture, dict):
        return ["schema:$:expected_object"]

    errors: list[str] = []

    def require_fields(value: dict[str, Any], fields: tuple[str, ...], path: str) -> None:
        for field in fields:
            if field not in value:
                errors.append(f"schema:{path}.{field}:missing_required_key")

    def require_string(value: Any, path: str, *, non_empty: bool = False) -> None:
        if not isinstance(value, str):
            errors.append(f"schema:{path}:expected_string")
        elif non_empty and not value:
            errors.append(f"schema:{path}:empty_string")

    def require_nullable_string(value: Any, path: str) -> None:
        if value is not None and not isinstance(value, str):
            errors.append(f"schema:{path}:expected_string_or_null")

    def require_bool(value: Any, path: str) -> None:
        if not isinstance(value, bool):
            errors.append(f"schema:{path}:expected_boolean")

    def require_string_list(value: Any, path: str) -> None:
        if not isinstance(value, list):
            errors.append(f"schema:{path}:expected_array")
            return
        for index, item in enumerate(value):
            if not isinstance(item, str):
                errors.append(f"schema:{path}[{index}]:expected_string")

    require_fields(
        capture,
        (
            "schema_version",
            "capture_id",
            "captured_at",
            "capture_method",
            "login_state",
            "contains_private_data",
            "redaction_applied",
            "redaction_notes",
            "source",
            "browser_context",
            "content",
            "assets",
            "privacy",
            "screenshot_policy",
            "warnings",
        ),
        "$",
    )
    if "schema_version" in capture:
        require_string(capture["schema_version"], "$.schema_version")
    if "capture_id" in capture:
        require_string(capture["capture_id"], "$.capture_id", non_empty=True)
    if "captured_at" in capture:
        require_string(capture["captured_at"], "$.captured_at", non_empty=True)
    if "capture_method" in capture:
        require_string(capture["capture_method"], "$.capture_method", non_empty=True)
    if "login_state" in capture:
        if not isinstance(capture["login_state"], str) or capture["login_state"] not in LOGIN_STATES:
            errors.append("schema:$.login_state:invalid_enum")
    if "contains_private_data" in capture:
        require_bool(capture["contains_private_data"], "$.contains_private_data")
    if "redaction_applied" in capture:
        require_bool(capture["redaction_applied"], "$.redaction_applied")
    if "redaction_notes" in capture:
        require_string_list(capture["redaction_notes"], "$.redaction_notes")
    if "warnings" in capture:
        require_string_list(capture["warnings"], "$.warnings")
    for field in ("document", "document_ast"):
        if field in capture and not isinstance(capture[field], dict):
            errors.append(f"schema:$.{field}:expected_object")

    source = capture.get("source")
    if not isinstance(source, dict):
        if "source" in capture:
            errors.append("schema:$.source:expected_object")
    else:
        require_fields(source, ("url", "page_title", "requires_login"), "$.source")
        if "url" in source:
            require_string(source["url"], "$.source.url", non_empty=True)
        if "page_title" in source:
            require_string(source["page_title"], "$.source.page_title", non_empty=True)
        if "requires_login" in source:
            require_bool(source["requires_login"], "$.source.requires_login")
        if "canonical_url" in source:
            require_nullable_string(source["canonical_url"], "$.source.canonical_url")
        if "site_name" in source:
            require_nullable_string(source["site_name"], "$.source.site_name")

    browser_context = capture.get("browser_context")
    if not isinstance(browser_context, dict):
        if "browser_context" in capture:
            errors.append("schema:$.browser_context:expected_object")
    else:
        require_fields(browser_context, ("tool", "login_state"), "$.browser_context")
        if "tool" in browser_context:
            require_string(browser_context["tool"], "$.browser_context.tool", non_empty=True)
        if "login_state" in browser_context:
            if (
                not isinstance(browser_context["login_state"], str)
                or browser_context["login_state"] not in LOGIN_STATES
            ):
                errors.append("schema:$.browser_context.login_state:invalid_enum")
        if "user_visible_profile" in browser_context:
            require_bool(browser_context["user_visible_profile"], "$.browser_context.user_visible_profile")
        if "region_or_locale" in browser_context:
            require_nullable_string(browser_context["region_or_locale"], "$.browser_context.region_or_locale")
        if "viewport" in browser_context and browser_context["viewport"] is not None and not isinstance(
            browser_context["viewport"], dict
        ):
            errors.append("schema:$.browser_context.viewport:expected_object_or_null")

    content = capture.get("content")
    if not isinstance(content, dict):
        if "content" in capture:
            errors.append("schema:$.content:expected_object")
    else:
        require_fields(
            content,
            ("html", "text", "accessibility_snapshot", "selected_main_content"),
            "$.content",
        )
        for field in ("html", "text", "selected_main_content"):
            if field in content:
                require_nullable_string(content[field], f"$.content.{field}")
        if "accessibility_snapshot" in content and content["accessibility_snapshot"] is not None and not isinstance(
            content["accessibility_snapshot"], (dict, list, str)
        ):
            errors.append(
                "schema:$.content.accessibility_snapshot:expected_object_array_string_or_null"
            )

    assets = capture.get("assets")
    if not isinstance(assets, dict):
        if "assets" in capture:
            errors.append("schema:$.assets:expected_object")
    else:
        require_fields(assets, ("screenshots", "images"), "$.assets")
        screenshots = assets.get("screenshots")
        if not isinstance(screenshots, list):
            if "screenshots" in assets:
                errors.append("schema:$.assets.screenshots:expected_array")
        else:
            for index, screenshot in enumerate(screenshots):
                path = f"$.assets.screenshots[{index}]"
                if not isinstance(screenshot, dict):
                    errors.append(f"schema:{path}:expected_object")
                    continue
                require_fields(screenshot, ("path",), path)
                if "path" in screenshot:
                    require_string(screenshot["path"], f"{path}.path", non_empty=True)
                if "captured_at" in screenshot:
                    require_nullable_string(screenshot["captured_at"], f"{path}.captured_at")
        if "images" in assets and not isinstance(assets["images"], list):
            errors.append("schema:$.assets.images:expected_array")

    privacy = capture.get("privacy")
    if not isinstance(privacy, dict):
        if "privacy" in capture:
            errors.append("schema:$.privacy:expected_object")
    else:
        require_fields(
            privacy,
            ("redaction_applied", "private_data_detected", "contains_private_data", "redaction_notes"),
            "$.privacy",
        )
        for field in ("redaction_applied", "private_data_detected", "contains_private_data"):
            if field in privacy:
                require_bool(privacy[field], f"$.privacy.{field}")
        if "redaction_notes" in privacy:
            require_string_list(privacy["redaction_notes"], "$.privacy.redaction_notes")
        if "screenshot_privacy_reviewed" in privacy:
            require_bool(privacy["screenshot_privacy_reviewed"], "$.privacy.screenshot_privacy_reviewed")

    screenshot_policy = capture.get("screenshot_policy")
    if not isinstance(screenshot_policy, dict):
        if "screenshot_policy" in capture:
            errors.append("schema:$.screenshot_policy:expected_object")
    else:
        require_fields(screenshot_policy, ("required", "reason", "status"), "$.screenshot_policy")
        if "required" in screenshot_policy:
            require_bool(screenshot_policy["required"], "$.screenshot_policy.required")
        if "reason" in screenshot_policy:
            require_string(screenshot_policy["reason"], "$.screenshot_policy.reason")
        if "status" in screenshot_policy:
            if (
                not isinstance(screenshot_policy["status"], str)
                or screenshot_policy["status"] not in SCREENSHOT_STATUSES
            ):
                errors.append("schema:$.screenshot_policy.status:invalid_enum")

    return list(dict.fromkeys(errors))


def validate_page_capture_contract(capture: Any) -> dict[str, Any]:
    errors = _page_capture_shape_errors(capture)
    if not isinstance(capture, dict):
        return {
            "schema_version": "1.0",
            "status": "fail",
            "errors": errors,
            "warnings": [],
            "requires_manual_review": True,
            "screenshot_policy": {"required": False, "reason": "invalid_capture", "status": "capture_failed"},
            **_status_fields(errors, [], False),
        }
    raw_warnings = capture.get("warnings")
    warnings: list[str] = (
        list(dict.fromkeys(raw_warnings))
        if isinstance(raw_warnings, list) and all(isinstance(item, str) for item in raw_warnings)
        else []
    )
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
    is_current_browser = _capture_is_current_browser(capture)

    url = source.get("url")
    if not isinstance(url, str) or not url.strip():
        errors.append("source.url_missing")
    else:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            errors.append("source.url_not_http")
        elif not is_current_browser:
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
    elif source.get("requires_login") and not is_current_browser:
        errors.append("source.requires_login_out_of_scope")

    if not isinstance(browser_context.get("tool"), str) or not browser_context.get("tool", "").strip():
        errors.append("browser_context.tool_missing")
    if browser_context.get("tool") not in {"playwright_mcp", "current_chrome"}:
        warnings.append(f"browser_context.unexpected_tool:{browser_context.get('tool')}")
    login_state = _normalize_login_state(str(browser_context.get("login_state")))
    if login_state not in LOGIN_STATES:
        errors.append(f"browser_context.login_state_invalid:{browser_context.get('login_state')}")
    elif login_state != "not_required" and not is_current_browser:
        errors.append(f"browser_context.login_state_out_of_scope:{login_state}")
    if capture.get("login_state") is not None and _normalize_login_state(str(capture.get("login_state"))) != login_state:
        errors.append("login_state_alias_mismatch")
    if browser_context.get("user_visible_profile") and not is_current_browser:
        errors.append("browser_context.user_visible_profile_forbidden")
    if is_current_browser:
        if browser_context.get("user_approved_current_page") is not True:
            errors.append("current_browser.user_approved_current_page_missing")
        if browser_context.get("scope") != "current_visible_page":
            errors.append("current_browser.scope_not_current_visible_page")
        if browser_context.get("related_tabs_scanned"):
            errors.append("current_browser.related_tabs_scanned_forbidden")
        if browser_context.get("account_menu_explored"):
            errors.append("current_browser.account_menu_exploration_forbidden")

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
    required_reasons = _screenshot_required_reasons(capture)
    if required_reasons and screenshot_policy.get("required") is not True:
        errors.append(f"screenshot_policy.required_missing_for:{'+'.join(required_reasons)}")
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
            if not screenshots:
                errors.append("screenshot_required_evidence_missing")
    if is_current_browser and screenshots and privacy.get("screenshot_privacy_reviewed") is not True:
        errors.append("screenshot_privacy_review_missing")

    if not isinstance(privacy.get("redaction_applied"), bool):
        errors.append("privacy.redaction_applied_missing")
    if not isinstance(privacy.get("private_data_detected"), bool):
        errors.append("privacy.private_data_detected_missing")
    if not isinstance(privacy.get("contains_private_data"), bool):
        errors.append("privacy.contains_private_data_missing")
    if not isinstance(privacy.get("redaction_notes"), list):
        errors.append("privacy.redaction_notes_missing")
    if capture.get("contains_private_data") is not None and bool(capture.get("contains_private_data")) != bool(privacy.get("contains_private_data")):
        errors.append("privacy.contains_private_data_alias_mismatch")
    if capture.get("redaction_applied") is not None and bool(capture.get("redaction_applied")) != bool(privacy.get("redaction_applied")):
        errors.append("privacy.redaction_applied_alias_mismatch")
    if capture.get("redaction_notes") is not None and capture.get("redaction_notes") != privacy.get("redaction_notes"):
        errors.append("privacy.redaction_notes_alias_mismatch")
    if privacy.get("private_data_detected") or privacy.get("contains_private_data"):
        manual_review = True
        if privacy.get("redaction_applied") and "private_data_redacted" not in warnings:
            warnings.append("private_data_redacted")
        elif "private_data_warning" not in warnings:
            warnings.append("private_data_warning")
    elif has_raw_private_text(content):
        errors.append("privacy.raw_private_data_detected")

    for key in _iter_dict_keys(capture):
        if key.lower() in FORBIDDEN_CAPTURE_KEYS:
            errors.append(f"forbidden_capture_key:{key}")

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


def read_capture_admission_bundle(
    run_dir: Path,
    *,
    expected_run_id: str,
    returncode: int,
) -> tuple[
    dict[str, Any] | None,
    dict[str, Any] | None,
    dict[str, Any] | None,
    dict[str, str],
    list[str],
]:
    documents: dict[str, dict[str, Any] | None] = {}
    digests: dict[str, str] = {}
    errors: list[str] = []
    for relative_path in CAPTURE_ADMISSION_PATHS:
        try:
            path = resolve_run_relative(run_dir, relative_path, must_exist=True)
            payload = path.read_bytes()
        except (OSError, ValueError) as exc:
            documents[relative_path] = None
            errors.append(f"capture_admission_read_failed:{relative_path}:{type(exc).__name__}")
            continue
        digests[relative_path] = f"sha256:{hashlib.sha256(payload).hexdigest()}"
        try:
            document = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError):
            documents[relative_path] = None
            errors.append(f"capture_admission_json_invalid:{relative_path}")
            continue
        if not isinstance(document, dict):
            documents[relative_path] = None
            errors.append(f"capture_admission_json_not_object:{relative_path}")
            continue
        documents[relative_path] = document

    capture = documents.get("capture/page_capture.json")
    report = documents.get("validation/capture-validation-report.json")
    manifest = documents.get(CAPTURE_STAGE_MANIFEST_PATH)
    errors.extend(
        capture_admissibility_errors(
            capture=capture,
            report=report,
            manifest=manifest,
            returncode=returncode,
            run_dir=run_dir,
            expected_run_id=expected_run_id,
        )
    )
    return capture, report, manifest, digests, list(dict.fromkeys(errors))


def _capture_report_shape_error(report: dict[str, Any]) -> str | None:
    missing = sorted(CAPTURE_REPORT_REQUIRED_FIELDS - report.keys())
    if missing:
        return f"required_field_missing:{missing[0]}"
    if not isinstance(report.get("schema_version"), str) or not report["schema_version"]:
        return "field_invalid:schema_version"
    if report.get("status") not in {"pass", "fail"}:
        return "field_invalid:status"
    for field in ("errors", "warnings", "completion_blockers"):
        value = report.get(field)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            return f"field_invalid:{field}"
    if not isinstance(report.get("requires_manual_review"), bool):
        return "field_invalid:requires_manual_review"
    if report.get("run_status") not in {"complete", "partial", "failed", "aborted_by_policy"}:
        return "field_invalid:run_status"
    if report.get("validation_status") not in {"passed", "failed"}:
        return "field_invalid:validation_status"
    manual_review = report.get("manual_review")
    if not isinstance(manual_review, dict):
        return "field_invalid:manual_review"
    if (
        not isinstance(manual_review.get("required"), bool)
        or manual_review.get("severity") not in {"info", "warning", "blocking"}
        or not isinstance(manual_review.get("reasons"), list)
        or not all(isinstance(reason, dict) for reason in manual_review.get("reasons", []))
    ):
        return "field_invalid:manual_review"
    if manual_review["required"] != report["requires_manual_review"]:
        return "field_invalid:manual_review.required"
    for reason in manual_review["reasons"]:
        if (
            not isinstance(reason.get("code"), str)
            or not reason["code"]
            or not isinstance(reason.get("message"), str)
            or reason.get("severity") not in {"info", "warning", "blocking"}
            or not isinstance(reason.get("artifact"), str)
            or not reason["artifact"]
        ):
            return "field_invalid:manual_review.reasons"
    screenshot_policy = report.get("screenshot_policy")
    if not isinstance(screenshot_policy, dict):
        return "field_invalid:screenshot_policy"
    if (
        not isinstance(screenshot_policy.get("required"), bool)
        or not isinstance(screenshot_policy.get("reason"), str)
        or not screenshot_policy["reason"]
        or screenshot_policy.get("status") not in SCREENSHOT_STATUSES
    ):
        return "field_invalid:screenshot_policy"
    return None


def capture_admissibility_errors(
    *,
    capture: dict[str, Any] | None,
    report: dict[str, Any] | None,
    manifest: dict[str, Any] | None,
    returncode: int,
    run_dir: Path,
    expected_run_id: str,
) -> list[str]:
    from inward_eyes.validation import (
        canonical_manifest_shape_error,
        validate_manifest_paths,
        validate_manifest_status,
    )

    errors: list[str] = []
    if capture is None:
        errors.append("capture_missing")
        canonical_report = None
    else:
        canonical_report = validate_page_capture_contract(capture)
        if canonical_report.get("status") != "pass":
            errors.append("capture_contract_not_passed")
    if report is None:
        errors.append("capture_report_missing")
    else:
        report_shape_error = _capture_report_shape_error(report)
        if report_shape_error:
            errors.append(f"capture_report_shape:{report_shape_error}")
        else:
            errors.extend(f"capture_report_{error}" for error in validate_manifest_status(report))
        if report.get("status") != "pass":
            errors.append("capture_report_not_passed")
        if report.get("validation_status") != "passed":
            errors.append("capture_report_validation_not_passed")
        if report.get("errors"):
            errors.append("capture_report_has_errors")
        if report.get("completion_blockers"):
            errors.append("capture_report_has_blockers")
        if canonical_report is not None:
            for field in (
                "status",
                "errors",
                "warnings",
                "requires_manual_review",
                "run_status",
                "validation_status",
                "manual_review",
                "completion_blockers",
                "screenshot_policy",
            ):
                if report.get(field) != canonical_report.get(field):
                    errors.append(f"capture_report_mismatch:{field}")
    if manifest is None:
        errors.append("capture_manifest_missing")
    else:
        manifest_shape_error = canonical_manifest_shape_error(
            manifest,
            expected_run_id=expected_run_id,
            expected_task="capture-adapter",
        )
        if manifest_shape_error:
            errors.append(f"capture_manifest_shape:{manifest_shape_error}")
        if manifest.get("skill") != "page-to-md":
            errors.append("capture_manifest_skill_mismatch")
        if manifest.get("run_status") not in {"complete", "partial"}:
            errors.append(f"capture_manifest_status_invalid:{manifest.get('run_status')}")
        if manifest.get("validation_status") != "passed":
            errors.append("capture_manifest_validation_not_passed")
        errors.extend(f"capture_{error}" for error in validate_manifest_status(manifest))
        errors.extend(f"capture_{error}" for error in validate_manifest_paths(run_dir, manifest))
        evidence = manifest.get("evidence") if isinstance(manifest.get("evidence"), list) else []
        capture_records = [
            item
            for item in evidence
            if isinstance(item, dict)
            and item.get("type") == "page_capture"
            and item.get("path") == "capture/page_capture.json"
        ]
        if not capture_records:
            errors.append("capture_manifest_page_capture_evidence_missing")
        validation = manifest.get("validation") if isinstance(manifest.get("validation"), dict) else {}
        if validation.get("report_path") != "validation/capture-validation-report.json":
            errors.append("capture_manifest_report_path_mismatch")
        if report is not None:
            for field in (
                "run_status",
                "validation_status",
                "requires_manual_review",
                "manual_review",
                "completion_blockers",
                "screenshot_policy",
            ):
                if manifest.get(field) != report.get(field):
                    errors.append(f"capture_manifest_report_mismatch:{field}")
            if validation.get("schema_valid") is not (report.get("status") == "pass"):
                errors.append("capture_manifest_schema_valid_mismatch")
        if capture is not None:
            assets = capture.get("assets") if isinstance(capture.get("assets"), dict) else {}
            screenshots = assets.get("screenshots") if isinstance(assets.get("screenshots"), list) else []
            manifest_screenshot_paths = {
                str(item.get("path"))
                for item in evidence
                if isinstance(item, dict) and item.get("type") == "screenshot" and item.get("path")
            }
            for item in screenshots:
                raw_path = item if isinstance(item, str) else item.get("path") if isinstance(item, dict) else None
                if raw_path and f"capture/{raw_path}" not in manifest_screenshot_paths:
                    errors.append(f"capture_manifest_screenshot_evidence_missing:{raw_path}")
    if returncode != 0:
        errors.append(f"capture_process_returncode:{returncode}")
    return list(dict.fromkeys(errors))


def _capture_screenshot_evidence(run_dir: Path) -> list[dict[str, Any]]:
    capture_path = resolve_run_relative(run_dir, "capture/page_capture.json", must_exist=True)
    capture = read_json(capture_path)
    if not isinstance(capture, dict):
        raise ValueError("capture/page_capture.json must be a JSON object")
    assets = capture.get("assets") if isinstance(capture.get("assets"), dict) else {}
    screenshots = assets.get("screenshots") if isinstance(assets.get("screenshots"), list) else []
    evidence: list[dict[str, Any]] = []
    for index, item in enumerate(screenshots, start=1):
        raw_path = item if isinstance(item, str) else item.get("path") if isinstance(item, dict) else None
        if not isinstance(raw_path, str) or not raw_path:
            raise ValueError(f"capture screenshot {index} path is invalid")
        manifest_path = f"capture/{raw_path}"
        screenshot_path = resolve_run_relative(run_dir, manifest_path, must_exist=True)
        if not screenshot_file_is_valid(screenshot_path):
            raise ValueError(f"capture screenshot is not a supported image: {manifest_path}")
        evidence.append(
            {
                "id": f"SS{index:03d}",
                "type": "screenshot",
                "path": manifest_path,
                "captured_at": item.get("captured_at") if isinstance(item, dict) else capture.get("captured_at"),
                "sha256": _sha256_file(screenshot_path),
            }
        )
    policy = capture.get("screenshot_policy") if isinstance(capture.get("screenshot_policy"), dict) else {}
    if policy.get("status") == "required_and_present" and not evidence:
        raise ValueError("required screenshot evidence is missing")
    return evidence


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
        evidence.extend(_capture_screenshot_evidence(run_dir))
    manifest = {
        "run_id": run_id,
        "task": "capture-adapter",
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
    write_json(resolve_run_relative(run_dir, CAPTURE_STAGE_MANIFEST_PATH), manifest)
    return manifest


def finalize_page_workflow_failure(
    run_dir: Path,
    *,
    run_id: str,
    failure_code: str,
    ownership_token: str,
) -> bool:
    if not page_workflow_ownership_matches(
        run_dir,
        run_id=run_id,
        ownership_token=ownership_token,
    ):
        return False
    if (run_dir / "manifest.json").exists():
        return False
    (run_dir / CONTINUATION_HANDOFF_PATH).unlink(missing_ok=True)
    stage_path = run_dir / CAPTURE_STAGE_MANIFEST_PATH
    report_path = run_dir / "validation" / "capture-validation-report.json"
    try:
        stage = read_json(stage_path) if stage_path.is_file() else {}
    except (OSError, ValueError):
        stage = {}
    try:
        report = read_json(report_path) if report_path.is_file() else {}
    except (OSError, ValueError):
        report = {}
    if not isinstance(stage, dict):
        stage = {}
    if not isinstance(report, dict):
        report = {}
    warnings = list(dict.fromkeys([str(item) for item in report.get("warnings", [])] + [failure_code]))
    blockers = list(
        dict.fromkeys(
            [str(item) for item in report.get("completion_blockers", [])]
            + [str(item) for item in report.get("errors", [])]
            + [failure_code]
        )
    )
    reason = {
        "code": failure_code,
        "message": failure_code.replace("_", " "),
        "severity": "blocking",
        "artifact": "validation/capture-validation-report.json",
    }
    failed_report = {
        **report,
        "schema_version": str(report.get("schema_version") or "1.0"),
        "status": "fail",
        "errors": blockers,
        "warnings": warnings,
        "requires_manual_review": True,
        "run_status": "aborted_by_policy"
        if stage.get("run_status") == "aborted_by_policy" or report.get("run_status") == "aborted_by_policy"
        else "failed",
        "validation_status": "failed",
        "manual_review": {"required": True, "severity": "blocking", "reasons": [reason]},
        "completion_blockers": blockers,
        "screenshot_policy": report.get("screenshot_policy")
        or stage.get("screenshot_policy")
        or {"required": False, "reason": "workflow_failed", "status": "capture_failed"},
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(report_path, failed_report)
    evidence = [dict(item) for item in stage.get("evidence", []) if isinstance(item, dict)]
    capture_path = run_dir / "capture" / "page_capture.json"
    if capture_path.is_file() and not any(item.get("path") == "capture/page_capture.json" for item in evidence):
        evidence.append({"id": "C001", "type": "page_capture", "path": "capture/page_capture.json"})
    write_json(
        run_dir / "manifest.json",
        {
            "run_id": run_id,
            "task": "page-to-md",
            "started_at": stage.get("started_at") or utc_now(),
            "finished_at": utc_now(),
            "operator": "codex",
            "skill": "page-to-md",
            "inputs": stage.get("inputs") if isinstance(stage.get("inputs"), dict) else {},
            "artifacts": [],
            "evidence": evidence,
            "validation": {
                "schema_valid": False,
                "warnings": len(warnings),
                "requires_manual_review": True,
                "report_path": "validation/capture-validation-report.json",
            },
            "warnings": warnings,
            "requires_manual_review": True,
            "run_status": failed_report["run_status"],
            "validation_status": "failed",
            "manual_review": failed_report["manual_review"],
            "completion_blockers": blockers,
            "screenshot_policy": failed_report["screenshot_policy"],
        },
    )
    return True


def write_capture_warnings(path: Path, warnings: list[str]) -> None:
    if not warnings:
        write_text(path, "No warnings.\n")
        return
    lines = ["# Capture Warnings", ""]
    lines.extend(f"- {warning}" for warning in warnings)
    write_text(path, "\n".join(lines) + "\n")
