---
doc_type: phase_plan
phase_id: m4_m5_price_pluginization_mvp
title: price-compare and pluginization MVP
status: completed
canonical: true
related_contracts:
  - docs/contracts/evidence-contract.md
  - docs/contracts/browser-operation-contract.md
  - docs/contracts/schemas-and-validation-contract.md
  - docs/contracts/safety-contract.md
related_adrs:
  - docs/adr/0001-evidence-first-browser-workflows.md
---

# M4-M5 price-compare and Pluginization MVP

## Status

Completed. The user approved starting M4 and M5 on 2026-06-09; the closeout is `docs/planning/archive/m4-m5-price-pluginization-mvp-closeout.md`.

## Scope

Implement the smallest deterministic M4/M5 loop:

- Local price input JSON with candidate discovery and quote extraction sections.
- `prices.json` as the structured price comparison record.
- `prices.csv`, `price-report.md`, `anomalies.md`, and `price-chart.png` rendered from structured data.
- One source record per quote and screenshot evidence policy enforcement.
- `price-validation-report.json`.
- `price-compare` skill.
- Updated plugin manifest/docs/examples so the local plugin validates with `page-to-md`, `browser-research`, and `price-compare`.

Real ecommerce browsing, MCP/browser adapters, broad product discovery, marketplace installation, and package distribution remain out of scope for this slice.

## Success Criteria

- Product names and specs remain separate.
- Region, currency, seller, condition, stock, URL, timestamp, screenshot policy, and source records exist for every quote.
- List price, sale price, coupon price, shipping fee, and estimated total remain separate.
- Low-confidence, incomplete-spec, out-of-stock, unknown-total, cart/checkout/coupon-claim, and address-change quotes are excluded from final lowest-price conclusions.
- Anomalies are listed in structured JSON and Markdown.
- Plugin validation passes.

## Current Gates

- `python -m py_compile scripts\price_compare_runner.py scripts\validation\validate_price_compare.py scripts\inward_eyes\price.py scripts\inward_eyes\validation.py evals\run_price_eval.py`
- `python evals\run_price_eval.py`
- `python scripts\validation\validate_json_schema.py --schema schemas\price_compare_run.schema.json --json evals\.tmp\price-compare\eval-product-quotes\artifacts\prices.json`
- `python scripts\validation\validate_json_schema.py --schema schemas\price_record.schema.json --json evals\.tmp\price-compare\eval-product-quotes\artifacts\prices.json --pointer /quotes/0`
- `python scripts\validation\validate_json_schema.py --schema schemas\run_manifest.schema.json --json evals\.tmp\price-compare\eval-product-quotes\manifest.json`
- `python scripts\validation\validate_json_schema.py --schema schemas\validation_report.schema.json --json evals\.tmp\price-compare\eval-product-quotes\validation\price-validation-report.json`
- `python C:\Users\62406\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py "E:\Inward Eyes"`
