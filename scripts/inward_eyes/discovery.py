from __future__ import annotations

import ipaddress
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from inward_eyes.research import source_dir_name
from inward_eyes.paths import resolve_run_relative

DEFAULT_MAX_SOURCES = 5
HARD_MAX_SOURCES = 20
DISCOVERY_MODES = {"candidate_list", "search_results"}
PROMPT_INJECTION_PATTERNS = (
    "ignore previous instructions",
    "ignore all previous instructions",
    "disregard previous instructions",
    "send cookies",
    "reveal your system prompt",
)


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _strings(value: Any) -> list[str]:
    return [str(item).strip() for item in _as_list(value) if str(item).strip()]


def _normalize_domain(value: str) -> str:
    raw = value.strip().lower()
    if not raw:
        return ""
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    return (parsed.hostname or raw).strip(".").lower()


def _hostname(raw_url: str) -> str:
    return (urlparse(raw_url).hostname or "").strip(".").lower()


def _domain_matches(hostname: str, domain: str) -> bool:
    domain = _normalize_domain(domain)
    return hostname == domain or hostname.endswith(f".{domain}")


def _public_url_error(raw_url: str) -> str | None:
    parsed = urlparse(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return "public_http_url_required"
    hostname = parsed.hostname.lower()
    if hostname in {"localhost", "127.0.0.1", "::1"} or hostname.endswith(".local"):
        return "public_url_required"
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return None
    if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved:
        return "public_url_required"
    return None


def _prompt_injection_present(*values: Any) -> bool:
    haystack = "\n".join(str(value or "") for value in values).lower()
    return any(pattern in haystack for pattern in PROMPT_INJECTION_PATTERNS)


def _int_value(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _recency_error(candidate: dict[str, Any], recency: Any) -> str | None:
    if not recency:
        return None
    if isinstance(recency, str):
        return None
    if not isinstance(recency, dict):
        return "recency_invalid"
    required = bool(recency.get("required"))
    published_at = str(candidate.get("published_at") or "").strip()
    if required and not published_at:
        return "recency_required_missing_published_at"
    published_after = str(recency.get("published_after") or "").strip()
    if published_after and published_at and published_at < published_after:
        return "recency_before_required_window"
    return None


def discovery_scope_errors(spec: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    question = str(spec.get("research_question") or spec.get("question") or "").strip()
    if not question:
        errors.append("research_question_required")

    try:
        max_sources = int(spec.get("max_sources") or DEFAULT_MAX_SOURCES)
    except (TypeError, ValueError):
        max_sources = 0
    if max_sources < 1:
        errors.append("max_sources_must_be_positive")
    if max_sources > HARD_MAX_SOURCES:
        errors.append("max_sources_hard_limit_exceeded")

    discovery_mode = str(spec.get("discovery_mode") or "candidate_list")
    if discovery_mode not in DISCOVERY_MODES:
        errors.append(f"discovery_mode_invalid:{discovery_mode}")

    allowed_domains = _strings(spec.get("allowed_domains"))
    allowed_types = _strings(spec.get("allowed_source_types"))
    if not allowed_domains and not allowed_types:
        errors.append("scope_requires_allowed_domains_or_source_types")

    if not _strings(spec.get("search_queries")):
        errors.append("search_queries_required")

    if bool(spec.get("allow_recursive_crawling")) or bool(spec.get("recursive_links_followed")):
        errors.append("recursive_crawling_forbidden")

    return errors


def _candidate_sort_key(item: tuple[int, dict[str, Any]]) -> tuple[int, int]:
    index, candidate = item
    rank = candidate.get("rank")
    try:
        rank_value = int(rank)
    except (TypeError, ValueError):
        rank_value = index
    return rank_value, index


def _candidate_rejection_reasons(
    candidate: dict[str, Any],
    *,
    allowed_domains: list[str],
    allowed_source_types: list[str],
    excluded_domains: list[str],
    excluded_source_types: list[str],
    recency: Any,
) -> list[str]:
    reasons: list[str] = []
    url = str(candidate.get("url") or "").strip()
    if not url:
        reasons.append("candidate_url_missing")
        return reasons
    public_error = _public_url_error(url)
    if public_error:
        reasons.append(public_error)

    hostname = _hostname(url)
    if allowed_domains and not any(_domain_matches(hostname, domain) for domain in allowed_domains):
        reasons.append("domain_not_allowed")
    if excluded_domains and any(_domain_matches(hostname, domain) for domain in excluded_domains):
        reasons.append("domain_excluded")

    source_type = str(candidate.get("source_type") or "web_page")
    if allowed_source_types and source_type not in allowed_source_types:
        reasons.append("source_type_not_allowed")
    if excluded_source_types and source_type in excluded_source_types:
        reasons.append("source_type_excluded")

    if candidate.get("requires_login"):
        reasons.append("login_required_source_forbidden")
    if candidate.get("followed_link") or _int_value(candidate.get("discovery_depth")) > 0:
        reasons.append("recursive_link_candidate_forbidden")
    if _prompt_injection_present(candidate.get("title"), candidate.get("snippet")):
        reasons.append("prompt_injection_text_present")
    recency_reason = _recency_error(candidate, recency)
    if recency_reason:
        reasons.append(recency_reason)
    if candidate.get("selected") is False or candidate.get("approved") is False:
        reasons.append("candidate_not_selected")
    return reasons


def build_discovery_log(spec: dict[str, Any], generated_at: str) -> tuple[dict[str, Any], list[str]]:
    question = str(spec.get("research_question") or spec.get("question") or "").strip()
    max_sources = int(spec.get("max_sources") or DEFAULT_MAX_SOURCES)
    allowed_domains = _strings(spec.get("allowed_domains"))
    allowed_source_types = _strings(spec.get("allowed_source_types"))
    excluded_domains = _strings(spec.get("excluded_domains"))
    excluded_source_types = _strings(spec.get("excluded_source_types"))
    search_queries = _strings(spec.get("search_queries"))
    rationale_required = bool(spec.get("selection_rationale_required", True))
    recency = spec.get("recency")
    candidates = [item for item in _as_list(spec.get("candidates") or spec.get("candidate_sources")) if isinstance(item, dict)]

    selected: list[dict[str, Any]] = []
    candidate_records: list[dict[str, Any]] = []
    errors = discovery_scope_errors(spec)
    accepted_count = 0

    for output_index, (input_index, candidate) in enumerate(sorted(enumerate(candidates, start=1), key=_candidate_sort_key), start=1):
        url = str(candidate.get("url") or "").strip()
        hostname = _hostname(url)
        source_type = str(candidate.get("source_type") or "web_page")
        query = str(candidate.get("query") or candidate.get("search_query") or (search_queries[0] if search_queries else "")).strip()
        rationale = str(candidate.get("selection_rationale") or candidate.get("rationale") or "").strip()
        reasons = _candidate_rejection_reasons(
            candidate,
            allowed_domains=allowed_domains,
            allowed_source_types=allowed_source_types,
            excluded_domains=excluded_domains,
            excluded_source_types=excluded_source_types,
            recency=recency,
        )
        if errors:
            reasons.extend(errors)
        if accepted_count >= max_sources:
            reasons.append("max_sources_reached")
        if rationale_required and not rationale and not reasons:
            reasons.append("selection_rationale_missing")

        status = "rejected" if reasons or errors else "accepted"
        source_id = None
        if status == "accepted":
            accepted_count += 1
            source_id = str(candidate.get("source_id") or f"S{accepted_count:03d}")
            selected.append(
                {
                    "source_id": source_id,
                    "candidate_id": f"D{output_index:03d}",
                    "url": url,
                    "title": candidate.get("title") or candidate.get("page_title") or url,
                    "source_type": source_type,
                    "domain": hostname,
                    "selection_rationale": rationale,
                }
            )

        reason = "; ".join(dict.fromkeys(reasons)) if reasons else f"selected: {rationale}"
        candidate_records.append(
            {
                "candidate_id": f"D{output_index:03d}",
                "input_index": input_index,
                "query": query,
                "url": url,
                "domain": hostname,
                "title": candidate.get("title") or candidate.get("page_title"),
                "snippet": candidate.get("snippet"),
                "source_type": source_type,
                "page_type": candidate.get("page_type") or "unknown",
                "status": status,
                "reason": reason,
                "selection_rationale": rationale if status == "accepted" else None,
                "timestamp": generated_at,
                "rank": candidate.get("rank") or output_index,
                "selected_source_id": source_id,
            }
        )

    if not selected and not errors:
        errors.append("no_sources_selected")

    log = {
        "schema_version": "1.0",
        "task_type": "browser-research-discovery",
        "research_question": question,
        "discovery_mode": str(spec.get("discovery_mode") or "candidate_list"),
        "max_sources": max_sources,
        "hard_max_sources": HARD_MAX_SOURCES,
        "allowed_domains": allowed_domains,
        "allowed_source_types": allowed_source_types,
        "excluded_domains": excluded_domains,
        "excluded_source_types": excluded_source_types,
        "recency": recency,
        "search_queries": search_queries,
        "selection_rationale_required": rationale_required,
        "public_only": True,
        "recursive_links_followed": False,
        "generated_at": generated_at,
        "candidates": candidate_records,
        "selected_sources": selected,
        "warnings": [],
    }
    return log, errors


def render_discovery_log(log: dict[str, Any]) -> str:
    lines = [
        "# Discovery Log",
        "",
        f"- Research question: {log.get('research_question') or 'missing'}",
        f"- Mode: {log.get('discovery_mode') or 'missing'}",
        f"- Max sources: {log.get('max_sources')} (hard max {log.get('hard_max_sources')})",
        f"- Public only: {log.get('public_only')}",
        f"- Recursive links followed: {log.get('recursive_links_followed')}",
        "",
        "## Candidates",
        "",
        "| Candidate | Query | Status | Source | Reason |",
        "| --- | --- | --- | --- | --- |",
    ]
    for candidate in log.get("candidates") or []:
        title = str(candidate.get("title") or candidate.get("url") or "Untitled").replace("|", "\\|")
        query = str(candidate.get("query") or "").replace("|", "\\|")
        reason = str(candidate.get("reason") or "").replace("|", "\\|")
        source = f"{title} ({candidate.get('url') or 'missing URL'})".replace("|", "\\|")
        lines.append(
            f"| {candidate.get('candidate_id')} | {query} | {candidate.get('status')} | {source} | {reason} |"
        )
    lines.extend(["", "## Selected Sources", ""])
    selected_sources = log.get("selected_sources") or []
    if not selected_sources:
        lines.append("No selected sources.")
    else:
        for source in selected_sources:
            lines.append(
                f"- {source.get('source_id')}: {source.get('title') or source.get('url')} "
                f"- {source.get('selection_rationale')}"
            )
    return "\n".join(lines).rstrip() + "\n"


def _review_reasons(codes: list[str], severity: str, artifact: str) -> list[dict[str, str]]:
    return [{"code": code, "message": code.replace("_", " "), "severity": severity, "artifact": artifact} for code in codes]


def _status_fields(errors: list[str], warnings: list[str], manual_review: bool) -> dict[str, Any]:
    status = "fail" if errors else "pass"
    if errors:
        run_status = "failed"
        severity = "blocking"
    elif manual_review:
        run_status = "partial"
        severity = "warning"
    else:
        run_status = "complete"
        severity = "info"
    reasons = _review_reasons(errors, "blocking", "validation/discovery-validation-report.json")
    reasons += _review_reasons(warnings if manual_review else [], "warning", "validation/discovery-validation-report.json")
    return {
        "schema_version": "1.0",
        "status": status,
        "errors": errors,
        "warnings": list(dict.fromkeys(warnings)),
        "requires_manual_review": manual_review or bool(errors),
        "run_status": run_status,
        "validation_status": "passed" if status == "pass" else "failed",
        "manual_review": {
            "required": manual_review or bool(errors),
            "severity": severity,
            "reasons": reasons,
        },
        "completion_blockers": errors,
        "screenshot_policy": {"required": False, "reason": "per_source_policy", "status": "not_required"},
    }


def _load_json(path: Path, errors: list[str], run_dir: Path) -> dict[str, Any] | None:
    relative_path = path.relative_to(run_dir).as_posix()
    if not path.exists():
        errors.append(f"missing_file:{relative_path}")
        return None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"invalid_json:{relative_path}:{exc.__class__.__name__}")
        return None
    if not isinstance(loaded, dict):
        errors.append(f"json_object_required:{relative_path}")
        return None
    if not loaded:
        errors.append(f"json_object_empty:{relative_path}")
        return None
    return loaded


def _load_run_manifest(run_dir: Path, errors: list[str]) -> dict[str, Any] | None:
    try:
        manifest_path = resolve_run_relative(run_dir, "manifest.json", must_exist=True)
    except FileNotFoundError:
        errors.append("missing_file:manifest.json")
        return None
    except ValueError:
        errors.append("manifest.path_invalid:manifest.json")
        return None
    return _load_json(manifest_path, errors, run_dir)


def validate_research_discovery_run(
    run_dir: Path,
    manifest_override: dict[str, Any] | None = None,
    *,
    pending_manifest_paths: set[str] | None = None,
    skip_manifest_validation: bool = False,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    manual_review = False

    log_path = run_dir / "artifacts" / "discovery-log.json"
    log_md_path = run_dir / "artifacts" / "discovery-log.md"
    claims_path = run_dir / "artifacts" / "claims.json"
    manifest_path = run_dir / "manifest.json"

    log = _load_json(log_path, errors, run_dir) or {}
    claims_doc = _load_json(claims_path, errors, run_dir) or {}
    manifest: dict[str, Any] | None = None
    if not skip_manifest_validation:
        manifest = manifest_override if manifest_override is not None else _load_run_manifest(run_dir, errors)

    if not log_md_path.exists():
        errors.append("missing_file:artifacts/discovery-log.md")

    for field_name in (
        "research_question",
        "discovery_mode",
        "max_sources",
        "allowed_domains",
        "allowed_source_types",
        "search_queries",
        "candidates",
        "selected_sources",
    ):
        if field_name not in log:
            errors.append(f"discovery_log.{field_name}_missing")

    max_sources = _int_value(log.get("max_sources"))
    if max_sources < 1:
        errors.append("discovery.max_sources_must_be_positive")
    if max_sources > HARD_MAX_SOURCES:
        errors.append("discovery.max_sources_hard_limit_exceeded")
    if log.get("public_only") is not True:
        errors.append("discovery.public_only_required")
    if log.get("recursive_links_followed"):
        errors.append("discovery.recursive_links_followed_forbidden")
    if not (log.get("allowed_domains") or log.get("allowed_source_types")):
        errors.append("discovery.scope_requires_allowed_domains_or_source_types")
    if not log.get("search_queries"):
        errors.append("discovery.search_queries_required")

    candidates = log.get("candidates") if isinstance(log.get("candidates"), list) else []
    selected_sources = log.get("selected_sources") if isinstance(log.get("selected_sources"), list) else []
    accepted_candidates = [candidate for candidate in candidates if isinstance(candidate, dict) and candidate.get("status") == "accepted"]
    if len(selected_sources) > max_sources:
        errors.append(f"discovery.selected_source_count_exceeds_max:{len(selected_sources)}>{max_sources}")
    if len(accepted_candidates) != len(selected_sources):
        errors.append("discovery.accepted_candidate_selected_source_mismatch")

    claims_sources = claims_doc.get("sources") if isinstance(claims_doc.get("sources"), list) else []
    claims_source_by_id = {
        str(source.get("source_id")): source
        for source in claims_sources
        if isinstance(source, dict) and source.get("source_id")
    }
    selected_by_id = {
        str(source.get("source_id")): source
        for source in selected_sources
        if isinstance(source, dict) and source.get("source_id")
    }

    for candidate in candidates:
        if not isinstance(candidate, dict):
            errors.append("discovery.candidate_not_object")
            continue
        candidate_id = str(candidate.get("candidate_id") or "unknown")
        for field_name in ("query", "url", "status", "reason", "timestamp"):
            if not candidate.get(field_name):
                errors.append(f"discovery.candidate.{candidate_id}.{field_name}_missing")
        status = candidate.get("status")
        if status not in {"accepted", "rejected"}:
            errors.append(f"discovery.candidate.{candidate_id}.status_invalid:{status}")
        url = str(candidate.get("url") or "")
        public_error = _public_url_error(url)
        if public_error and status == "accepted":
            errors.append(f"discovery.accepted_non_public_source:{candidate_id}:{public_error}")
        if candidate.get("followed_link") or _int_value(candidate.get("discovery_depth")) > 0:
            errors.append(f"discovery.recursive_candidate:{candidate_id}")
        if _prompt_injection_present(candidate.get("title"), candidate.get("snippet")) and status == "accepted":
            errors.append(f"discovery.prompt_injection_candidate_accepted:{candidate_id}")
        if status == "accepted" and not candidate.get("selection_rationale"):
            errors.append(f"discovery.selection_rationale_missing:{candidate_id}")

    for source_id, selected in selected_by_id.items():
        if source_id not in claims_source_by_id:
            errors.append(f"discovery.selected_source_missing_from_claims:{source_id}")
        try:
            source_directory = source_dir_name(source_id)
        except ValueError:
            errors.append(f"discovery.selected_source_id_invalid:{source_id}")
            source_record = None
        else:
            source_record_path = run_dir / "evidence" / source_directory / "source_record.json"
            source_record = _load_json(source_record_path, errors, run_dir)
        if source_record:
            if source_record.get("source_id") != source_id:
                errors.append(f"discovery.source_record_id_mismatch:{source_id}")
            if source_record.get("url") != selected.get("url"):
                errors.append(f"discovery.source_record_url_mismatch:{source_id}")
        if not selected.get("selection_rationale"):
            errors.append(f"discovery.selected_source_rationale_missing:{source_id}")

    if not skip_manifest_validation and manifest is not None:
        from inward_eyes.validation import (
            canonical_manifest_shape_error,
            validate_manifest_paths,
            validate_manifest_status,
        )

        shape_error = canonical_manifest_shape_error(
            manifest,
            expected_run_id=run_dir.name,
            expected_task="browser-research",
        )
        if shape_error:
            errors.append(f"manifest.shape_invalid:{shape_error}")
        errors.extend(validate_manifest_paths(run_dir, manifest, allow_missing_paths=pending_manifest_paths))
        errors.extend(validate_manifest_status(manifest))
        manifest_paths = {
            item.get("path")
            for section in ("artifacts", "evidence")
            for item in (manifest.get(section) or [])
            if isinstance(item, dict)
        }
        for required_path in (
            "artifacts/discovery-log.json",
            "artifacts/discovery-log.md",
            "validation/discovery-validation-report.json",
        ):
            if required_path not in manifest_paths and required_path != "validation/discovery-validation-report.json":
                errors.append(f"discovery.manifest_path_missing:{required_path}")

    return {
        **_status_fields(errors, warnings, manual_review),
        "candidate_count": len(candidates),
        "selected_source_count": len(selected_sources),
        "max_sources": max_sources,
    }
