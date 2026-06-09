# Current Active Work

Last updated: 2026-06-09
Source of current phase: `docs/phase-manifest.yaml`

## Current State

- Shipped/frozen: M0-M2 foundation and `page-to-md` MVP baseline.
- Active: none.
- Completed: plugin manifest, `page-to-md` skill, shared schemas, local HTML/page-capture runner, Markdown renderer, validator, safety classifier, synthetic evals, and M2 closeout.
- Next but not approved: `browser-research`, `price-compare`, plugin marketplace distribution, and optional MCP/browser adapters.

## Active Objective

No implementation phase is currently active. M3-M5 remains planned but not approved.

## Required Reading for Current Work

- `AGENTS.md`
- `docs/project-status.md`
- `docs/planning/archive/m0-m2-closeout.md`
- `docs/planning/next/m3-m5-research-price-pluginization.md`
- `docs/contracts/evidence-contract.md`
- `docs/contracts/capture-adapter-contract.md`
- `docs/contracts/browser-operation-contract.md`
- `docs/contracts/schemas-and-validation-contract.md`
- `docs/contracts/safety-contract.md`

## Explicitly Out of Scope

- Installing browser automation dependencies without explicit approval.
- Creating runnable MCP servers without explicit approval.
- Capturing real user browser pages without explicit approval.
- Large-scale crawling.
- Automated purchases, posting, account mutation, CAPTCHA handling, stealth browsing, proxies, or anti-bot bypass.

## Current Gates

- `python -m py_compile scripts\page_to_md_runner.py scripts\markdown\render_page_md.py scripts\validation\validate_page_to_md.py scripts\validation\validate_json_schema.py scripts\validation\classify_browser_action.py scripts\inward_eyes\__init__.py scripts\inward_eyes\html_extract.py scripts\inward_eyes\io.py scripts\inward_eyes\markdown.py scripts\inward_eyes\safety.py scripts\inward_eyes\validation.py evals\run_eval.py evals\run_safety_eval.py`
- `python evals\run_eval.py`
- `python evals\run_safety_eval.py`
- `python scripts\validation\validate_json_schema.py --schema schemas\page_to_md_metadata.schema.json --json evals\.tmp\page-to-md\eval-public-article\artifacts\metadata.json`
- `python scripts\validation\validate_json_schema.py --schema schemas\run_manifest.schema.json --json evals\.tmp\page-to-md\eval-public-article\manifest.json`
- `python C:\Users\62406\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py "E:\Inward Eyes"`

## Closeout

- M0-M2 closeout: `docs/planning/archive/m0-m2-closeout.md`
- Archived phase plan: `docs/planning/archive/m0-m2-foundation-and-page-to-md.md`

## Notes for Implementation Agents

- Do not start M3-M5 unless the user explicitly approves it.
- Codex is the agent; Inward Eyes provides skills, schemas, scripts, evidence rules, and tool routing.
- Runtime evidence belongs in the user's workspace output directory, not inside the plugin package.
