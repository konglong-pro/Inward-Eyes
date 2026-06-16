from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from inward_eyes.discovery import validate_research_discovery_run
from inward_eyes.price_discovery import validate_price_candidate_discovery_run

BOILERPLATE_PATTERNS = (
    "sign in",
    "subscribe",
    "recommended",
    "more like this",
    "advertisement",
    "cookie policy",
)
PRIVATE_DATA_WARNINGS = {
    "private_data_warning",
    "private_data_redacted",
    "private_data_detected",
}


def _field(data: dict[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _source_dir_name(source_id: str) -> str:
    if source_id.startswith("S") and source_id[1:].isdigit():
        return f"source-{int(source_id[1:]):03d}"
    return source_id.lower().replace("_", "-")


def _manual_review(required: bool, severity: str, reasons: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "required": required,
        "severity": severity,
        "reasons": reasons,
    }


def _status_fields(
    status: str,
    warnings: list[str],
    manual_review_required: bool,
    manual_review_reasons: list[dict[str, str]],
    completion_blockers: list[str],
) -> dict[str, Any]:
    if status == "fail":
        run_status = "failed"
        severity = "blocking"
    elif manual_review_required:
        run_status = "partial"
        severity = "warning"
    else:
        run_status = "complete"
        severity = "info"
    return {
        "run_status": run_status,
        "validation_status": "passed" if status == "pass" else "failed",
        "manual_review": _manual_review(
            manual_review_required or bool(completion_blockers),
            severity,
            manual_review_reasons,
        ),
        "completion_blockers": completion_blockers,
    }


def _review_reasons(codes: list[str], severity: str, artifact: str) -> list[dict[str, str]]:
    return [{"code": code, "message": code.replace("_", " "), "severity": severity, "artifact": artifact} for code in codes]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


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
        metadata_warnings = _field(metadata, "extraction.warnings") or []
        privacy = metadata.get("privacy") if isinstance(metadata.get("privacy"), dict) else {}
        if privacy.get("contains_private_data") or PRIVATE_DATA_WARNINGS.intersection(set(metadata_warnings)):
            manual_review = True
            if "private_data_warning" not in warnings:
                warnings.append("private_data_warning")
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
                if not screenshot_assets:
                    errors.append("screenshot_required_evidence_missing")

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
                candidate_path = run_dir / raw_path
                if not candidate_path.exists():
                    errors.append(f"manifest.{section}[{index}].path_missing_on_disk:{raw_path}")
                    continue
                if section == "evidence" and record.get("type") == "screenshot":
                    expected_sha = record.get("sha256")
                    if not expected_sha:
                        errors.append(f"manifest.evidence[{index}].sha256_missing:{raw_path}")
                    elif expected_sha != _sha256_file(candidate_path):
                        errors.append(f"manifest.evidence[{index}].sha256_mismatch:{raw_path}")

        manifest_source = _field(manifest, "inputs.source_url")
        if metadata and manifest_source and manifest_source != metadata["source"].get("url"):
            errors.append("manifest.inputs.source_url_mismatch")

    status = "fail" if errors else "pass"
    reasons = _review_reasons(errors, "blocking", "validation/validation-report.json") + _review_reasons(
        warnings if manual_review else [], "warning", "validation/validation-report.json"
    )
    return {
        "schema_version": "1.0",
        "status": status,
        "errors": errors,
        "warnings": warnings,
        "requires_manual_review": manual_review,
        "screenshot_policy": _field(metadata or {}, "extraction.screenshot_policy") or {"required": False, "reason": "unknown", "status": "not_required"},
        **_status_fields(status, warnings, manual_review, reasons, errors),
    }


def validate_browser_research_run(run_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    manual_review = False

    claims_path = run_dir / "artifacts" / "claims.json"
    report_path = run_dir / "artifacts" / "report.md"
    sources_csv_path = run_dir / "artifacts" / "sources.csv"
    source_notes_path = run_dir / "artifacts" / "source_notes.md"
    missing_sources_path = run_dir / "validation" / "missing-sources.md"
    manifest_path = run_dir / "manifest.json"

    def load(path: Path) -> dict[str, Any] | None:
        if not path.exists():
            errors.append(f"missing_file:{path.relative_to(run_dir).as_posix()}")
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"invalid_json:{path.relative_to(run_dir).as_posix()}:{exc}")
            return None

    claims_doc = load(claims_path)
    manifest = load(manifest_path)

    if not report_path.exists():
        errors.append("missing_file:artifacts/report.md")
        report_markdown = ""
    else:
        report_markdown = report_path.read_text(encoding="utf-8")

    if not source_notes_path.exists():
        errors.append("missing_file:artifacts/source_notes.md")

    if not missing_sources_path.exists():
        errors.append("missing_file:validation/missing-sources.md")

    csv_source_ids: set[str] = set()
    if not sources_csv_path.exists():
        errors.append("missing_file:artifacts/sources.csv")
    else:
        with sources_csv_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                errors.append("sources_csv.header_missing")
            else:
                for row in reader:
                    source_id = row.get("source_id")
                    if source_id:
                        csv_source_ids.add(source_id)

    sources = claims_doc.get("sources", []) if isinstance(claims_doc, dict) else []
    claims = claims_doc.get("claims", []) if isinstance(claims_doc, dict) else []
    if not isinstance(sources, list):
        errors.append("claims.sources_not_list")
        sources = []
    if not isinstance(claims, list):
        errors.append("claims.claims_not_list")
        claims = []

    source_ids: set[str] = set()
    source_by_id: dict[str, dict[str, Any]] = {}
    for source in sources:
        if not isinstance(source, dict):
            errors.append("source.not_object")
            continue
        source_id = str(source.get("source_id") or "")
        if not source_id:
            errors.append("source.source_id_missing")
            continue
        if source_id in source_ids:
            errors.append(f"source.duplicate_id:{source_id}")
        source_ids.add(source_id)
        source_by_id[source_id] = source

        for field_name in ("url", "title", "accessed_at", "source_type", "evidence_status"):
            if not source.get(field_name):
                errors.append(f"source.{source_id}.{field_name}_missing")

        independence = source.get("independence") if isinstance(source.get("independence"), dict) else {}
        independence_status = independence.get("status")
        if independence_status not in {"independent", "not_independent", "unknown", "primary_source"}:
            errors.append(f"source.{source_id}.independence_status_invalid:{independence_status}")
        elif independence_status in {"not_independent", "unknown"}:
            warnings.append(f"source_independence_{independence_status}:{source_id}")
            manual_review = True

        evidence_path = source.get("evidence_path") or f"evidence/{_source_dir_name(source_id)}/source_record.json"
        expected_prefix = f"evidence/{_source_dir_name(source_id)}/"
        if not str(evidence_path).replace("\\", "/").startswith(expected_prefix):
            errors.append(f"source.evidence_dir_mismatch:{source_id}:{evidence_path}")
        source_record_path = run_dir / str(evidence_path)
        source_record = load(source_record_path)
        if source_record:
            if source_record.get("source_id") != source_id:
                errors.append(f"source_record.id_mismatch:{source_id}")
            if source.get("url") != source_record.get("url"):
                errors.append(f"source_record.url_mismatch:{source_id}")

        policy = source.get("screenshot_policy") or {}
        if policy.get("required"):
            manual_review = True
            status = policy.get("status")
            if status == "required_and_present":
                screenshot = _field(source, "evidence.screenshot")
                if not screenshot:
                    errors.append(f"screenshot.required_present_path_missing:{source_id}")
                elif not (run_dir / str(screenshot)).exists():
                    errors.append(f"screenshot.required_present_missing_on_disk:{source_id}")
            elif status == "required_but_missing":
                errors.append(f"screenshot.required_but_missing:{source_id}")
            elif status in {"capture_failed", "redacted"}:
                warnings.append(f"screenshot_{status}:{source_id}")
            else:
                errors.append(f"screenshot.unknown_required_status:{source_id}:{status}")

    if csv_source_ids and csv_source_ids != source_ids:
        errors.append(f"sources_csv.id_mismatch:{sorted(csv_source_ids)}!={sorted(source_ids)}")

    if not claims:
        errors.append("claims.empty")

    supported_claims = 0
    unsupported_claims: list[str] = []
    unknown_claims = 0
    single_source_claims = 0
    claim_ids: set[str] = set()

    for claim in claims:
        if not isinstance(claim, dict):
            errors.append("claim.not_object")
            continue
        claim_id = str(claim.get("claim_id") or "")
        claim_type = str(claim.get("claim_type") or "")
        claim_role = str(claim.get("claim_role") or ("unknown" if claim_type == "unknown" else "key_claim" if claim.get("is_key_finding") else "background"))
        source_id_list = [str(item) for item in claim.get("source_ids", []) if str(item).strip()] if isinstance(claim.get("source_ids"), list) else []
        support = claim.get("support") if isinstance(claim.get("support"), list) else []
        support_source_ids = [str(item.get("source_id") or "") for item in support if isinstance(item, dict)]

        if not claim_id:
            errors.append("claim.claim_id_missing")
            claim_id = "unknown"
        if claim_id in claim_ids:
            errors.append(f"claim.duplicate_id:{claim_id}")
        claim_ids.add(claim_id)
        if not claim.get("text"):
            errors.append(f"claim.text_missing:{claim_id}")
        if claim_type not in {"fact", "inference", "unknown"}:
            errors.append(f"claim.invalid_type:{claim_id}:{claim_type}")
        if claim_role not in {"key_claim", "background", "method_note", "unknown", "limitation"}:
            errors.append(f"claim.invalid_role:{claim_id}:{claim_role}")

        for source_id in source_id_list:
            if source_id not in source_ids:
                errors.append(f"claim.missing_source:{claim_id}:{source_id}")
        for support_item in support:
            if not isinstance(support_item, dict):
                errors.append(f"claim.support_not_object:{claim_id}")
                continue
            support_source_id = str(support_item.get("source_id") or "")
            support_type = str(support_item.get("support_type") or "")
            if support_source_id not in source_ids:
                errors.append(f"claim.support_missing_source:{claim_id}:{support_source_id}")
            if support_source_id and support_source_id not in source_id_list:
                errors.append(f"claim.support_source_not_listed:{claim_id}:{support_source_id}")
            if support_type not in {"direct", "inferred"}:
                errors.append(f"claim.invalid_support_type:{claim_id}:{support_type}")

        if claim_role == "method_note":
            if claim_id not in report_markdown:
                errors.append(f"report.claim_missing:{claim_id}")
            continue

        if claim_role == "limitation" and not (claim.get("notes") or claim.get("reason")):
            errors.append(f"limitation_without_reason:{claim_id}")

        if claim_type == "unknown" or claim_role == "unknown":
            unknown_claims += 1
            if not (claim.get("notes") or claim.get("sources_checked")):
                errors.append(f"unknown_without_explanation:{claim_id}")
            if claim_id not in report_markdown:
                errors.append(f"report.unknown_claim_missing:{claim_id}")
            continue

        is_key = claim_role == "key_claim" or bool(claim.get("is_key_finding"))
        if is_key and not source_id_list:
            errors.append(f"unsupported_claim:{claim_id}:no_source_ids")
            unsupported_claims.append(claim_id)
        if is_key and not support:
            errors.append(f"unsupported_claim:{claim_id}:no_support")
            unsupported_claims.append(claim_id)
        if is_key:
            failed_support_sources = [
                source_id
                for source_id in source_id_list
                if source_by_id.get(source_id, {}).get("evidence_status") == "capture_failed"
            ]
            for source_id in failed_support_sources:
                errors.append(f"claim.uses_failed_source:{claim_id}:{source_id}")
        if claim_role == "background" and (not source_id_list or not support):
            warnings.append(f"background_claim_missing_support:{claim_id}")
            manual_review = True
        if claim_type == "fact" and support and "direct" not in [str(item.get("support_type")) for item in support if isinstance(item, dict)]:
            errors.append(f"fact_without_direct_support:{claim_id}")
        if any(str(item.get("support_type")) == "inferred" for item in support if isinstance(item, dict)):
            warnings.append(f"inferred_support:{claim_id}")
            manual_review = True

        if len(source_id_list) == 1:
            single_source_claims += 1
            if not claim.get("single_source"):
                errors.append(f"single_source_claim_not_marked:{claim_id}")
        elif is_key and source_id_list:
            independent_keys: set[str] = set()
            unknown_or_related = False
            for source_id in source_id_list:
                source = source_by_id.get(source_id, {})
                independence = source.get("independence") if isinstance(source.get("independence"), dict) else {}
                independence_status = independence.get("status")
                if independence_status in {"primary_source", "independent"}:
                    independent_keys.add(source_id)
                elif independence_status == "not_independent":
                    related_to = independence.get("related_to")
                    if related_to:
                        independent_keys.add(str(related_to))
                    else:
                        unknown_or_related = True
                else:
                    unknown_or_related = True
            if len(independent_keys) < 2:
                warnings.append(f"claim_not_independently_supported:{claim_id}")
                manual_review = True
                single_source_claims += 1
                if not claim.get("single_source"):
                    errors.append(f"non_independent_sources_not_marked_single_source:{claim_id}")
            elif unknown_or_related:
                warnings.append(f"claim_independence_partially_unknown:{claim_id}")
                manual_review = True

        if source_id_list and support:
            supported_claims += 1

        if claim_id not in report_markdown:
            errors.append(f"report.claim_missing:{claim_id}")
        for source_id in source_id_list:
            if f"[{source_id}]" not in report_markdown:
                errors.append(f"report.source_marker_missing:{claim_id}:{source_id}")

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
        for key in ("report_path", "missing_sources_path"):
            raw_path = _field(manifest, f"validation.{key}")
            if raw_path and not (run_dir / str(raw_path)).exists():
                errors.append(f"manifest.validation.{key}_missing_on_disk:{raw_path}")

    if (run_dir / "artifacts" / "discovery-log.json").exists():
        discovery_report = validate_research_discovery_run(run_dir)
        errors.extend(discovery_report.get("errors", []))
        warnings.extend(discovery_report.get("warnings", []))
        manual_review = manual_review or bool(discovery_report.get("requires_manual_review"))

    status = "fail" if errors else "pass"
    reasons = _review_reasons(errors, "blocking", "validation/claim-coverage-report.json") + _review_reasons(
        list(dict.fromkeys(warnings)) if manual_review else [], "warning", "validation/claim-coverage-report.json"
    )
    return {
        "schema_version": "1.0",
        "status": status,
        "errors": errors,
        "warnings": list(dict.fromkeys(warnings)),
        "requires_manual_review": manual_review or bool(errors),
        "total_claims": len(claims),
        "supported_claims": supported_claims,
        "unsupported_claims": sorted(set(unsupported_claims)),
        "unknown_claims": unknown_claims,
        "single_source_claims": single_source_claims,
        "source_ids": sorted(source_ids),
        "screenshot_policy": {"required": False, "reason": "per_source_policy", "status": "not_required"},
        **_status_fields(status, list(dict.fromkeys(warnings)), manual_review or bool(errors), reasons, errors),
    }


def validate_price_compare_run(run_dir: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    manual_review = False

    prices_path = run_dir / "artifacts" / "prices.json"
    prices_csv_path = run_dir / "artifacts" / "prices.csv"
    report_path = run_dir / "artifacts" / "price-report.md"
    anomalies_path = run_dir / "artifacts" / "anomalies.md"
    chart_path = run_dir / "artifacts" / "price-chart.png"
    manifest_path = run_dir / "manifest.json"

    def load(path: Path) -> dict[str, Any] | None:
        if not path.exists():
            errors.append(f"missing_file:{path.relative_to(run_dir).as_posix()}")
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"invalid_json:{path.relative_to(run_dir).as_posix()}:{exc}")
            return None

    prices_doc = load(prices_path)
    manifest = load(manifest_path)

    if not report_path.exists():
        errors.append("missing_file:artifacts/price-report.md")
        report_markdown = ""
    else:
        report_markdown = report_path.read_text(encoding="utf-8")

    if not anomalies_path.exists():
        errors.append("missing_file:artifacts/anomalies.md")
        anomalies_markdown = ""
    else:
        anomalies_markdown = anomalies_path.read_text(encoding="utf-8")

    if not chart_path.exists():
        errors.append("missing_file:artifacts/price-chart.png")
    elif chart_path.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
        errors.append("price_chart.not_png")

    csv_quote_ids: set[str] = set()
    if not prices_csv_path.exists():
        errors.append("missing_file:artifacts/prices.csv")
    else:
        with prices_csv_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            required_columns = {
                "quote_id",
                "source_id",
                "platform",
                "product_name",
                "seller",
                "condition",
                "region",
                "currency",
                "stock",
                "match_confidence",
                "list_price",
                "sale_price",
                "coupon_price",
                "shipping_fee",
                "estimated_total",
                "comparison_price",
                "eligible_for_lowest_price",
                "url",
            }
            if reader.fieldnames is None:
                errors.append("prices_csv.header_missing")
            elif not required_columns.issubset(set(reader.fieldnames)):
                errors.append("prices_csv.required_columns_missing")
            for row in reader:
                quote_id = row.get("quote_id")
                if quote_id:
                    csv_quote_ids.add(quote_id)

    quotes = prices_doc.get("quotes", []) if isinstance(prices_doc, dict) else []
    candidates = prices_doc.get("candidates", []) if isinstance(prices_doc, dict) else []
    anomalies = prices_doc.get("anomalies", []) if isinstance(prices_doc, dict) else []
    comparison = prices_doc.get("comparison", {}) if isinstance(prices_doc, dict) else {}
    if not isinstance(quotes, list):
        errors.append("prices.quotes_not_list")
        quotes = []
    if not isinstance(candidates, list):
        errors.append("prices.candidates_not_list")
        candidates = []
    if not isinstance(anomalies, list):
        errors.append("prices.anomalies_not_list")
        anomalies = []
    if not isinstance(comparison, dict):
        errors.append("prices.comparison_not_object")
        comparison = {}

    quote_ids: set[str] = set()
    eligible_quote_ids: list[str] = []
    source_ids: set[str] = set()
    manual_review_codes: list[str] = []
    anomaly_keys = {
        f"{anomaly.get('record_id')}:{anomaly.get('anomaly')}"
        for anomaly in anomalies
        if isinstance(anomaly, dict)
    }

    for candidate in candidates:
        if not isinstance(candidate, dict):
            errors.append("candidate.not_object")
            continue
        candidate_id = str(candidate.get("candidate_id") or "")
        if not candidate_id:
            errors.append("candidate.candidate_id_missing")
        if candidate.get("match_confidence", 0) < 0.8 and f"{candidate_id}:low_confidence_match" not in anomaly_keys:
            errors.append(f"candidate.low_confidence_not_anomalized:{candidate_id}")
        for field_name in ("product_identity", "platform", "url", "seller", "condition", "currency", "match_confidence"):
            if candidate.get(field_name) is None:
                errors.append(f"candidate.{candidate_id}.{field_name}_missing")
        if candidate.get("assessment_method") != "provided_url_candidate_assessment":
            errors.append(f"candidate.{candidate_id}.assessment_method_invalid")

    for quote in quotes:
        if not isinstance(quote, dict):
            errors.append("quote.not_object")
            continue
        quote_id = str(quote.get("quote_id") or "")
        source_id = str(quote.get("source_id") or "")
        if not quote_id:
            errors.append("quote.quote_id_missing")
            quote_id = "unknown"
        if quote_id in quote_ids:
            errors.append(f"quote.duplicate_id:{quote_id}")
        quote_ids.add(quote_id)
        if not source_id:
            errors.append(f"quote.source_id_missing:{quote_id}")
        else:
            source_ids.add(source_id)

        for field_name in ("url", "platform", "region", "currency", "seller", "condition", "stock", "accessed_at"):
            if not quote.get(field_name):
                errors.append(f"quote.{quote_id}.{field_name}_missing")
        quote_context = quote.get("quote_context") if isinstance(quote.get("quote_context"), dict) else {}
        if not quote_context:
            errors.append(f"quote.{quote_id}.quote_context_missing")
        else:
            for field_name in (
                "platform",
                "region",
                "currency",
                "seller_type",
                "condition",
                "selected_specs",
                "membership_required",
                "coupon_action_required",
                "cart_required",
                "checkout_required",
                "shipping_known",
                "stock_status",
            ):
                if field_name not in quote_context:
                    errors.append(f"quote.{quote_id}.quote_context.{field_name}_missing")
            if quote_context.get("region") != quote.get("region"):
                errors.append(f"quote.{quote_id}.quote_context_region_mismatch")
            if quote_context.get("currency") != quote.get("currency"):
                errors.append(f"quote.{quote_id}.quote_context_currency_mismatch")
        if not quote.get("quote_context_hash"):
            errors.append(f"quote.{quote_id}.quote_context_hash_missing")
        elif not str(quote.get("quote_context_hash")).startswith("sha256:"):
            errors.append(f"quote.{quote_id}.quote_context_hash_invalid")

        identity = quote.get("product_identity")
        if not isinstance(identity, dict):
            errors.append(f"quote.{quote_id}.product_identity_missing")
            identity = {}
        if not identity.get("product_name"):
            errors.append(f"quote.{quote_id}.product_name_missing")
        specs = identity.get("specs")
        if not isinstance(specs, dict) or not specs:
            errors.append(f"quote.{quote_id}.specs_missing")

        prices = quote.get("prices")
        if not isinstance(prices, dict):
            errors.append(f"quote.{quote_id}.prices_missing")
            prices = {}
        for key in ("list_price", "sale_price", "coupon_price", "shipping_fee", "estimated_total"):
            if key not in prices:
                errors.append(f"quote.{quote_id}.price_component_missing:{key}")
        if "price" in prices:
            errors.append(f"quote.{quote_id}.generic_price_field_forbidden")
        if prices.get("shipping_fee") is None and f"{quote_id}:unknown_shipping_fee" not in anomaly_keys:
            errors.append(f"quote.{quote_id}.unknown_shipping_fee_not_anomalized")
        estimated_total = quote.get("estimated_total")
        if not isinstance(estimated_total, dict):
            errors.append(f"quote.{quote_id}.estimated_total_details_missing")
        else:
            for field_name in ("amount", "currency", "calculation", "components", "confidence", "warnings"):
                if field_name not in estimated_total:
                    errors.append(f"quote.{quote_id}.estimated_total.{field_name}_missing")
            if estimated_total.get("calculation") == "unknown" and not estimated_total.get("warnings"):
                errors.append(f"quote.{quote_id}.estimated_total_unknown_without_warning")

        flags = quote.get("flags") if isinstance(quote.get("flags"), dict) else {}
        for flag in ("coupon_action_required", "cart_required", "checkout_required", "membership_required", "address_change_required"):
            if flag not in flags:
                errors.append(f"quote.{quote_id}.flag_missing:{flag}")
        if any(flags.get(flag) for flag in ("coupon_action_required", "cart_required", "checkout_required", "address_change_required")):
            manual_review = True
            for flag in ("coupon_action_required", "cart_required", "checkout_required", "address_change_required"):
                if flags.get(flag):
                    manual_review_codes.append(f"{quote_id}:{flag}")
            if quote.get("eligible_for_lowest_price"):
                errors.append(f"quote.{quote_id}.red_action_required_but_eligible")
        if quote.get("manual_review_required"):
            manual_review = True
            manual_review_codes.append(f"{quote_id}:manual_review_required")

        if quote.get("match_confidence", 0) < 0.8 and quote.get("eligible_for_lowest_price"):
            errors.append(f"quote.{quote_id}.low_confidence_but_eligible")
        if not quote.get("selected_specs_confirmed") and quote.get("eligible_for_lowest_price"):
            errors.append(f"quote.{quote_id}.unconfirmed_specs_but_eligible")

        if quote.get("eligible_for_lowest_price"):
            eligible_quote_ids.append(quote_id)
            if quote.get("comparison_price") is None:
                errors.append(f"quote.{quote_id}.eligible_without_comparison_price")
            if comparison.get("region") and quote.get("region") != comparison.get("region"):
                errors.append(f"quote.{quote_id}.eligible_region_mismatch")
            if comparison.get("currency") and quote.get("currency") != comparison.get("currency"):
                errors.append(f"quote.{quote_id}.eligible_currency_mismatch")
            required_specs = comparison.get("required_specs") if isinstance(comparison.get("required_specs"), dict) else {}
            mismatched_specs = [
                str(key)
                for key, expected in required_specs.items()
                if str((identity.get("specs") or {}).get(key, "")).strip().lower() != str(expected).strip().lower()
            ]
            if mismatched_specs:
                errors.append(f"quote.{quote_id}.eligible_incompatible_specs:{','.join(mismatched_specs)}")
            if quote.get("manual_review_required"):
                errors.append(f"quote.{quote_id}.manual_review_required_but_eligible")
            if quote.get("excluded_from_lowest_price"):
                errors.append(f"quote.{quote_id}.excluded_but_eligible")

        screenshot_policy = quote.get("screenshot_policy") if isinstance(quote.get("screenshot_policy"), dict) else {}
        if not screenshot_policy.get("required"):
            errors.append(f"quote.{quote_id}.screenshot_not_required_for_product_page")
        status = screenshot_policy.get("status")
        screenshot = quote.get("screenshot")
        if status == "required_and_present":
            if not screenshot:
                errors.append(f"quote.{quote_id}.screenshot_path_missing")
            elif not (run_dir / str(screenshot)).exists():
                errors.append(f"quote.{quote_id}.screenshot_missing_on_disk:{screenshot}")
        elif status == "required_but_missing":
            errors.append(f"quote.{quote_id}.screenshot_required_but_missing")
            manual_review = True
            manual_review_codes.append(f"{quote_id}:screenshot_required_but_missing")
        elif status in {"capture_failed", "redacted"}:
            warnings.append(f"screenshot_{status}:{quote_id}")
            manual_review_codes.append(f"{quote_id}:screenshot_{status}")
            manual_review = True
        else:
            errors.append(f"quote.{quote_id}.screenshot_status_invalid:{status}")

        source_record_path = quote.get("source_record_path")
        if not source_record_path:
            errors.append(f"quote.{quote_id}.source_record_path_missing")
        else:
            expected_prefix = f"evidence/{_source_dir_name(source_id)}/"
            if source_id and not str(source_record_path).replace("\\", "/").startswith(expected_prefix):
                errors.append(f"quote.{quote_id}.source_record_dir_mismatch:{source_record_path}")
            source_record = load(run_dir / str(source_record_path))
            if source_record:
                if source_record.get("source_id") != source_id:
                    errors.append(f"source_record.id_mismatch:{quote_id}")
                if source_record.get("url") != quote.get("url"):
                    errors.append(f"source_record.url_mismatch:{quote_id}")

        if quote_id not in report_markdown:
            errors.append(f"report.quote_missing:{quote_id}")
        for anomaly in quote.get("anomalies") or []:
            if str(anomaly) not in anomalies_markdown:
                errors.append(f"anomalies_md.missing:{quote_id}:{anomaly}")

    if csv_quote_ids and csv_quote_ids != quote_ids:
        errors.append(f"prices_csv.id_mismatch:{sorted(csv_quote_ids)}!={sorted(quote_ids)}")

    lowest_id = comparison.get("lowest_eligible_quote_id")
    if lowest_id and lowest_id not in eligible_quote_ids:
        errors.append(f"comparison.lowest_not_eligible:{lowest_id}")
    if eligible_quote_ids and not lowest_id:
        errors.append("comparison.lowest_missing")
    if not eligible_quote_ids:
        manual_review = True
        manual_review_codes.append("no_eligible_quotes")

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
        raw_path = _field(manifest, "validation.report_path")
        if raw_path and not (run_dir / str(raw_path)).exists():
            errors.append(f"manifest.validation.report_path_missing_on_disk:{raw_path}")

    if (run_dir / "artifacts" / "candidates.json").exists():
        candidate_report = validate_price_candidate_discovery_run(run_dir)
        errors.extend(candidate_report.get("errors", []))
        warnings.extend(candidate_report.get("warnings", []))
        manual_review = manual_review or bool(candidate_report.get("requires_manual_review"))

    status = "fail" if errors else "pass"
    warning_reasons = list(dict.fromkeys(warnings + manual_review_codes)) if manual_review else []
    reasons = _review_reasons(errors, "blocking", "validation/price-validation-report.json") + _review_reasons(
        warning_reasons, "warning", "validation/price-validation-report.json"
    )
    return {
        "schema_version": "1.0",
        "status": status,
        "errors": errors,
        "warnings": list(dict.fromkeys(warnings)),
        "requires_manual_review": manual_review or bool(errors),
        "total_candidates": len(candidates),
        "total_quotes": len(quotes),
        "eligible_quotes": eligible_quote_ids,
        "anomaly_count": len(anomalies),
        "source_ids": sorted(source_ids),
        "screenshot_policy": {"required": True, "reason": "ecommerce_product_pages", "status": "per_quote_policy"},
        **_status_fields(status, list(dict.fromkeys(warnings)), manual_review or bool(errors), reasons, errors),
    }
