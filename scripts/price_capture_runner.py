from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from inward_eyes.io import read_json, utc_now, write_json, write_text  # noqa: E402
from inward_eyes.price import PRICE_KEYS, source_dir_name  # noqa: E402
from inward_eyes.validation import validate_price_compare_run  # noqa: E402

SCREENSHOT_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def _slug_timestamp(timestamp: str) -> str:
    return re.sub(r"[^0-9TZ]", "", timestamp)


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _strings(value: Any) -> list[str]:
    return [str(item) for item in _as_list(value) if str(item).strip()]


def _safe_asset_name(raw_name: str, index: int) -> str:
    path = Path(raw_name)
    suffix = path.suffix.lower()
    if suffix not in SCREENSHOT_EXTENSIONS:
        suffix = ".png"
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", path.stem).strip(".-") or f"screenshot-{index:03d}"
    return f"{index:03d}-{stem}{suffix}"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _append_optional(command: list[str], flag: str, value: Any) -> None:
    if value is not None:
        command.extend([flag, str(value)])


def _append_repeated(command: list[str], flag: str, values: list[Any]) -> None:
    for value in values:
        command.extend([flag, str(value)])


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
            raise SystemExit("M9 input JSON must be an object")
        spec.update(loaded)
    if args.target_name:
        product = spec.get("product") if isinstance(spec.get("product"), dict) else {}
        product["target_name"] = args.target_name
        spec["product"] = product
    if args.required_spec:
        product = spec.get("product") if isinstance(spec.get("product"), dict) else {}
        required_specs = product.get("required_specs") if isinstance(product.get("required_specs"), dict) else {}
        required_specs.update(_parse_required_specs(args.required_spec))
        product["required_specs"] = required_specs
        spec["product"] = product
    if args.region:
        spec["region"] = args.region
    if args.currency:
        spec["currency"] = args.currency
    if args.url:
        spec.setdefault("sources", [])
        spec["sources"].extend({"url": url, "approved": True} for url in args.url)
    return spec, input_path


def _source_records(spec: dict[str, Any]) -> list[dict[str, Any]]:
    raw_sources = spec.get("sources")
    if raw_sources is None:
        raw_sources = spec.get("product_urls")
    sources: list[dict[str, Any]] = []
    for item in _as_list(raw_sources):
        if isinstance(item, str):
            sources.append({"url": item, "approved": True})
        elif isinstance(item, dict):
            sources.append(item)
    return sources


def _validate_scope(spec: dict[str, Any], sources: list[dict[str, Any]], *, min_urls: int, max_urls: int) -> None:
    product = spec.get("product") if isinstance(spec.get("product"), dict) else {}
    required_specs = product.get("required_specs") if isinstance(product.get("required_specs"), dict) else {}
    if not product.get("target_name"):
        raise SystemExit("M9 requires product.target_name or --target-name")
    if not required_specs:
        raise SystemExit("M9 requires product.required_specs or --required-spec")
    if len(sources) < min_urls:
        raise SystemExit(f"M9 requires at least {min_urls} approved product URLs by default")
    if len(sources) > max_urls:
        raise SystemExit(f"M9 accepts at most {max_urls} approved product URLs for one run")
    for index, source in enumerate(sources, start=1):
        if not source.get("url"):
            raise SystemExit(f"product URL {index} missing url")
        if source.get("approved") is False:
            raise SystemExit(f"product URL {index} is not approved")
        backend = str(source.get("capture_backend") or source.get("backend") or "public_url")
        if backend != "public_url":
            raise SystemExit(f"M9 supports public product URL capture only: {backend}")


def _resolve_input_path(raw_path: Any, input_path: Path | None) -> Path:
    path = Path(str(raw_path))
    if path.is_absolute():
        return path.resolve()
    base = input_path.parent if input_path else Path.cwd()
    return (base / path).resolve()


def _source_screenshot_values(source: dict[str, Any], input_path: Path | None) -> list[str]:
    screenshots = source.get("screenshots")
    values = screenshots if isinstance(screenshots, list) else [source["screenshot"]] if source.get("screenshot") else []
    return [str(_resolve_input_path(value, input_path)) for value in values]


def _write_observation_file(source_dir: Path, name: str, value: Any) -> str | None:
    if value is None:
        return None
    path = source_dir / name
    if isinstance(value, (dict, list)):
        write_json(path, value)
    else:
        write_text(path, str(value))
    return str(path)


def _observation_file(
    source: dict[str, Any],
    source_dir: Path,
    key: str,
    file_key: str,
    filename: str,
    input_path: Path | None,
) -> str | None:
    if source.get(file_key):
        return str(_resolve_input_path(source[file_key], input_path))
    return _write_observation_file(source_dir, filename, source.get(key))


def _capture_command(
    *,
    source: dict[str, Any],
    source_index: int,
    adapter_output_root: Path,
    final_source_dir: Path,
    input_path: Path | None,
) -> list[str]:
    command = [
        sys.executable,
        str(SCRIPT_ROOT / "capture" / "playwright_mcp_capture.py"),
        "--url",
        str(source["url"]),
        "--output-root",
        str(adapter_output_root),
        "--run-id",
        f"source-{source_index:03d}",
        "--screenshot-required",
        "--screenshot-reason",
        "product_page",
    ]
    if source.get("capture_id"):
        command.extend(["--capture-id", str(source["capture_id"])])

    title = source.get("page_title") or source.get("title")
    _append_optional(command, "--page-title", title)
    _append_optional(command, "--canonical-url", source.get("canonical_url"))
    _append_optional(command, "--site-name", source.get("site_name") or source.get("platform"))

    html_file = _observation_file(source, final_source_dir, "html", "html_file", "observed.html", input_path)
    text_file = _observation_file(source, final_source_dir, "text", "text_file", "observed.txt", input_path)
    selected_file = _observation_file(
        source,
        final_source_dir,
        "selected_main_content",
        "selected_main_content_file",
        "selected-main-content.txt",
        input_path,
    )
    snapshot_file = _observation_file(
        source,
        final_source_dir,
        "accessibility_snapshot",
        "accessibility_snapshot_file",
        "accessibility-snapshot.json",
        input_path,
    )
    _append_optional(command, "--html-file", html_file)
    _append_optional(command, "--text-file", text_file)
    _append_optional(command, "--selected-main-content-file", selected_file)
    _append_optional(command, "--accessibility-snapshot-file", snapshot_file)

    if source.get("failure_reason"):
        _append_optional(command, "--failure-reason", source.get("failure_reason"))
    if source.get("requires_login"):
        command.append("--requires-login")
    _append_repeated(command, "--screenshot", _source_screenshot_values(source, input_path))
    _append_repeated(command, "--warning", _strings(source.get("warnings")))
    _append_repeated(command, "--action", _strings(source.get("actions")))
    return command


def _read_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    loaded = read_json(path)
    return loaded if isinstance(loaded, dict) else None


def _capture_asset_roots(capture_path: Path) -> list[Path]:
    return list(dict.fromkeys([capture_path.parent.resolve(), capture_path.parent.parent.resolve()]))


def _resolve_capture_asset(raw_path: str, capture_path: Path) -> Path | None:
    if not raw_path:
        return None
    path = Path(raw_path)
    if path.is_absolute():
        return path.resolve() if path.exists() else None
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", raw_path):
        return None
    for root in _capture_asset_roots(capture_path):
        candidate = (root / path).resolve()
        if candidate.exists():
            return candidate
    return None


def _stage_source_screenshots(
    *,
    capture: dict[str, Any],
    capture_path: Path,
    run_dir: Path,
    source_id: str,
    warnings: list[str],
) -> list[dict[str, Any]]:
    assets = capture.get("assets") if isinstance(capture.get("assets"), dict) else {}
    raw_screenshots = assets.get("screenshots") if isinstance(assets.get("screenshots"), list) else []
    staged: list[dict[str, Any]] = []
    for index, item in enumerate(raw_screenshots, start=1):
        if isinstance(item, str):
            raw_path = item
            captured_at = capture.get("captured_at")
        elif isinstance(item, dict):
            raw_path = str(item.get("path") or "")
            captured_at = item.get("captured_at") or capture.get("captured_at")
        else:
            warnings.append(f"{source_id}:screenshot_asset_invalid:{index}")
            continue
        source_path = _resolve_capture_asset(raw_path, capture_path)
        if source_path is None:
            warnings.append(f"{source_id}:screenshot_asset_missing:{raw_path}")
            continue
        destination = run_dir / "evidence" / source_dir_name(source_id) / "screenshots" / _safe_asset_name(raw_path, index)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination)
        staged.append(
            {
                "type": "screenshot",
                "path": destination.relative_to(run_dir).as_posix(),
                "captured_at": str(captured_at or capture.get("captured_at") or ""),
                "sha256": _sha256_file(destination),
            }
        )
    return staged


def _prices_from_source(source: dict[str, Any]) -> dict[str, Any]:
    prices = source.get("prices") if isinstance(source.get("prices"), dict) else {}
    return {key: prices.get(key, source.get(key)) for key in PRICE_KEYS}


def _identity_from_source(source: dict[str, Any], capture: dict[str, Any] | None) -> dict[str, Any]:
    identity = source.get("product_identity") if isinstance(source.get("product_identity"), dict) else {}
    specs = source.get("specs") if isinstance(source.get("specs"), dict) else identity.get("specs")
    capture_source = capture.get("source") if isinstance(capture, dict) and isinstance(capture.get("source"), dict) else {}
    return {
        "product_name": identity.get("product_name") or source.get("product_name") or capture_source.get("page_title"),
        "model_number": identity.get("model_number") or source.get("model_number"),
        "specs": specs if isinstance(specs, dict) else {},
    }


def _screenshot_policy_from_capture(
    capture: dict[str, Any] | None,
    staged_screenshots: list[dict[str, Any]],
) -> dict[str, Any]:
    if isinstance(capture, dict) and isinstance(capture.get("screenshot_policy"), dict):
        policy = dict(capture["screenshot_policy"])
    else:
        policy = {"required": True, "reason": "product_page", "status": "capture_failed"}
    policy["required"] = True
    policy["reason"] = "product_page"
    if policy.get("status") == "required_and_present" and not staged_screenshots:
        policy["status"] = "required_but_missing"
    return policy


def _candidate_from_source(
    *,
    source: dict[str, Any],
    source_index: int,
    source_id: str,
    capture: dict[str, Any] | None,
    region: str | None,
    currency: str | None,
) -> dict[str, Any]:
    identity = _identity_from_source(source, capture)
    return {
        "candidate_id": str(source.get("candidate_id") or f"K{source_index:03d}"),
        "source_id": source_id,
        "assessment_method": "provided_url_candidate_assessment",
        "product_identity": identity,
        "platform": source.get("platform") or (capture or {}).get("source", {}).get("site_name") or "unknown",
        "url": str((capture or {}).get("source", {}).get("url") or source.get("url") or ""),
        "seller": source.get("seller") or "unknown",
        "condition": source.get("condition") or "unknown",
        "provisional_price": source.get("provisional_price") or _prices_from_source(source).get("sale_price"),
        "currency": source.get("currency") or currency,
        "region": source.get("region") or region,
        "match_confidence": source.get("match_confidence", 0),
        "warnings": _strings(source.get("warnings")),
    }


def _quote_from_source(
    *,
    source: dict[str, Any],
    source_index: int,
    source_id: str,
    capture: dict[str, Any] | None,
    capture_report: dict[str, Any] | None,
    staged_screenshots: list[dict[str, Any]],
    source_warnings: list[str],
    accessed_at: str,
    region: str | None,
    currency: str | None,
) -> dict[str, Any]:
    capture_source = capture.get("source") if isinstance(capture, dict) and isinstance(capture.get("source"), dict) else {}
    screenshot = staged_screenshots[0]["path"] if staged_screenshots else None
    warnings = list(dict.fromkeys(_strings(source.get("warnings")) + source_warnings + _strings((capture_report or {}).get("warnings"))))
    return {
        "quote_id": str(source.get("quote_id") or f"Q{source_index:03d}"),
        "candidate_id": str(source.get("candidate_id") or f"K{source_index:03d}"),
        "source_id": source_id,
        "url": str(capture_source.get("url") or source.get("url") or ""),
        "canonical_url": capture_source.get("canonical_url") or source.get("canonical_url"),
        "title": capture_source.get("page_title") or source.get("title") or source.get("page_title"),
        "platform": source.get("platform") or capture_source.get("site_name") or "unknown",
        "region": source.get("region") or region,
        "currency": source.get("currency") or currency,
        "accessed_at": str((capture or {}).get("captured_at") or source.get("accessed_at") or accessed_at),
        "product_identity": _identity_from_source(source, capture),
        "seller": source.get("seller") or "unknown",
        "seller_type": source.get("seller_type") or "unknown",
        "condition": source.get("condition") or "unknown",
        "stock": source.get("stock") or "unknown",
        "prices": _prices_from_source(source),
        "price_basis": source.get("price_basis") or "visible_product_page",
        "capture_method": str((capture or {}).get("capture_method") or "capture_failed"),
        "match_confidence": source.get("match_confidence", 0),
        "selected_specs_confirmed": bool(source.get("selected_specs_confirmed")),
        "coupon_action_required": bool(source.get("coupon_action_required")),
        "cart_required": bool(source.get("cart_required")),
        "checkout_required": bool(source.get("checkout_required")),
        "membership_required": bool(source.get("membership_required")),
        "address_change_required": bool(source.get("address_change_required")),
        "screenshot_policy": _screenshot_policy_from_capture(capture, staged_screenshots),
        "screenshot": screenshot,
        "warnings": warnings,
        "notes": source.get("notes"),
    }


def _write_warnings(path: Path, warnings: list[str]) -> None:
    if not warnings:
        write_text(path, "No warnings.\n")
        return
    lines = ["# Warnings", ""]
    lines.extend(f"- {warning}" for warning in warnings)
    write_text(path, "\n".join(lines) + "\n")


def _manual_review_reason(code: str, severity: str = "warning") -> dict[str, str]:
    return {
        "code": code,
        "message": code.replace("_", " "),
        "severity": severity,
        "artifact": "validation/price-validation-report.json",
    }


def _augment_validation_report(
    report: dict[str, Any],
    *,
    capture_warnings: list[str],
    capture_failures: list[str],
    captured_source_count: int,
) -> dict[str, Any]:
    augmented = dict(report)
    warnings = list(dict.fromkeys(list(augmented.get("warnings") or []) + capture_warnings + capture_failures))
    errors = list(augmented.get("errors") or [])
    manual_review = bool(augmented.get("requires_manual_review") or capture_warnings or capture_failures)
    if captured_source_count == 0 and "all_product_captures_failed" not in errors:
        errors.append("all_product_captures_failed")
    status = "fail" if errors else str(augmented.get("status") or "pass")
    run_status = "failed" if status == "fail" else "partial" if manual_review else "complete"
    reasons = list(augmented.get("manual_review", {}).get("reasons") or [])
    reasons.extend(_manual_review_reason(warning) for warning in capture_warnings)
    reasons.extend(_manual_review_reason(failure, "blocking" if captured_source_count == 0 else "warning") for failure in capture_failures)
    blockers = list(dict.fromkeys(list(augmented.get("completion_blockers") or []) + errors))
    augmented.update(
        {
            "status": status,
            "errors": errors,
            "warnings": warnings,
            "requires_manual_review": manual_review or bool(errors),
            "run_status": run_status,
            "validation_status": "passed" if status == "pass" else "failed",
            "manual_review": {
                "required": manual_review or bool(errors),
                "severity": "blocking" if status == "fail" else "warning" if manual_review else "info",
                "reasons": reasons,
            },
            "completion_blockers": blockers,
        }
    )
    return augmented


def _manifest_screenshot_sha(run_dir: Path, evidence: list[dict[str, Any]]) -> None:
    for item in evidence:
        if item.get("type") == "screenshot" and item.get("path"):
            path = run_dir / str(item["path"])
            if path.exists():
                item["sha256"] = _sha256_file(path)


def _augment_manifest(
    run_dir: Path,
    *,
    input_record: dict[str, Any],
    capture_evidence: list[dict[str, Any]],
    screenshot_evidence: list[dict[str, Any]],
    validation_report: dict[str, Any],
    warnings: list[str],
) -> None:
    manifest_path = run_dir / "manifest.json"
    manifest = read_json(manifest_path)
    evidence = list(manifest.get("evidence") or [])
    _manifest_screenshot_sha(run_dir, evidence)
    seen_paths = {item.get("path") for item in evidence if isinstance(item, dict)}
    for item in capture_evidence + screenshot_evidence:
        if item["path"] not in seen_paths:
            evidence.append(item)
            seen_paths.add(item["path"])
    _manifest_screenshot_sha(run_dir, evidence)
    manifest["inputs"] = input_record
    manifest["evidence"] = evidence
    manifest["warnings"] = list(dict.fromkeys(list(manifest.get("warnings") or []) + warnings + list(validation_report.get("warnings") or [])))
    manifest["requires_manual_review"] = bool(validation_report.get("requires_manual_review"))
    manifest["run_status"] = validation_report.get("run_status", manifest.get("run_status"))
    manifest["validation_status"] = validation_report.get("validation_status", manifest.get("validation_status"))
    manifest["manual_review"] = validation_report.get("manual_review", manifest.get("manual_review"))
    manifest["completion_blockers"] = validation_report.get("completion_blockers", manifest.get("completion_blockers", []))
    manifest["validation"] = {
        **(manifest.get("validation") or {}),
        "schema_valid": validation_report.get("status") == "pass",
        "warnings": len(validation_report.get("warnings", [])),
        "requires_manual_review": bool(validation_report.get("requires_manual_review")),
        "report_path": "validation/price-validation-report.json",
    }
    write_json(manifest_path, manifest)


def _write_aborted_run(
    run_dir: Path,
    *,
    run_id: str,
    started_at: str,
    input_record: dict[str, Any],
    capture_evidence: list[dict[str, Any]],
    screenshot_evidence: list[dict[str, Any]],
    reasons: list[str],
) -> None:
    validation_report = {
        "schema_version": "1.0",
        "status": "fail",
        "errors": ["aborted_by_policy"],
        "warnings": reasons,
        "requires_manual_review": True,
        "run_status": "aborted_by_policy",
        "validation_status": "failed",
        "manual_review": {
            "required": True,
            "severity": "blocking",
            "reasons": [_manual_review_reason(reason, "blocking") for reason in reasons],
        },
        "completion_blockers": ["aborted_by_policy"],
        "screenshot_policy": {"required": True, "reason": "ecommerce_product_pages", "status": "capture_failed"},
    }
    evidence = capture_evidence + screenshot_evidence
    _manifest_screenshot_sha(run_dir, evidence)
    write_json(run_dir / "input.json", input_record)
    write_json(run_dir / "validation" / "price-validation-report.json", validation_report)
    _write_warnings(run_dir / "validation" / "warnings.md", reasons)
    write_json(
        run_dir / "manifest.json",
        {
            "run_id": run_id,
            "task": "price-compare",
            "started_at": started_at,
            "finished_at": utc_now(),
            "operator": "codex",
            "skill": "price-compare",
            "inputs": input_record,
            "artifacts": [],
            "evidence": evidence,
            "validation": {
                "schema_valid": False,
                "warnings": len(reasons),
                "requires_manual_review": True,
                "report_path": "validation/price-validation-report.json",
            },
            "warnings": reasons,
            "requires_manual_review": True,
            "run_status": "aborted_by_policy",
            "validation_status": "failed",
            "manual_review": validation_report["manual_review"],
            "completion_blockers": ["aborted_by_policy"],
            "screenshot_policy": {"required": True, "reason": "ecommerce_product_pages", "status": "capture_failed"},
        },
    )


def run(args: argparse.Namespace) -> Path:
    started_at = utc_now()
    run_id = args.run_id or f"{_slug_timestamp(started_at)}-price-capture"
    output_root = Path(args.output_root or "browser-operator-runs").resolve()
    run_dir = output_root / run_id
    (run_dir / "capture").mkdir(parents=True, exist_ok=True)
    (run_dir / "evidence").mkdir(parents=True, exist_ok=True)
    (run_dir / "validation").mkdir(parents=True, exist_ok=True)

    spec, input_path = _load_spec(args)
    sources = _source_records(spec)
    _validate_scope(spec, sources, min_urls=args.min_urls, max_urls=args.max_urls)

    product = spec.get("product") if isinstance(spec.get("product"), dict) else {}
    region = spec.get("region")
    currency = spec.get("currency")
    adapter_stage_root = run_dir / "capture" / "_adapter-stage"
    candidates: list[dict[str, Any]] = []
    quotes: list[dict[str, Any]] = []
    capture_evidence: list[dict[str, Any]] = []
    screenshot_evidence: list[dict[str, Any]] = []
    capture_warnings: list[str] = []
    capture_failures: list[str] = []
    aborted_by_policy: list[str] = []

    try:
        for index, source in enumerate(sources[: args.max_urls], start=1):
            source_id = str(source.get("source_id") or f"S{index:03d}")
            source_dir = run_dir / "capture" / source_dir_name(source_id)
            source_dir.mkdir(parents=True, exist_ok=True)
            command = _capture_command(
                source=source,
                source_index=index,
                adapter_output_root=adapter_stage_root,
                final_source_dir=source_dir,
                input_path=input_path,
            )
            completed = subprocess.run(command, cwd=Path(__file__).resolve().parents[1], text=True, capture_output=True)
            adapter_run_dir = adapter_stage_root / f"source-{index:03d}"
            adapter_capture_path = adapter_run_dir / "capture" / "page_capture.json"
            adapter_report_path = adapter_run_dir / "validation" / "capture-validation-report.json"
            adapter_manifest_path = adapter_run_dir / "manifest.json"
            final_capture_path = source_dir / "page_capture.json"
            final_report_path = source_dir / "capture-validation-report.json"
            capture = _read_json_if_exists(adapter_capture_path)
            capture_report = _read_json_if_exists(adapter_report_path)
            adapter_manifest = _read_json_if_exists(adapter_manifest_path)
            source_warnings: list[str] = []
            if capture:
                write_json(final_capture_path, capture)
                capture_evidence.append(
                    {
                        "id": f"C{index:03d}",
                        "type": "page_capture",
                        "path": final_capture_path.relative_to(run_dir).as_posix(),
                        "url": capture.get("source", {}).get("url"),
                        "captured_at": capture.get("captured_at"),
                    }
                )
                staged_screenshots = _stage_source_screenshots(
                    capture=capture,
                    capture_path=adapter_capture_path,
                    run_dir=run_dir,
                    source_id=source_id,
                    warnings=source_warnings,
                )
                for screenshot_index, screenshot in enumerate(staged_screenshots, start=1):
                    screenshot_evidence.append(
                        {
                            "id": f"SS{index:03d}-{screenshot_index:03d}",
                            "type": "screenshot",
                            "path": screenshot["path"],
                            "captured_at": screenshot.get("captured_at"),
                            "sha256": screenshot.get("sha256"),
                        }
                    )
            else:
                staged_screenshots = []
                failure_code = f"{source_id}:capture_failed"
                capture_failures.append(failure_code)
                source_warnings.append(failure_code)
            if capture_report:
                write_json(final_report_path, capture_report)
            if adapter_manifest and adapter_manifest.get("run_status") == "aborted_by_policy":
                aborted_by_policy.append(f"{source_id}:aborted_by_policy")
            if completed.returncode != 0:
                if capture:
                    source_warnings.append(f"{source_id}:adapter_validation_failed")
                else:
                    source_warnings.append(f"{source_id}:adapter_returncode:{completed.returncode}")
            capture_warnings.extend(source_warnings)
            candidates.append(
                _candidate_from_source(
                    source=source,
                    source_index=index,
                    source_id=source_id,
                    capture=capture,
                    region=str(region) if region is not None else None,
                    currency=str(currency) if currency is not None else None,
                )
            )
            quotes.append(
                _quote_from_source(
                    source=source,
                    source_index=index,
                    source_id=source_id,
                    capture=capture,
                    capture_report=capture_report,
                    staged_screenshots=staged_screenshots,
                    source_warnings=source_warnings,
                    accessed_at=started_at,
                    region=str(region) if region is not None else None,
                    currency=str(currency) if currency is not None else None,
                )
            )
    finally:
        if adapter_stage_root.exists():
            shutil.rmtree(adapter_stage_root)

    input_record = {
        "input_path": str(input_path) if input_path else None,
        "generated_price_input": "capture/price-input.json",
        "target_product": product,
        "region": region,
        "currency": currency,
        "approved_product_urls": [source.get("url") for source in sources],
        "product_url_count": len(sources),
        "captured_source_count": len(capture_evidence),
        "max_urls": args.max_urls,
        "workflow": "price-compare",
        "capture_stage": "provided_url_product_quote_capture",
        "candidate_assessment": "provided_url_candidate_assessment",
    }

    if aborted_by_policy:
        _write_aborted_run(
            run_dir,
            run_id=run_id,
            started_at=started_at,
            input_record=input_record,
            capture_evidence=capture_evidence,
            screenshot_evidence=screenshot_evidence,
            reasons=list(dict.fromkeys(aborted_by_policy + capture_warnings + capture_failures)),
        )
        print(run_dir)
        return run_dir

    warnings = list(dict.fromkeys(_strings(spec.get("warnings")) + capture_warnings + capture_failures))
    price_input = {
        "schema_version": "1.0",
        "title": spec.get("title") or f"{product.get('target_name')} price comparison",
        "region": region,
        "currency": currency,
        "product": product,
        "candidates": candidates,
        "quotes": quotes,
        "warnings": warnings,
    }
    price_input_path = run_dir / "capture" / "price-input.json"
    write_json(price_input_path, price_input)

    runner_command = [
        sys.executable,
        str(SCRIPT_ROOT / "price_compare_runner.py"),
        "--input",
        str(price_input_path),
        "--output-root",
        str(output_root),
        "--run-id",
        run_id,
    ]
    completed_runner = subprocess.run(runner_command, cwd=Path(__file__).resolve().parents[1], text=True, capture_output=True)
    if completed_runner.returncode != 0:
        raise SystemExit(completed_runner.stderr.strip() or "price_compare_runner.py failed")

    validation_path = run_dir / "validation" / "price-validation-report.json"
    validation_report = read_json(validation_path)
    augmented_report = _augment_validation_report(
        validation_report,
        capture_warnings=list(dict.fromkeys(capture_warnings)),
        capture_failures=list(dict.fromkeys(capture_failures)),
        captured_source_count=len(capture_evidence),
    )
    write_json(validation_path, augmented_report)
    final_validation_report = validate_price_compare_run(run_dir)
    augmented_report = _augment_validation_report(
        final_validation_report,
        capture_warnings=list(dict.fromkeys(capture_warnings)),
        capture_failures=list(dict.fromkeys(capture_failures)),
        captured_source_count=len(capture_evidence),
    )
    write_json(validation_path, augmented_report)
    _write_warnings(run_dir / "validation" / "warnings.md", list(dict.fromkeys(warnings + augmented_report.get("warnings", []))))

    write_json(run_dir / "input.json", input_record)
    _augment_manifest(
        run_dir,
        input_record=input_record,
        capture_evidence=capture_evidence + [{"id": "PI001", "type": "price_input", "path": "capture/price-input.json"}],
        screenshot_evidence=screenshot_evidence,
        validation_report=augmented_report,
        warnings=list(dict.fromkeys(warnings)),
    )
    final_validation_report = validate_price_compare_run(run_dir)
    augmented_report = _augment_validation_report(
        final_validation_report,
        capture_warnings=list(dict.fromkeys(capture_warnings)),
        capture_failures=list(dict.fromkeys(capture_failures)),
        captured_source_count=len(capture_evidence),
    )
    write_json(validation_path, augmented_report)
    _augment_manifest(
        run_dir,
        input_record=input_record,
        capture_evidence=capture_evidence + [{"id": "PI001", "type": "price_input", "path": "capture/price-input.json"}],
        screenshot_evidence=screenshot_evidence,
        validation_report=augmented_report,
        warnings=list(dict.fromkeys(warnings)),
    )
    _write_warnings(run_dir / "validation" / "warnings.md", list(dict.fromkeys(warnings + augmented_report.get("warnings", []))))
    print(run_dir)
    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Capture user-approved product URLs, build price input, run existing price-compare pipeline."
    )
    parser.add_argument("--input", help="M9 product URL price capture JSON spec.")
    parser.add_argument("--target-name", help="Target product name.")
    parser.add_argument("--required-spec", action="append", default=[], help="Required product spec as key=value. May be repeated.")
    parser.add_argument("--url", action="append", default=[], help="Approved product URL. May be repeated.")
    parser.add_argument("--region", help="Optional comparison region constraint.")
    parser.add_argument("--currency", help="Optional comparison currency constraint.")
    parser.add_argument("--output-root", default="browser-operator-runs")
    parser.add_argument("--run-id")
    parser.add_argument("--max-urls", type=int, default=20)
    parser.add_argument("--min-urls", type=int, default=2)
    args = parser.parse_args()
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
