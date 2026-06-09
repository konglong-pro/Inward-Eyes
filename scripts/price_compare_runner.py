from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parent
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from inward_eyes.io import read_json, utc_now, write_json, write_text
from inward_eyes.price import (
    build_price_model,
    quote_evidence_name,
    render_anomalies,
    render_price_chart_png,
    render_price_report,
    render_prices_csv,
    render_screenshot_fixture_png,
    source_dir_name,
    source_record_from_quote,
)
from inward_eyes.validation import validate_price_compare_run


def _slug_timestamp(timestamp: str) -> str:
    return re.sub(r"[^0-9TZ]", "", timestamp)


def create_manifest(
    run_id: str,
    started_at: str,
    finished_at: str,
    input_record: dict[str, Any],
    model: dict[str, Any],
    validation_report: dict[str, Any] | None,
) -> dict[str, Any]:
    validation = validation_report or {"status": "pending", "warnings": [], "requires_manual_review": False}
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
        if quote.get("screenshot"):
            evidence.append({"id": f"{quote['source_id']}-screenshot", "type": "screenshot", "path": quote["screenshot"]})
    if validation_report is not None:
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
        "screenshot_policy": {"required": True, "reason": "ecommerce_product_pages", "status": "per_quote_policy"},
    }


def run(args: argparse.Namespace) -> Path:
    input_path = Path(args.input).resolve()
    if not input_path.exists():
        raise SystemExit(f"input does not exist: {input_path}")

    started_at = utc_now()
    run_id = args.run_id or f"{_slug_timestamp(started_at)}-price-compare"
    output_root = Path(args.output_root or "browser-operator-runs").resolve()
    run_dir = output_root / run_id
    (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    (run_dir / "evidence").mkdir(parents=True, exist_ok=True)
    (run_dir / "validation").mkdir(parents=True, exist_ok=True)

    raw_input = read_json(input_path)
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

    model = build_price_model(raw_input, started_at)
    write_json(run_dir / "artifacts" / "prices.json", model)
    write_text(run_dir / "artifacts" / "prices.csv", render_prices_csv(model["quotes"]))
    write_text(run_dir / "artifacts" / "price-report.md", render_price_report(model))
    write_text(run_dir / "artifacts" / "anomalies.md", render_anomalies(model))
    (run_dir / "artifacts" / "price-chart.png").write_bytes(render_price_chart_png(model))

    for quote in model["quotes"]:
        source_dir = run_dir / "evidence" / source_dir_name(quote["source_id"])
        source_dir.mkdir(parents=True, exist_ok=True)
        write_json(source_dir / "source_record.json", source_record_from_quote(quote))
        if quote.get("screenshot_fixture") and quote.get("screenshot"):
            screenshot_path = run_dir / quote["screenshot"]
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)
            screenshot_path.write_bytes(render_screenshot_fixture_png())
        elif quote.get("screenshot") and quote["screenshot"].startswith("evidence/") and quote.get("screenshot_policy", {}).get("status") == "required_and_present":
            screenshot_path = run_dir / quote["screenshot"]
            if not screenshot_path.exists() and quote.get("screenshot_fixture"):
                screenshot_path.write_bytes(render_screenshot_fixture_png())
        elif quote.get("screenshot_policy", {}).get("status") == "required_and_present" and quote.get("screenshot_fixture"):
            screenshot_path = run_dir / "evidence" / quote_evidence_name(quote)
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)
            screenshot_path.write_bytes(render_screenshot_fixture_png())

    draft_manifest = create_manifest(run_id, started_at, utc_now(), input_record, model, None)
    write_json(run_dir / "manifest.json", draft_manifest)
    validation_report = validate_price_compare_run(run_dir)
    write_json(run_dir / "validation" / "price-validation-report.json", validation_report)
    final_manifest = create_manifest(run_id, started_at, utc_now(), input_record, model, validation_report)
    write_json(run_dir / "manifest.json", final_manifest)
    final_validation_report = validate_price_compare_run(run_dir)
    write_json(run_dir / "validation" / "price-validation-report.json", final_validation_report)
    final_manifest = create_manifest(run_id, started_at, utc_now(), input_record, model, final_validation_report)
    write_json(run_dir / "manifest.json", final_manifest)
    print(run_dir)
    return run_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Render and validate an evidence-backed price comparison run.")
    parser.add_argument("--input", required=True, help="Local price-compare input JSON.")
    parser.add_argument("--output-root", default="browser-operator-runs", help="Directory where run outputs are written.")
    parser.add_argument("--run-id", help="Optional run id.")
    args = parser.parse_args()
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
