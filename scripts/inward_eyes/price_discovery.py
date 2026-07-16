from __future__ import annotations

import csv
import ipaddress
import io
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from inward_eyes.price import MIN_MATCH_CONFIDENCE
from inward_eyes.paths import resolve_run_relative

DEFAULT_MAX_CANDIDATES_PER_PLATFORM = 3
HARD_MAX_TOTAL_CANDIDATES = 20
ASSESSMENT_METHOD = "approved_candidate_discovery"
APPROVAL_POLICY_AUTO_HIGH_CONFIDENCE = "auto_high_confidence"
APPROVAL_POLICY_REVIEW_ONLY = "review_only"
APPROVAL_POLICIES = {APPROVAL_POLICY_AUTO_HIGH_CONFIDENCE, APPROVAL_POLICY_REVIEW_ONLY}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _strings(value: Any) -> list[str]:
    return [str(item).strip() for item in _as_list(value) if str(item).strip()]


def _number_or_none(value: Any) -> float | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = "".join(ch for ch in value if ch.isdigit() or ch in ".-")
        if cleaned:
            try:
                return float(cleaned)
            except ValueError:
                return None
    return None


def _int_value(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


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


def _target_product(spec: dict[str, Any]) -> str:
    target = spec.get("target_product")
    if isinstance(target, dict):
        return str(target.get("target_name") or target.get("name") or "").strip()
    return str(target or "").strip()


def _required_specs(spec: dict[str, Any]) -> dict[str, Any]:
    if isinstance(spec.get("required_specs"), dict):
        return spec["required_specs"]
    target = spec.get("target_product")
    if isinstance(target, dict) and isinstance(target.get("required_specs"), dict):
        return target["required_specs"]
    product = spec.get("product")
    if isinstance(product, dict) and isinstance(product.get("required_specs"), dict):
        return product["required_specs"]
    return {}


def _missing_or_mismatched_specs(required_specs: dict[str, Any], actual_specs: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    for key, expected in required_specs.items():
        actual = actual_specs.get(key)
        if actual is None:
            flags.append(f"missing_spec:{key}")
        elif str(actual).strip().lower() != str(expected).strip().lower():
            flags.append(f"spec_mismatch:{key}")
    return flags


def discovery_scope_errors(spec: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not _target_product(spec):
        errors.append("target_product_required")
    if not _required_specs(spec):
        errors.append("required_specs_required")
    if not _strings(spec.get("allowed_platforms")):
        errors.append("allowed_platforms_required")
    if not _strings(spec.get("allowed_domains")):
        errors.append("allowed_domains_required")
    if not str(spec.get("region") or "").strip():
        errors.append("region_required")
    if not str(spec.get("currency") or "").strip():
        errors.append("currency_required")
    max_per_platform = _int_value(spec.get("max_candidates_per_platform"), DEFAULT_MAX_CANDIDATES_PER_PLATFORM)
    if max_per_platform < 1:
        errors.append("max_candidates_per_platform_must_be_positive")
    raw_candidates = _candidate_inputs(spec)
    if len(raw_candidates) > HARD_MAX_TOTAL_CANDIDATES:
        errors.append(f"candidate.total_cap_exceeded:{len(raw_candidates)}>{HARD_MAX_TOTAL_CANDIDATES}")
    policy = str(spec.get("approval_policy") or APPROVAL_POLICY_REVIEW_ONLY)
    if policy not in APPROVAL_POLICIES:
        errors.append(f"approval_policy_invalid:{policy}")
    return errors


def _candidate_inputs(spec: dict[str, Any]) -> list[dict[str, Any]]:
    raw_candidates = spec.get("candidates") or spec.get("candidate_products")
    return [item for item in _as_list(raw_candidates) if isinstance(item, dict)]


def _candidate_url(candidate: dict[str, Any]) -> str:
    return str(candidate.get("product_url") or candidate.get("url") or "").strip()


def _candidate_specs(candidate: dict[str, Any]) -> dict[str, Any]:
    visible_specs = candidate.get("visible_specs")
    if isinstance(visible_specs, dict):
        return visible_specs
    identity = candidate.get("product_identity")
    if isinstance(identity, dict) and isinstance(identity.get("specs"), dict):
        return identity["specs"]
    specs = candidate.get("specs")
    return specs if isinstance(specs, dict) else {}


def _seller_blocked(candidate: dict[str, Any], spec: dict[str, Any]) -> bool:
    seller = str(candidate.get("seller") or "").strip().lower()
    excluded = {item.lower() for item in _strings(spec.get("excluded_sellers"))}
    preferences = spec.get("seller_preferences") if isinstance(spec.get("seller_preferences"), dict) else {}
    excluded.update(item.lower() for item in _strings(preferences.get("excluded_sellers")))
    return bool(seller and seller in excluded)


def _condition_mismatch(candidate: dict[str, Any], spec: dict[str, Any]) -> bool:
    expected = str(spec.get("required_condition") or "").strip().lower()
    preferences = spec.get("seller_preferences") if isinstance(spec.get("seller_preferences"), dict) else {}
    allowed = {item.lower() for item in _strings(preferences.get("allowed_conditions"))}
    condition = str(candidate.get("condition") or "").strip().lower()
    if expected and condition and condition != expected:
        return True
    if allowed and condition and condition not in allowed:
        return True
    return False


def normalize_candidates(spec: dict[str, Any], generated_at: str) -> dict[str, Any]:
    target_product = _target_product(spec)
    required_specs = _required_specs(spec)
    allowed_platforms = _strings(spec.get("allowed_platforms"))
    allowed_domains = _strings(spec.get("allowed_domains"))
    max_per_platform = _int_value(spec.get("max_candidates_per_platform"), DEFAULT_MAX_CANDIDATES_PER_PLATFORM)
    approval_policy = str(spec.get("approval_policy") or APPROVAL_POLICY_REVIEW_ONLY)
    scope_errors = discovery_scope_errors(spec)
    seen_urls: set[str] = set()
    per_platform_counts: dict[str, int] = {}
    candidate_records: list[dict[str, Any]] = []

    for index, candidate in enumerate(_candidate_inputs(spec), start=1):
        candidate_id = str(candidate.get("candidate_id") or f"K{index:03d}")
        platform = str(candidate.get("platform") or "").strip()
        url = _candidate_url(candidate)
        hostname = _hostname(url)
        specs = _candidate_specs(candidate)
        confidence = float(_number_or_none(candidate.get("match_confidence")) or 0)
        mismatch_flags = _strings(candidate.get("mismatch_flags"))
        for flag in _missing_or_mismatched_specs(required_specs, specs):
            if flag not in mismatch_flags:
                mismatch_flags.append(flag)
        rejection_reasons: list[str] = []
        manual_review_reasons: list[str] = []
        if scope_errors:
            rejection_reasons.extend(scope_errors)

        public_error = _public_url_error(url)
        if public_error:
            rejection_reasons.append(public_error)
        if allowed_platforms and platform not in allowed_platforms:
            rejection_reasons.append("platform_not_allowed")
        if allowed_domains and not any(_domain_matches(hostname, domain) for domain in allowed_domains):
            rejection_reasons.append("domain_not_allowed")
        if bool(candidate.get("is_recommendation")) or str(candidate.get("source_surface") or "") == "recommendation":
            rejection_reasons.append("recommendation_link_ignored")
        if candidate.get("requires_login"):
            rejection_reasons.append("login_required_discovery_forbidden")
        if candidate.get("followed_link") or _int_value(candidate.get("discovery_depth")) > 0:
            rejection_reasons.append("recursive_link_candidate_forbidden")
        normalized_url = url.lower().rstrip("/")
        if normalized_url in seen_urls:
            rejection_reasons.append("duplicate_product_url")
        elif normalized_url:
            seen_urls.add(normalized_url)
        per_platform_counts[platform] = per_platform_counts.get(platform, 0) + 1
        if platform and per_platform_counts[platform] > max_per_platform:
            rejection_reasons.append("max_candidates_per_platform_exceeded")

        if mismatch_flags:
            manual_review_reasons.append("required_spec_mismatch")
        if confidence < MIN_MATCH_CONFIDENCE:
            manual_review_reasons.append("low_match_confidence")
        if _seller_blocked(candidate, spec):
            manual_review_reasons.append("seller_excluded")
        if _condition_mismatch(candidate, spec):
            manual_review_reasons.append("condition_mismatch")
        if not candidate.get("selection_rationale"):
            manual_review_reasons.append("selection_rationale_missing")

        candidate_approved = bool(candidate.get("approved_for_quote_capture"))
        auto_approved = (
            approval_policy == APPROVAL_POLICY_AUTO_HIGH_CONFIDENCE
            and not rejection_reasons
            and not manual_review_reasons
            and confidence >= MIN_MATCH_CONFIDENCE
        )
        approved_for_quote_capture = candidate_approved or auto_approved
        requires_manual_review = bool(manual_review_reasons) and not candidate_approved
        if rejection_reasons:
            status = "rejected"
        elif approved_for_quote_capture:
            status = "approved_for_quote_capture"
        else:
            status = "needs_manual_review"
            requires_manual_review = True
            if "approval_required" not in manual_review_reasons:
                manual_review_reasons.append("approval_required")

        reason = "; ".join(dict.fromkeys(rejection_reasons or manual_review_reasons or ["approved"]))
        candidate_records.append(
            {
                "candidate_id": candidate_id,
                "assessment_method": ASSESSMENT_METHOD,
                "platform": platform,
                "domain": hostname,
                "product_url": url,
                "url": url,
                "visible_product_name": candidate.get("visible_product_name")
                or candidate.get("product_name")
                or candidate.get("page_title")
                or url,
                "visible_specs": specs,
                "seller": candidate.get("seller") or "unknown",
                "seller_type": candidate.get("seller_type") or "unknown",
                "condition": candidate.get("condition") or "unknown",
                "provisional_price": _number_or_none(candidate.get("provisional_price")),
                "currency": candidate.get("currency") or spec.get("currency"),
                "region": candidate.get("region") or spec.get("region"),
                "match_confidence": confidence,
                "mismatch_flags": list(dict.fromkeys(mismatch_flags)),
                "selection_rationale": candidate.get("selection_rationale"),
                "rejection_rationale": reason if status == "rejected" else None,
                "approval_rationale": reason if status == "approved_for_quote_capture" else None,
                "review_rationale": reason if status == "needs_manual_review" else None,
                "requires_manual_review": requires_manual_review,
                "approved_for_quote_capture": approved_for_quote_capture,
                "explicitly_approved": candidate_approved,
                "status": status,
                "timestamp": generated_at,
                "source_surface": candidate.get("source_surface") or "search_result",
                "raw_candidate_index": index,
            }
        )

    return {
        "schema_version": "1.0",
        "task_type": "price-candidate-discovery",
        "target_product": target_product,
        "required_specs": required_specs,
        "allowed_platforms": allowed_platforms,
        "allowed_domains": allowed_domains,
        "max_candidates_per_platform": max_per_platform,
        "hard_max_total_candidates": HARD_MAX_TOTAL_CANDIDATES,
        "region": spec.get("region"),
        "currency": spec.get("currency"),
        "excluded_sellers": _strings(spec.get("excluded_sellers")),
        "seller_preferences": spec.get("seller_preferences") if isinstance(spec.get("seller_preferences"), dict) else {},
        "approval_policy": approval_policy,
        "generated_at": generated_at,
        "candidates": candidate_records,
        "approved_candidate_urls": [
            candidate["product_url"] for candidate in candidate_records if candidate.get("approved_for_quote_capture")
        ],
        "warnings": _strings(spec.get("warnings")),
        "scope_errors": scope_errors,
    }


def render_candidates_csv(candidates: list[dict[str, Any]]) -> str:
    output = io.StringIO()
    fieldnames = [
        "candidate_id",
        "platform",
        "product_url",
        "visible_product_name",
        "seller",
        "condition",
        "provisional_price",
        "currency",
        "match_confidence",
        "mismatch_flags",
        "status",
        "requires_manual_review",
        "approved_for_quote_capture",
        "rationale",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for candidate in candidates:
        writer.writerow(
            {
                "candidate_id": candidate.get("candidate_id"),
                "platform": candidate.get("platform"),
                "product_url": candidate.get("product_url"),
                "visible_product_name": candidate.get("visible_product_name"),
                "seller": candidate.get("seller"),
                "condition": candidate.get("condition"),
                "provisional_price": candidate.get("provisional_price"),
                "currency": candidate.get("currency"),
                "match_confidence": candidate.get("match_confidence"),
                "mismatch_flags": ",".join(candidate.get("mismatch_flags") or []),
                "status": candidate.get("status"),
                "requires_manual_review": candidate.get("requires_manual_review"),
                "approved_for_quote_capture": candidate.get("approved_for_quote_capture"),
                "rationale": candidate.get("approval_rationale")
                or candidate.get("review_rationale")
                or candidate.get("rejection_rationale"),
            }
        )
    return output.getvalue()


def render_candidate_review(model: dict[str, Any]) -> str:
    lines = [
        "# Candidate Review",
        "",
        f"- Target product: {model.get('target_product') or 'missing'}",
        f"- Region: {model.get('region') or 'unknown'}",
        f"- Currency: {model.get('currency') or 'unknown'}",
        f"- Approval policy: {model.get('approval_policy')}",
        "",
        "| Candidate | Platform | Product | Match | Status | Rationale |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    for candidate in model.get("candidates") or []:
        rationale = (
            candidate.get("approval_rationale")
            or candidate.get("review_rationale")
            or candidate.get("rejection_rationale")
            or ""
        )
        lines.append(
            f"| {candidate.get('candidate_id')} | {candidate.get('platform') or 'unknown'} | "
            f"{candidate.get('visible_product_name') or candidate.get('product_url')} | "
            f"{float(candidate.get('match_confidence') or 0):.2f} | {candidate.get('status')} | {rationale} |"
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
    reasons = _review_reasons(errors, "blocking", "validation/candidate-validation-report.json")
    reasons += _review_reasons(warnings if manual_review else [], "warning", "validation/candidate-validation-report.json")
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
        "screenshot_policy": {"required": True, "reason": "ecommerce_product_pages", "status": "per_quote_policy"},
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


def validate_price_candidate_discovery_run(
    run_dir: Path,
    manifest_override: dict[str, Any] | None = None,
    *,
    pending_manifest_paths: set[str] | None = None,
    skip_manifest_validation: bool = False,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    manual_review = False

    candidates_path = run_dir / "artifacts" / "candidates.json"
    candidates_csv_path = run_dir / "artifacts" / "candidates.csv"
    review_path = run_dir / "artifacts" / "candidate-review.md"
    manifest_path = run_dir / "manifest.json"

    doc = _load_json(candidates_path, errors, run_dir) or {}
    manifest: dict[str, Any] | None = None
    if not skip_manifest_validation:
        manifest = manifest_override if manifest_override is not None else _load_run_manifest(run_dir, errors)
    errors.extend(str(item) for item in doc.get("scope_errors", []) if str(item).strip())

    if not candidates_csv_path.exists():
        errors.append("missing_file:artifacts/candidates.csv")
    if not review_path.exists():
        errors.append("missing_file:artifacts/candidate-review.md")

    for field_name in (
        "target_product",
        "required_specs",
        "allowed_platforms",
        "allowed_domains",
        "max_candidates_per_platform",
        "hard_max_total_candidates",
        "candidates",
    ):
        if field_name not in doc:
            errors.append(f"candidates.{field_name}_missing")

    candidates = doc.get("candidates") if isinstance(doc.get("candidates"), list) else []
    max_per_platform = _int_value(doc.get("max_candidates_per_platform"), DEFAULT_MAX_CANDIDATES_PER_PLATFORM)
    if len(candidates) > HARD_MAX_TOTAL_CANDIDATES:
        errors.append(f"candidate.total_cap_exceeded:{len(candidates)}>{HARD_MAX_TOTAL_CANDIDATES}")
    if max_per_platform < 1:
        errors.append("candidate.max_candidates_per_platform_invalid")

    allowed_platforms = set(str(item) for item in doc.get("allowed_platforms") or [])
    allowed_domains = [str(item) for item in doc.get("allowed_domains") or []]
    if not allowed_platforms:
        errors.append("candidate.allowed_platforms_required")
    if not allowed_domains:
        errors.append("candidate.allowed_domains_required")
    if not doc.get("target_product"):
        errors.append("candidate.target_product_required")
    if not isinstance(doc.get("required_specs"), dict) or not doc.get("required_specs"):
        errors.append("candidate.required_specs_required")
    if not doc.get("region"):
        errors.append("candidate.region_required")
    if not doc.get("currency"):
        errors.append("candidate.currency_required")

    seen_urls: set[str] = set()
    platform_counts: dict[str, int] = {}
    approved_count = 0
    for candidate in candidates:
        if not isinstance(candidate, dict):
            errors.append("candidate.not_object")
            continue
        candidate_id = str(candidate.get("candidate_id") or "unknown")
        for field_name in (
            "platform",
            "product_url",
            "visible_product_name",
            "visible_specs",
            "seller",
            "condition",
            "match_confidence",
            "mismatch_flags",
            "requires_manual_review",
            "status",
        ):
            if candidate.get(field_name) is None:
                errors.append(f"candidate.{candidate_id}.{field_name}_missing")
        if candidate.get("assessment_method") != ASSESSMENT_METHOD:
            errors.append(f"candidate.{candidate_id}.assessment_method_invalid")
        platform = str(candidate.get("platform") or "")
        platform_counts[platform] = platform_counts.get(platform, 0) + 1
        if platform_counts[platform] > max_per_platform:
            errors.append(f"candidate.per_platform_cap_exceeded:{platform}:{platform_counts[platform]}>{max_per_platform}")
        if allowed_platforms and platform not in allowed_platforms:
            errors.append(f"candidate.platform_outside_scope:{candidate_id}:{platform}")
        url = str(candidate.get("product_url") or "")
        public_error = _public_url_error(url)
        if public_error:
            errors.append(f"candidate.non_public_url:{candidate_id}:{public_error}")
        hostname = _hostname(url)
        if allowed_domains and not any(_domain_matches(hostname, domain) for domain in allowed_domains):
            errors.append(f"candidate.domain_outside_scope:{candidate_id}:{hostname}")
        normalized_url = url.lower().rstrip("/")
        if normalized_url in seen_urls and candidate.get("status") != "rejected":
            errors.append(f"candidate.duplicate_url_not_rejected:{candidate_id}")
        if normalized_url:
            seen_urls.add(normalized_url)
        if str(candidate.get("source_surface") or "") == "recommendation" and candidate.get("status") != "rejected":
            errors.append(f"candidate.recommendation_not_rejected:{candidate_id}")
        if candidate.get("status") == "rejected":
            if not candidate.get("rejection_rationale"):
                errors.append(f"candidate.rejection_rationale_missing:{candidate_id}")
            continue
        if not candidate.get("selection_rationale"):
            errors.append(f"candidate.selection_rationale_missing:{candidate_id}")
        if candidate.get("match_confidence", 0) < MIN_MATCH_CONFIDENCE:
            manual_review = True
            if not candidate.get("requires_manual_review"):
                errors.append(f"candidate.low_confidence_without_manual_review:{candidate_id}")
            if candidate.get("approved_for_quote_capture") and not candidate.get("explicitly_approved"):
                errors.append(f"candidate.low_confidence_auto_approved:{candidate_id}")
        if candidate.get("mismatch_flags"):
            manual_review = True
            if not candidate.get("requires_manual_review"):
                errors.append(f"candidate.mismatch_without_manual_review:{candidate_id}")
            if candidate.get("approved_for_quote_capture") and not candidate.get("explicitly_approved"):
                errors.append(f"candidate.mismatch_auto_approved:{candidate_id}")
        if candidate.get("requires_manual_review"):
            manual_review = True
        if candidate.get("approved_for_quote_capture"):
            approved_count += 1

    if not skip_manifest_validation and manifest is not None:
        from inward_eyes.validation import (
            canonical_manifest_shape_error,
            validate_manifest_paths,
            validate_manifest_status,
        )

        shape_error = canonical_manifest_shape_error(
            manifest,
            expected_run_id=run_dir.name,
            expected_task="price-compare",
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
            "artifacts/candidates.json",
            "artifacts/candidates.csv",
            "artifacts/candidate-review.md",
            "validation/candidate-validation-report.json",
        ):
            if required_path not in manifest_paths and required_path != "validation/candidate-validation-report.json":
                errors.append(f"candidate.manifest_path_missing:{required_path}")

    return {
        **_status_fields(errors, warnings, manual_review),
        "total_candidates": len(candidates),
        "approved_candidates": approved_count,
        "max_candidates_per_platform": max_per_platform,
        "hard_max_total_candidates": HARD_MAX_TOTAL_CANDIDATES,
    }
