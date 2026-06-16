from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from inward_eyes.io import read_json, utc_now, write_json, write_text  # noqa: E402
from inward_eyes.price_discovery import (  # noqa: E402
    APPROVAL_POLICY_AUTO_HIGH_CONFIDENCE,
    DEFAULT_MAX_CANDIDATES_PER_PLATFORM,
    HARD_MAX_TOTAL_CANDIDATES,
    normalize_candidates,
    render_candidate_review,
    render_candidates_csv,
    validate_price_candidate_discovery_run,
)
from inward_eyes.validation import validate_price_compare_run  # noqa: E402


def _slug_timestamp(timestamp: str) -> str:
    return re.sub(r"[^0-9TZ]", "", timestamp)


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _strings(value: Any) -> list[str]:
    return [str(item) for item in _as_list(value) if str(item).strip()]


def _parse_required_specs(values: list[str]) -> dict[str, str]:
    specs: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise SystemExit(f"--required-spec must be key=value: {value}")
        key, raw_value = value.split("=", 1)
        key = key.strip()
        if not key:
            raise SystemExit(f"--required-spec key missing: {value}")
        specs[key] = raw_value.strip()
    return specs


def _load_spec(args: argparse.Namespace) -> tuple[dict[str, Any], Path | None]:
    spec: dict[str, Any] = {}
    input_path: Path | None = None
    if args.input:
        input_path = Path(args.input).resolve()
        loaded = read_json(input_path)
        if not isinstance(loaded, dict):
            raise SystemExit("M10B input JSON must be an object")
        spec.update(loaded)
    if args.target_product:
        spec["target_product"] = args.target_product
    if args.required_spec:
        required_specs = spec.get("required_specs") if isinstance(spec.get("required_specs"), dict) else {}
        required_specs.update(_parse_required_specs(args.required_spec))
        spec["required_specs"] = required_specs
    if args.allowed_platform:
        spec["allowed_platforms"] = args.allowed_platform
    if args.allowed_domain:
        spec["allowed_domains"] = args.allowed_domain
    if args.max_candidates_per_platform is not None:
        spec["max_candidates_per_platform"] = args.max_candidates_per_platform
    if args.region:
        spec["region"] = args.region
    if args.currency:
        spec["currency"] = args.currency
    if args.approval_policy:
        spec["approval_policy"] = args.approval_policy
    spec.setdefault("max_candidates_per_platform", DEFAULT_MAX_CANDIDATES_PER_PLATFORM)
    spec.setdefault("approval_policy", "review_only")
    return spec, input_path


def _target_name(spec: dict[str, Any], candidates_model: dict[str, Any]) -> str:
    target = spec.get("target_product")
    if isinstance(target, dict):
        return str(target.get("target_name") or target.get("name") or candidates_model.get("target_product") or "")
    return str(target or candidates_model.get("target_product") or "")


def _required_specs(spec: dict[str, Any], candidates_model: dict[str, Any]) -> dict[str, Any]:
    if isinstance(spec.get("required_specs"), dict):
        return spec["required_specs"]
    if isinstance(candidates_model.get("required_specs"), dict):
        return candidates_model["required_specs"]
    target = spec.get("target_product")
    if isinstance(target, dict) and isinstance(target.get("required_specs"), dict):
        return target["required_specs"]
    return {}


def _resolve_input_path(raw_path: Any, input_path: Path | None) -> str:
    path = Path(str(raw_path))
    if path.is_absolute():
        return str(path.resolve())
    base = input_path.parent if input_path else Path.cwd()
    return str((base / path).resolve())


def _raw_candidates(spec: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in _as_list(spec.get("candidates") or spec.get("candidate_products")) if isinstance(item, dict)]


def _raw_by_index(spec: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {index: item for index, item in enumerate(_raw_candidates(spec), start=1)}


def _prices_from_candidate(raw: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    prices = raw.get("prices") if isinstance(raw.get("prices"), dict) else {}
    return {
        "list_price": prices.get("list_price", raw.get("list_price")),
        "sale_price": prices.get("sale_price", raw.get("sale_price", candidate.get("provisional_price"))),
        "coupon_price": prices.get("coupon_price", raw.get("coupon_price")),
        "shipping_fee": prices.get("shipping_fee", raw.get("shipping_fee")),
        "estimated_total": prices.get("estimated_total", raw.get("estimated_total")),
    }


def _m9_sources(
    *,
    spec: dict[str, Any],
    candidates_model: dict[str, Any],
    input_path: Path | None,
) -> list[dict[str, Any]]:
    raw_by_index = _raw_by_index(spec)
    sources: list[dict[str, Any]] = []
    for index, candidate in enumerate(
        [item for item in candidates_model.get("candidates", []) if item.get("approved_for_quote_capture")],
        start=1,
    ):
        raw = raw_by_index.get(int(candidate.get("raw_candidate_index") or 0), {})
        source: dict[str, Any] = {
            "source_id": f"S{index:03d}",
            "candidate_id": candidate.get("candidate_id"),
            "approved": True,
            "url": candidate["product_url"],
            "page_title": raw.get("page_title") or candidate.get("visible_product_name"),
            "site_name": raw.get("site_name") or candidate.get("platform"),
            "platform": candidate.get("platform"),
            "selected_main_content": raw.get("selected_main_content")
            or f"{candidate.get('visible_product_name')} seller {candidate.get('seller')}",
            "product_identity": {
                "product_name": raw.get("product_name") or candidate.get("visible_product_name"),
                "model_number": raw.get("model_number"),
                "specs": candidate.get("visible_specs") or {},
            },
            "seller": candidate.get("seller"),
            "seller_type": raw.get("seller_type") or candidate.get("seller_type") or "unknown",
            "condition": candidate.get("condition"),
            "stock": raw.get("stock") or "unknown",
            "prices": _prices_from_candidate(raw, candidate),
            "match_confidence": candidate.get("match_confidence"),
            "selected_specs_confirmed": not candidate.get("mismatch_flags"),
            "region": raw.get("region") or candidate.get("region") or candidates_model.get("region"),
            "currency": raw.get("currency") or candidate.get("currency") or candidates_model.get("currency"),
            "notes": raw.get("notes") or candidate.get("selection_rationale"),
        }
        for key in (
            "canonical_url",
            "html",
            "html_file",
            "text",
            "text_file",
            "accessibility_snapshot",
            "accessibility_snapshot_file",
            "screenshot_required",
            "screenshot_reason",
            "failure_reason",
            "warnings",
            "actions",
            "coupon_action_required",
            "cart_required",
            "checkout_required",
            "membership_required",
            "address_change_required",
        ):
            if key in raw:
                source[key] = raw[key]
        if raw.get("screenshot"):
            source["screenshot"] = _resolve_input_path(raw["screenshot"], input_path)
        if isinstance(raw.get("screenshots"), list):
            source["screenshots"] = [_resolve_input_path(item, input_path) for item in raw["screenshots"]]
        sources.append(source)
    return sources


def _write_warnings(path: Path, warnings: list[str]) -> None:
    if not warnings:
        write_text(path, "No warnings.\n")
        return
    lines = ["# Warnings", ""]
    lines.extend(f"- {warning}" for warning in warnings)
    write_text(path, "\n".join(lines) + "\n")


def _base_manifest(
    *,
    run_id: str,
    started_at: str,
    input_record: dict[str, Any],
    candidate_report: dict[str, Any],
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "task": "price-compare",
        "started_at": started_at,
        "finished_at": utc_now(),
        "operator": "codex",
        "skill": "price-compare",
        "inputs": input_record,
        "artifacts": [
            {"id": "CAND001", "type": "candidate_json", "path": "artifacts/candidates.json"},
            {"id": "CAND002", "type": "candidate_csv", "path": "artifacts/candidates.csv"},
            {"id": "CAND003", "type": "candidate_review", "path": "artifacts/candidate-review.md"},
        ],
        "evidence": [
            {
                "id": "CVAL001",
                "type": "validation_report",
                "path": "validation/candidate-validation-report.json",
            }
        ],
        "validation": {
            "schema_valid": candidate_report.get("status") == "pass",
            "warnings": len(candidate_report.get("warnings", [])),
            "requires_manual_review": bool(candidate_report.get("requires_manual_review")),
            "report_path": "validation/candidate-validation-report.json",
        },
        "warnings": candidate_report.get("warnings", []),
        "requires_manual_review": bool(candidate_report.get("requires_manual_review")),
        "run_status": candidate_report.get("run_status", "failed"),
        "validation_status": candidate_report.get("validation_status", "failed"),
        "manual_review": candidate_report.get("manual_review", {"required": True, "severity": "blocking", "reasons": []}),
        "completion_blockers": candidate_report.get("completion_blockers", []),
        "screenshot_policy": {"required": True, "reason": "ecommerce_product_pages", "status": "per_quote_policy"},
    }


def _upsert_path_record(records: list[dict[str, Any]], record: dict[str, Any]) -> None:
    path = record.get("path")
    for index, item in enumerate(records):
        if isinstance(item, dict) and item.get("path") == path:
            records[index] = {**item, **record}
            return
    records.append(record)


def _merge_manifest(
    run_dir: Path,
    *,
    input_record: dict[str, Any],
    candidate_report: dict[str, Any],
    price_report: dict[str, Any] | None = None,
) -> None:
    manifest_path = run_dir / "manifest.json"
    manifest = read_json(manifest_path)
    artifacts = [item for item in manifest.get("artifacts", []) if isinstance(item, dict)]
    evidence = [item for item in manifest.get("evidence", []) if isinstance(item, dict)]
    _upsert_path_record(artifacts, {"id": "CAND001", "type": "candidate_json", "path": "artifacts/candidates.json"})
    _upsert_path_record(artifacts, {"id": "CAND002", "type": "candidate_csv", "path": "artifacts/candidates.csv"})
    _upsert_path_record(artifacts, {"id": "CAND003", "type": "candidate_review", "path": "artifacts/candidate-review.md"})
    _upsert_path_record(
        evidence,
        {"id": "CVAL001", "type": "validation_report", "path": "validation/candidate-validation-report.json"},
    )
    reports = [candidate_report]
    if price_report is not None:
        reports.append(price_report)
    status_failed = any(report.get("status") == "fail" for report in reports)
    requires_manual_review = any(bool(report.get("requires_manual_review")) for report in reports)
    warnings = list(
        dict.fromkeys(
            _strings(manifest.get("warnings"))
            + _strings(candidate_report.get("warnings"))
            + (_strings(price_report.get("warnings")) if price_report else [])
        )
    )
    blockers = list(
        dict.fromkeys(
            _strings(candidate_report.get("completion_blockers"))
            + (_strings(price_report.get("completion_blockers")) if price_report else [])
        )
    )
    reasons: list[dict[str, Any]] = []
    for report in reports:
        manual_review = report.get("manual_review") if isinstance(report.get("manual_review"), dict) else {}
        reasons.extend(reason for reason in manual_review.get("reasons", []) if isinstance(reason, dict))
    manifest.update(
        {
            "inputs": input_record,
            "artifacts": artifacts,
            "evidence": evidence,
            "warnings": warnings,
            "requires_manual_review": requires_manual_review,
            "run_status": "failed" if status_failed else "partial" if requires_manual_review else "complete",
            "validation_status": "failed" if status_failed else "passed",
            "manual_review": {
                "required": requires_manual_review,
                "severity": "blocking" if status_failed else "warning" if requires_manual_review else "info",
                "reasons": reasons,
            },
            "completion_blockers": blockers,
            "validation": {
                **(manifest.get("validation") or {}),
                "schema_valid": not status_failed,
                "warnings": len(warnings),
                "requires_manual_review": requires_manual_review,
                "report_path": "validation/price-validation-report.json"
                if price_report is not None
                else "validation/candidate-validation-report.json",
                "candidate_report_path": "validation/candidate-validation-report.json",
            },
        }
    )
    write_json(manifest_path, manifest)


def _input_record(
    *,
    args: argparse.Namespace,
    spec: dict[str, Any],
    candidates_model: dict[str, Any],
    approved_count: int,
    quote_extraction_proceeded: bool,
) -> dict[str, Any]:
    return {
        "schema_version": str(spec.get("schema_version") or "1.0"),
        "target_product": candidates_model.get("target_product"),
        "required_specs": candidates_model.get("required_specs") or {},
        "allowed_platforms": candidates_model.get("allowed_platforms") or [],
        "allowed_domains": candidates_model.get("allowed_domains") or [],
        "max_candidates_per_platform": candidates_model.get("max_candidates_per_platform"),
        "region": candidates_model.get("region"),
        "currency": candidates_model.get("currency"),
        "excluded_sellers": candidates_model.get("excluded_sellers") or [],
        "seller_preferences": candidates_model.get("seller_preferences") or {},
        "approval_policy": candidates_model.get("approval_policy"),
        "input_path": str(args.input) if args.input else None,
        "workflow": "price-compare",
        "capture_stage": "approved_candidate_discovery",
        "candidate_count": len(candidates_model.get("candidates") or []),
        "approved_candidate_count": approved_count,
        "quote_extraction_proceeded": quote_extraction_proceeded,
    }


def run(args: argparse.Namespace) -> tuple[Path, bool]:
    started_at = utc_now()
    run_id = args.run_id or f"{_slug_timestamp(started_at)}-price-candidate-discovery"
    output_root = Path(args.output_root or "browser-operator-runs").resolve()
    run_dir = output_root / run_id
    (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    (run_dir / "capture" / "candidate-search").mkdir(parents=True, exist_ok=True)
    (run_dir / "validation").mkdir(parents=True, exist_ok=True)

    spec, input_path = _load_spec(args)
    candidates_model = normalize_candidates(spec, started_at)
    write_json(run_dir / "artifacts" / "candidates.json", candidates_model)
    write_text(run_dir / "artifacts" / "candidates.csv", render_candidates_csv(candidates_model["candidates"]))
    write_text(run_dir / "artifacts" / "candidate-review.md", render_candidate_review(candidates_model))
    write_json(
        run_dir / "capture" / "candidate-search" / "discovery-scope.json",
        {
            "allowed_platforms": candidates_model.get("allowed_platforms"),
            "allowed_domains": candidates_model.get("allowed_domains"),
            "max_candidates_per_platform": candidates_model.get("max_candidates_per_platform"),
            "hard_max_total_candidates": HARD_MAX_TOTAL_CANDIDATES,
            "approval_policy": candidates_model.get("approval_policy"),
        },
    )

    approved_sources = _m9_sources(spec=spec, candidates_model=candidates_model, input_path=input_path)
    input_record = _input_record(
        args=args,
        spec=spec,
        candidates_model=candidates_model,
        approved_count=len(approved_sources),
        quote_extraction_proceeded=False,
    )
    write_json(run_dir / "input.json", input_record)
    candidate_report = validate_price_candidate_discovery_run(run_dir)
    write_json(run_dir / "validation" / "candidate-validation-report.json", candidate_report)
    _write_warnings(run_dir / "validation" / "warnings.md", candidate_report.get("warnings", []))
    write_json(
        run_dir / "manifest.json",
        _base_manifest(run_id=run_id, started_at=started_at, input_record=input_record, candidate_report=candidate_report),
    )
    candidate_report = validate_price_candidate_discovery_run(run_dir)
    write_json(run_dir / "validation" / "candidate-validation-report.json", candidate_report)

    if candidate_report.get("status") == "fail":
        _merge_manifest(run_dir, input_record=input_record, candidate_report=candidate_report)
        print(run_dir)
        return run_dir, True

    if not approved_sources:
        _merge_manifest(run_dir, input_record=input_record, candidate_report=candidate_report)
        print(run_dir)
        return run_dir, False

    price_capture_input = {
        "schema_version": "1.0",
        "title": spec.get("title") or f"{candidates_model.get('target_product')} approved candidate discovery",
        "region": candidates_model.get("region"),
        "currency": candidates_model.get("currency"),
        "product": {
            "target_name": _target_name(spec, candidates_model),
            "required_specs": _required_specs(spec, candidates_model),
        },
        "sources": approved_sources,
        "warnings": _strings(spec.get("warnings")),
    }
    price_capture_input_path = run_dir / "capture" / "approved-candidates-price-input.json"
    write_json(price_capture_input_path, price_capture_input)

    command = [
        sys.executable,
        str(SCRIPT_ROOT / "price_capture_runner.py"),
        "--input",
        str(price_capture_input_path),
        "--output-root",
        str(output_root),
        "--run-id",
        run_id,
        "--min-urls",
        "1",
        "--max-urls",
        str(HARD_MAX_TOTAL_CANDIDATES),
    ]
    completed = subprocess.run(command, cwd=Path(__file__).resolve().parents[1], text=True, capture_output=True)
    if completed.returncode != 0:
        candidate_report = {
            **candidate_report,
            "status": "fail",
            "errors": list(candidate_report.get("errors", [])) + [completed.stderr.strip() or "price_capture_runner_failed"],
            "requires_manual_review": True,
            "run_status": "failed",
            "validation_status": "failed",
        }
        write_json(run_dir / "validation" / "candidate-validation-report.json", candidate_report)
        _merge_manifest(run_dir, input_record=input_record, candidate_report=candidate_report)
        print(run_dir)
        return run_dir, True

    write_json(run_dir / "artifacts" / "candidates.json", candidates_model)
    write_text(run_dir / "artifacts" / "candidates.csv", render_candidates_csv(candidates_model["candidates"]))
    write_text(run_dir / "artifacts" / "candidate-review.md", render_candidate_review(candidates_model))
    input_record = _input_record(
        args=args,
        spec=spec,
        candidates_model=candidates_model,
        approved_count=len(approved_sources),
        quote_extraction_proceeded=True,
    )
    write_json(run_dir / "input.json", input_record)
    existing_price_report = read_json(run_dir / "validation" / "price-validation-report.json")
    _merge_manifest(
        run_dir,
        input_record=input_record,
        candidate_report=candidate_report,
        price_report=existing_price_report,
    )
    candidate_report = validate_price_candidate_discovery_run(run_dir)
    price_report = validate_price_compare_run(run_dir)
    write_json(run_dir / "validation" / "candidate-validation-report.json", candidate_report)
    write_json(run_dir / "validation" / "price-validation-report.json", price_report)
    _merge_manifest(run_dir, input_record=input_record, candidate_report=candidate_report, price_report=price_report)
    _write_warnings(
        run_dir / "validation" / "warnings.md",
        list(dict.fromkeys(_strings(candidate_report.get("warnings")) + _strings(price_report.get("warnings")))),
    )
    print(run_dir)
    return run_dir, False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Discover bounded approved product candidates, then optionally run M9 quote capture."
    )
    parser.add_argument("--input", help="M10B candidate discovery JSON spec.")
    parser.add_argument("--target-product", help="Target product name.")
    parser.add_argument("--required-spec", action="append", default=[], help="Required product spec as key=value.")
    parser.add_argument("--allowed-platform", action="append", default=[])
    parser.add_argument("--allowed-domain", action="append", default=[])
    parser.add_argument("--max-candidates-per-platform", type=int)
    parser.add_argument("--region")
    parser.add_argument("--currency")
    parser.add_argument("--approval-policy", choices=[APPROVAL_POLICY_AUTO_HIGH_CONFIDENCE, "review_only"])
    parser.add_argument("--output-root", default="browser-operator-runs")
    parser.add_argument("--run-id")
    args = parser.parse_args()
    _, blocked = run(args)
    return 1 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
