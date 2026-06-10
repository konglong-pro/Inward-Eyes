# Current Active Work

Last updated: 2026-06-09
Source of current phase: `docs/phase-manifest.yaml`

## Current State

- Shipped/frozen: M0-M2 foundation and `page-to-md` MVP baseline.
- Completed: M3 `browser-research` MVP local runner, claim ledger, validation, and eval slice.
- Completed: M4-M5 `price-compare` and pluginization MVP local runner, validation, eval, packaging, and CI slice.
- Active: none.
- Next but not active: real browser/MCP adapters, broad product discovery, marketplace installation, and package distribution.

## Active Objective

No implementation phase is currently active. M0-M5 MVP work is closed as Inward Eyes v0.2: deterministic local evidence workflows complete; real browser adapter layer not implemented.

## Required Reading for Future Work

- `AGENTS.md`
- `docs/project-status.md`
- `docs/planning/archive/m0-m2-closeout.md`
- `docs/planning/archive/m3-browser-research-mvp-closeout.md`
- `docs/planning/archive/m4-m5-price-pluginization-mvp-closeout.md`
- `docs/planning/next/m6-browser-capture-adapter-mvp.md`
- `docs/planning/next/m3-m5-research-price-pluginization.md`
- `docs/contracts/evidence-contract.md`
- `docs/contracts/capture-adapter-contract.md`
- `docs/contracts/browser-operation-contract.md`
- `docs/contracts/schemas-and-validation-contract.md`
- `docs/contracts/safety-contract.md`

## Explicitly Out of Scope Unless Reapproved

- Installing browser automation dependencies.
- Creating runnable MCP servers.
- Capturing real user browser pages.
- Broad product discovery.
- Marketplace installation or distribution.
- Large-scale crawling.
- Automated purchases, posting, account mutation, coupon claiming, CAPTCHA handling, stealth browsing, proxies, or anti-bot bypass.

## Current Gates

- `python -m py_compile scripts\page_to_md_runner.py scripts\markdown\render_page_md.py scripts\validation\validate_page_to_md.py scripts\validation\validate_json_schema.py scripts\validation\classify_browser_action.py scripts\validation\validate_browser_research.py scripts\validation\validate_price_compare.py scripts\inward_eyes\__init__.py scripts\inward_eyes\html_extract.py scripts\inward_eyes\io.py scripts\inward_eyes\markdown.py scripts\inward_eyes\safety.py scripts\inward_eyes\validation.py scripts\inward_eyes\research.py scripts\inward_eyes\price.py scripts\browser_research_runner.py scripts\price_compare_runner.py evals\run_eval.py evals\run_safety_eval.py evals\run_research_eval.py evals\run_price_eval.py`
- `python evals\run_eval.py`
- `python evals\run_safety_eval.py`
- `python evals\run_research_eval.py`
- `python evals\run_price_eval.py`
- `python scripts\validation\validate_json_schema.py --schema schemas\page_to_md_metadata.schema.json --json evals\.tmp\page-to-md\eval-public-article\artifacts\metadata.json`
- `python scripts\validation\validate_json_schema.py --schema schemas\run_manifest.schema.json --json evals\.tmp\page-to-md\eval-public-article\manifest.json`
- `python scripts\validation\validate_json_schema.py --schema schemas\validation_report.schema.json --json evals\.tmp\page-to-md\eval-public-article\validation\validation-report.json`
- `python scripts\validation\validate_json_schema.py --schema schemas\research_report.schema.json --json evals\.tmp\browser-research\eval-evidence-backed-research\artifacts\claims.json`
- `python scripts\validation\validate_json_schema.py --schema schemas\run_manifest.schema.json --json evals\.tmp\browser-research\eval-evidence-backed-research\manifest.json`
- `python scripts\validation\validate_json_schema.py --schema schemas\validation_report.schema.json --json evals\.tmp\browser-research\eval-evidence-backed-research\validation\claim-coverage-report.json`
- `python scripts\validation\validate_json_schema.py --schema schemas\price_compare_run.schema.json --json evals\.tmp\price-compare\eval-product-quotes\artifacts\prices.json`
- `python scripts\validation\validate_json_schema.py --schema schemas\price_record.schema.json --json evals\.tmp\price-compare\eval-product-quotes\artifacts\prices.json --pointer /quotes/0`
- `python scripts\validation\validate_json_schema.py --schema schemas\run_manifest.schema.json --json evals\.tmp\price-compare\eval-product-quotes\manifest.json`
- `python scripts\validation\validate_json_schema.py --schema schemas\validation_report.schema.json --json evals\.tmp\price-compare\eval-product-quotes\validation\price-validation-report.json`
- `python C:\Users\62406\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py "E:\Inward Eyes"`

## Closeout

- M0-M2 closeout: `docs/planning/archive/m0-m2-closeout.md`
- M3 closeout: `docs/planning/archive/m3-browser-research-mvp-closeout.md`
- M4-M5 closeout: `docs/planning/archive/m4-m5-price-pluginization-mvp-closeout.md`

## Notes for Implementation Agents

- M0-M5 MVP is closed.
- Current release class is local deterministic MVP, not live browser operation.
- Codex is the agent; Inward Eyes provides skills, schemas, scripts, evidence rules, and tool routing.
- Runtime evidence belongs in the user's workspace output directory, not inside the plugin package.
