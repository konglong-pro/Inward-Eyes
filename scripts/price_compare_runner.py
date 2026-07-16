from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from inward_eyes.io import utc_now, write_bytes, write_json, write_text
from inward_eyes.capture import screenshot_file_is_valid
from inward_eyes.paths import prepare_run_dir, resolve_run_relative, validate_run_id, validate_source_id
from inward_eyes.price import (
    build_price_model,
    render_anomalies,
    render_price_chart_png,
    render_price_report,
    render_prices_csv,
    source_dir_name,
    source_record_from_quote,
)
from inward_eyes.validation import validate_price_compare_run

PRICE_COMPARE_STAGE_MANIFEST = "validation/price-compare-stage-manifest.json"


def _slug_timestamp(timestamp: str) -> str:
    return re.sub(r"[^0-9TZ]", "", timestamp)


SCREENSHOT_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _sha256_bytes(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _canonical_input_relative_path(raw_path: Any, *, label: str) -> Path:
    value = str(raw_path)
    if (
        not value
        or "\x00" in value
        or "\\" in value
        or ":" in value
        or value.startswith("/")
        or value.endswith("/")
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise ValueError(f"{label} must be a canonical input-relative path")
    return Path(*value.split("/"))


def _screenshot_bytes_are_valid(data: bytes, suffix: str) -> bool:
    header = data[:12]
    if suffix == ".png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    if suffix in {".jpg", ".jpeg"}:
        return header.startswith(b"\xff\xd8\xff")
    if suffix == ".gif":
        return header.startswith((b"GIF87a", b"GIF89a"))
    return suffix == ".webp" and len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP"


def _preflight_price_screenshots(
    raw_input: dict[str, Any],
    *,
    input_path: Path,
    expected_run_dir: Path,
) -> list[tuple[str, bytes]]:
    staged_files: list[tuple[str, bytes]] = []
    quotes = raw_input.get("quotes") if isinstance(raw_input.get("quotes"), list) else []
    for index, raw_quote in enumerate(quotes, start=1):
        if not isinstance(raw_quote, dict):
            continue
        warnings = raw_quote.get("warnings") if isinstance(raw_quote.get("warnings"), list) else []
        raw_quote["warnings"] = warnings
        if raw_quote.pop("screenshot_fixture", False):
            warnings.append("screenshot_fixture_forbidden")
        source_id = validate_source_id(str(raw_quote.get("source_id") or f"S{index:03d}"))
        expected_screenshot_prefix = f"evidence/{source_dir_name(source_id)}/screenshots/"
        screenshot_present = False
        screenshot_source = raw_quote.pop("screenshot_source", None)
        if screenshot_source:
            source_relative = _canonical_input_relative_path(
                screenshot_source,
                label=f"quote {index} screenshot_source",
            )
            source_root = input_path.parent.resolve()
            source = (source_root / source_relative).resolve()
            try:
                source.relative_to(source_root)
            except ValueError as exc:
                raise ValueError(f"quote {index} screenshot_source escapes the input directory") from exc
            try:
                screenshot_bytes = source.read_bytes()
            except OSError:
                screenshot_bytes = b""
            suffix = source.suffix.lower()
            if suffix in SCREENSHOT_EXTENSIONS and _screenshot_bytes_are_valid(screenshot_bytes, suffix):
                destination_relative = f"{expected_screenshot_prefix}{index:03d}{suffix}"
                staged_files.append((destination_relative, screenshot_bytes))
                raw_quote["screenshot"] = destination_relative
                raw_quote["screenshot_policy"] = {
                    "required": True,
                    "reason": "product_page",
                    "status": "required_and_present",
                }
                screenshot_present = True
            else:
                warnings.append("screenshot_source_missing_or_invalid")
        screenshot = raw_quote.get("screenshot")
        if screenshot and not screenshot_present:
            screenshot_value = str(screenshot)
            if not screenshot_value.startswith(expected_screenshot_prefix):
                raise ValueError(f"quote {index} screenshot path must belong to source_id {source_id}")
            try:
                screenshot_path = resolve_run_relative(expected_run_dir, screenshot_value)
            except ValueError as exc:
                raise ValueError(f"quote {index} screenshot path must be canonical run-relative") from exc
            screenshot_present = screenshot_file_is_valid(screenshot_path)
            if not screenshot_present:
                warnings.append("screenshot_path_missing_or_invalid")
        policy = raw_quote.get("screenshot_policy") if isinstance(raw_quote.get("screenshot_policy"), dict) else {}
        if screenshot and not screenshot_present:
            raw_quote["screenshot"] = None
            raw_quote["screenshot_policy"] = {
                "required": True,
                "reason": str(policy.get("reason") or "product_page"),
                "status": "required_but_missing",
            }
    return staged_files


def _stage_price_screenshots(run_dir: Path, staged_files: list[tuple[str, bytes]]) -> None:
    for relative_path, screenshot_bytes in staged_files:
        destination = resolve_run_relative(run_dir, relative_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        write_bytes(destination, screenshot_bytes)
        if not screenshot_file_is_valid(destination):
            destination.unlink(missing_ok=True)
            raise RuntimeError(f"staged screenshot failed integrity validation: {relative_path}")


def create_manifest(
    run_dir: Path,
    run_id: str,
    started_at: str,
    finished_at: str,
    input_record: dict[str, Any],
    model: dict[str, Any],
    validation_report: dict[str, Any],
) -> dict[str, Any]:
    validation = validation_report
    evidence = []
    for quote in model["quotes"]:
        evidence.append(
            {
                "id": quote["source_id"],
                "type": "source_record",
                "path": quote["source_record_path"],
                "url": quote.get("url"),
                "captured_at": quote.get("accessed_at"),
            }
        )
        if quote.get("screenshot") and quote.get("screenshot_policy", {}).get("status") == "required_and_present":
            try:
                screenshot_path = resolve_run_relative(run_dir, str(quote["screenshot"]), must_exist=True)
            except (ValueError, FileNotFoundError):
                continue
            evidence.append(
                {
                    "id": f"{quote['source_id']}-screenshot",
                    "type": "screenshot",
                    "path": quote["screenshot"],
                    "sha256": _sha256_file(screenshot_path),
                }
            )
    evidence.append({"id": "V001", "type": "validation_report", "path": "validation/price-validation-report.json"})

    return {
        "run_id": run_id,
        "task": "price-compare",
        "started_at": started_at,
        "finished_at": finished_at,
        "operator": "codex",
        "skill": "price-compare",
        "inputs": input_record,
        "artifacts": [
            {"id": "A001", "type": "prices_json", "path": "artifacts/prices.json"},
            {"id": "A002", "type": "prices_csv", "path": "artifacts/prices.csv"},
            {"id": "A003", "type": "markdown_report", "path": "artifacts/price-report.md"},
            {"id": "A004", "type": "anomalies", "path": "artifacts/anomalies.md"},
            {"id": "A005", "type": "chart", "path": "artifacts/price-chart.png"},
        ],
        "evidence": evidence,
        "validation": {
            "schema_valid": validation.get("status") == "pass",
            "warnings": len(validation.get("warnings", [])),
            "requires_manual_review": bool(validation.get("requires_manual_review")),
            "report_path": "validation/price-validation-report.json",
        },
        "warnings": list(model.get("warnings") or []) + list(validation.get("warnings", [])),
        "requires_manual_review": bool(validation.get("requires_manual_review")),
        "run_status": validation.get("run_status", "failed" if validation.get("status") == "fail" else "partial" if validation.get("requires_manual_review") else "complete"),
        "validation_status": validation.get("validation_status")
        if validation.get("validation_status") in {"passed", "failed"}
        else "failed",
        "manual_review": validation.get(
            "manual_review",
            {"required": bool(validation.get("requires_manual_review")), "severity": "warning" if validation.get("requires_manual_review") else "info", "reasons": []},
        ),
        "completion_blockers": validation.get("completion_blockers", []),
        "screenshot_policy": {"required": True, "reason": "ecommerce_product_pages", "status": "per_quote_policy"},
    }


def run(args: argparse.Namespace) -> Path:
    input_path = Path(args.input).resolve()
    if not input_path.exists():
        raise SystemExit(f"input does not exist: {input_path}")
    input_bytes = input_path.read_bytes()
    raw_input = json.loads(input_bytes.decode("utf-8"))
    if not isinstance(raw_input, dict):
        raise SystemExit("price-compare input must be a JSON object")

    started_at = utc_now()
    run_id = validate_run_id(args.run_id or f"{_slug_timestamp(started_at)}-price-compare")
    output_root = Path(args.output_root or "browser-operator-runs").resolve()
    expected_run_dir = resolve_run_relative(output_root, run_id)
    continue_existing = bool(getattr(args, "continue_existing_run", False))
    defer_manifest = bool(getattr(args, "defer_manifest", False))
    if continue_existing and not defer_manifest:
        raise SystemExit("authenticated continuation requires --defer-manifest")
    if defer_manifest and not continue_existing:
        raise SystemExit("deferred price-compare manifest requires authenticated continuation")
    if continue_existing and input_path != (expected_run_dir / "capture" / "price-input.json").resolve():
        raise SystemExit("continued price-compare run must consume capture/price-input.json from that run")
    staged_screenshots = _preflight_price_screenshots(
        raw_input,
        input_path=input_path,
        expected_run_dir=expected_run_dir,
    )
    model = build_price_model(raw_input, started_at)
    run_dir = prepare_run_dir(
        output_root,
        run_id,
        continue_existing=continue_existing,
        continuation_required_paths=("capture/price-input.json",) if continue_existing else (),
        continuation_token=getattr(args, "continuation_token", None),
        continuation_stage="price-compare-render" if continue_existing else None,
        continuation_input_path="capture/price-input.json" if continue_existing else None,
        continuation_artifact_sha256=(
            {"capture/price-input.json": _sha256_bytes(input_bytes)}
            if continue_existing
            else None
        ),
    )
    (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    (run_dir / "evidence").mkdir(parents=True, exist_ok=True)
    (run_dir / "validation").mkdir(parents=True, exist_ok=True)

    _stage_price_screenshots(run_dir, staged_screenshots)
    input_record = {
        "input_path": str(input_path),
        "title": raw_input.get("title"),
        "region": raw_input.get("region"),
        "currency": raw_input.get("currency"),
        "product": raw_input.get("product"),
        "candidate_count": len(raw_input.get("candidates", [])) if isinstance(raw_input.get("candidates"), list) else 0,
        "quote_count": len(raw_input.get("quotes", [])) if isinstance(raw_input.get("quotes"), list) else 0,
    }
    write_json(run_dir / "input.json", input_record)

    write_json(run_dir / "artifacts" / "prices.json", model)
    write_text(run_dir / "artifacts" / "prices.csv", render_prices_csv(model["quotes"]))
    write_text(run_dir / "artifacts" / "price-report.md", render_price_report(model))
    write_text(run_dir / "artifacts" / "anomalies.md", render_anomalies(model))
    write_bytes(run_dir / "artifacts" / "price-chart.png", render_price_chart_png(model))

    for quote in model["quotes"]:
        source_dir = run_dir / "evidence" / source_dir_name(quote["source_id"])
        source_dir.mkdir(parents=True, exist_ok=True)
        write_json(source_dir / "source_record.json", source_record_from_quote(quote))
    final_validation_report = validate_price_compare_run(
        run_dir,
        manifest_override={},
        skip_manifest_validation=True,
    )
    final_manifest: dict[str, Any] | None = None
    for _ in range(4):
        candidate_manifest = create_manifest(
            run_dir,
            run_id,
            started_at,
            utc_now(),
            input_record,
            model,
            final_validation_report,
        )
        checked_report = validate_price_compare_run(
            run_dir,
            manifest_override=candidate_manifest,
            pending_manifest_paths={"validation/price-validation-report.json"},
        )
        if checked_report == final_validation_report:
            final_manifest = candidate_manifest
            break
        final_validation_report = checked_report
    if final_manifest is None:
        raise RuntimeError("price-compare manifest validation did not converge")
    write_json(run_dir / "validation" / "price-validation-report.json", final_validation_report)
    manifest_output = PRICE_COMPARE_STAGE_MANIFEST if defer_manifest else "manifest.json"
    write_json(resolve_run_relative(run_dir, manifest_output), final_manifest)
    print(run_dir)
    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Render and validate an evidence-backed price comparison run.")
    parser.add_argument("--input", required=True, help="Local price-compare input JSON.")
    parser.add_argument("--output-root", default="browser-operator-runs", help="Directory where run outputs are written.")
    parser.add_argument("--run-id", help="Optional run id.")
    parser.add_argument(
        "--continue-existing-run",
        action="store_true",
        help="Continue a capture-orchestrated run using its canonical capture/price-input.json.",
    )
    parser.add_argument("--continuation-token", help=argparse.SUPPRESS)
    parser.add_argument("--defer-manifest", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
