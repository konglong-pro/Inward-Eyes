# Inward Eyes

Inward Eyes is a Codex plugin MVP for local deterministic evidence workflows. It processes local HTML, page capture JSON, research input JSON, and price input JSON into validated, evidence-backed artifacts.

The project is not a crawler replacement. It targets small-scale, high-complexity, login-state or interaction-heavy browser tasks where accuracy, reviewability, and evidence matter more than throughput.

## Product Positioning

**Evidence-backed browser workflows for Codex.**

Inward Eyes uses:

- Codex skills for workflow decisions.
- Browser/MCP tools for observation and interaction.
- Local deterministic scripts for cleanup, validation, rendering, charts, and exports.
- Evidence manifests so outputs can be audited.

## Implemented Local Workflows

- `page-to-md`: convert one browser page, article, X-like thread, forum thread, docs page, or logged-in visible page into Markdown with metadata and evidence.
- `browser-research`: produce a report from multiple sources using a claim ledger, source records, and explicit unknowns.
- `price-compare`: compare product prices with strict product/spec matching, region, seller, coupon, shipping, stock, timestamp, URL, and screenshot evidence.

## Current Release

Current release class: local deterministic MVP.

The current plugin can process local input JSON/HTML and render validated, evidence-backed artifacts. It does not yet operate a live browser.

Version semantics:

- `0.1.x`: `page-to-md` local deterministic workflow.
- `0.2.x`: three local workflows plus local plugin validation and CI.
- `0.3.x`: browser capture adapter contract implemented for one backend.
- `0.4.x`: real `page-to-md` browser adapter MVP.
- `0.5.x`: `browser-research` discovery/capture MVP.
- `0.6.x`: `price-compare` real ecommerce URL capture MVP.
- `1.0.0`: stable browser-backed plugin, still read-only.

## Current State

M0-M2 `page-to-md` local workflow is complete:

- plugin manifest
- `page-to-md` skill
- schema-shaped metadata and Document AST
- Python standard-library runner
- deterministic Markdown renderer
- validation scripts
- manifest/evidence path checks
- screenshot policy
- safety classifier
- synthetic eval fixtures

M3 `browser-research` MVP is complete. The first slice supports local research
input JSON, claim ledger validation, source records, rendered reports, sources
CSV, source notes, and synthetic pass/fail eval fixtures.

M4-M5 `price-compare` and pluginization MVP is complete. The first price slice
supports local price input JSON, separated product specs and price components,
anomalies, CSV/Markdown/chart rendering, screenshot-policy validation, and a
validated local plugin containing all three skills.

Not implemented:

- real browser capture adapters
- Codex Chrome extension integration
- Playwright MCP adapter
- Chrome DevTools MCP adapter
- Browser Use adapter
- Computer Use fallback
- broad web/product discovery
- marketplace distribution package

Closeouts:

- `docs/planning/archive/m0-m2-closeout.md`
- `docs/planning/archive/m3-browser-research-mvp-closeout.md`
- `docs/planning/archive/m4-m5-price-pluginization-mvp-closeout.md`

Read:

- `docs/active/current.md` for current scope.
- `docs/planning/archive/m0-m2-closeout.md` for the completed M0-M2 closeout.
- `docs/architecture.md` for system design.
- `docs/testing.md` for testing and eval strategy.
- `docs/pluginization.md` for current local plugin packaging boundaries.
- `.github/workflows/ci.yml` for repository-contained CI checks.

## Repository Shape

```text
Inward Eyes/
  .codex-plugin/
  skills/
  schemas/
  scripts/
  evals/
  docs/
  AGENTS.md
  CONTEXT.md
  README.md
```

Runtime outputs should be written to a user-selected workspace directory such as `browser-operator-runs/`, not inside the installed plugin package.

## Commands

Run from the repository root.

- Install: no install step yet; first implementation uses Python standard library only.
- Compile check: see `docs/testing.md`.
- Run evals: `python evals/run_eval.py`
- Run research evals: `python evals/run_research_eval.py`
- Run price evals: `python evals/run_price_eval.py`
- Validate one page-to-md run: `python scripts/validation/validate_page_to_md.py <run_dir>`
- Validate one browser-research run: `python scripts/validation/validate_browser_research.py <run_dir>`
- Validate one price-compare run: `python scripts/validation/validate_price_compare.py <run_dir>`
- Validate JSON against schema: `python scripts/validation/validate_json_schema.py --schema <schema-path> --json <json-path>`
- Validate plugin: `python C:\Users\62406\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py "E:\Inward Eyes"`
- Build/package plugin: not implemented yet.

## Safety Baseline

Inward Eyes is read-only by default. It must not buy, pay, post, comment, like, follow, send messages, claim coupons, add to cart, change account settings, process passwords, submit CAPTCHA, bypass anti-bot systems, or export unrelated personal data.
