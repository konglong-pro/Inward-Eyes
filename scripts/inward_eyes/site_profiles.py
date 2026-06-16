from __future__ import annotations

import fnmatch
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from inward_eyes.io import read_json


DEFAULT_PROFILE_PATH = Path(__file__).resolve().parents[2] / "profiles" / "site_profiles.json"


def load_site_profiles(path: Path | None = None) -> dict[str, Any]:
    profile_path = path or DEFAULT_PROFILE_PATH
    data = read_json(profile_path)
    if not isinstance(data, dict):
        raise ValueError("site profile file must contain an object")
    return data


def validate_site_profiles(data: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    profiles = data.get("profiles")
    if not isinstance(profiles, list) or not profiles:
        errors.append("SITE_PROFILES_EMPTY")
        profiles = []
    seen: set[str] = set()
    for profile in profiles:
        if not isinstance(profile, dict):
            errors.append("SITE_PROFILE_NOT_OBJECT")
            continue
        profile_id = str(profile.get("profile_id") or "")
        if not profile_id:
            errors.append("SITE_PROFILE_ID_MISSING")
        elif profile_id in seen:
            errors.append(f"SITE_PROFILE_DUPLICATE_ID:{profile_id}")
        seen.add(profile_id)
        for field in ("label", "page_types", "content_scope", "screenshot_policy", "risk_flags"):
            if field not in profile:
                errors.append(f"SITE_PROFILE_FIELD_MISSING:{profile_id}:{field}")
        if not isinstance(profile.get("page_types"), list) or not profile.get("page_types"):
            errors.append(f"SITE_PROFILE_PAGE_TYPES_EMPTY:{profile_id}")
        if not isinstance(profile.get("url_patterns"), list):
            warnings.append(f"SITE_PROFILE_URL_PATTERNS_MISSING:{profile_id}")
    return {
        "schema_version": "1.0",
        "status": "fail" if errors else "pass",
        "errors": errors,
        "warnings": warnings,
        "requires_manual_review": bool(errors or warnings),
        "run_status": "failed" if errors else "partial" if warnings else "complete",
        "validation_status": "failed" if errors else "passed",
        "manual_review": {
            "required": bool(errors or warnings),
            "severity": "blocking" if errors else "warning" if warnings else "info",
            "reasons": [
                {
                    "code": code,
                    "message": code.replace("_", " ").replace(":", ": "),
                    "severity": "blocking" if code in errors else "warning",
                    "artifact": "profiles/site_profiles.json",
                }
                for code in errors + warnings
            ],
        },
        "completion_blockers": errors,
    }


def _pattern_match(pattern: str, value: str) -> bool:
    if pattern.startswith("regex:"):
        return re.search(pattern.removeprefix("regex:"), value) is not None
    return fnmatch.fnmatch(value, pattern)


def match_site_profile(
    profiles_doc: dict[str, Any],
    *,
    url: str,
    page_type: str = "unknown",
    site_name: str | None = None,
) -> dict[str, Any]:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    url_text = url.lower()
    candidates = []
    for profile in profiles_doc.get("profiles", []):
        if not isinstance(profile, dict):
            continue
        score = 0
        if page_type in profile.get("page_types", []):
            score += 10
        for pattern in profile.get("domain_patterns", []):
            if _pattern_match(str(pattern).lower(), hostname):
                score += 8
        for pattern in profile.get("url_patterns", []):
            if _pattern_match(str(pattern).lower(), url_text):
                score += 4
        if site_name and str(site_name).lower() in [str(item).lower() for item in profile.get("site_names", [])]:
            score += 5
        if score:
            candidates.append((score, profile))
    if not candidates:
        fallback = next(
            (
                profile
                for profile in profiles_doc.get("profiles", [])
                if isinstance(profile, dict) and profile.get("profile_id") == "generic_public_page"
            ),
            None,
        )
        return {
            "schema_version": "1.0",
            "url": url,
            "page_type": page_type,
            "matched_profile_id": (fallback or {}).get("profile_id", "generic_public_page"),
            "confidence": 0.3,
            "profile": fallback or {},
            "warnings": ["SITE_PROFILE_GENERIC_FALLBACK"],
        }
    score, profile = sorted(candidates, key=lambda item: item[0], reverse=True)[0]
    return {
        "schema_version": "1.0",
        "url": url,
        "page_type": page_type,
        "matched_profile_id": profile.get("profile_id"),
        "confidence": min(0.95, 0.4 + score / 20),
        "profile": profile,
        "warnings": [],
    }


def render_site_profile_markdown(data: dict[str, Any], report: dict[str, Any]) -> str:
    lines = [
        "# Site Profiles",
        "",
        f"Status: `{report['status']}`",
        "",
        "| Profile | Page types | Evidence | Screenshot rule | Risks |",
        "| --- | --- | --- | --- | --- |",
    ]
    for profile in data.get("profiles", []):
        if not isinstance(profile, dict):
            continue
        evidence = ", ".join(profile.get("required_evidence", []))
        screenshot = profile.get("screenshot_policy", {}).get("rule", "unknown")
        risks = ", ".join(profile.get("risk_flags", []))
        lines.append(
            f"| {profile.get('profile_id')} | {', '.join(profile.get('page_types', []))} | "
            f"{evidence} | {screenshot} | {risks} |"
        )
    lines.append("")
    if report.get("errors"):
        lines.extend(["## Blockers", ""])
        lines.extend(f"- {error}" for error in report["errors"])
        lines.append("")
    if report.get("warnings"):
        lines.extend(["## Warnings", ""])
        lines.extend(f"- {warning}" for warning in report["warnings"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
