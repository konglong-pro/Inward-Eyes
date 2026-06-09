# Inward Eyes

Inward Eyes is a planned Codex plugin for evidence-backed browser workflows. It will help Codex convert browser pages to Markdown, conduct source-backed browser research, and compare ecommerce prices while preserving source records, screenshots, metadata, validation reports, and run manifests.

The project is not a crawler replacement. It targets small-scale, high-complexity, login-state or interaction-heavy browser tasks where accuracy, reviewability, and evidence matter more than throughput.

## Product Positioning

**Evidence-backed browser workflows for Codex.**

Inward Eyes uses:

- Codex skills for workflow decisions.
- Browser/MCP tools for observation and interaction.
- Local deterministic scripts for cleanup, validation, rendering, charts, and exports.
- Evidence manifests so outputs can be audited.

## Planned Capabilities

- `page-to-md`: convert one browser page, article, X-like thread, forum thread, docs page, or logged-in visible page into Markdown with metadata and evidence.
- `browser-research`: produce a report from multiple sources using a claim ledger, source records, and explicit unknowns.
- `price-compare`: compare product prices with strict product/spec matching, region, seller, coupon, shipping, stock, timestamp, URL, and screenshot evidence.

## Current State

M0-M2 is complete. The `page-to-md` baseline exists for local HTML and
page-capture JSON:

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

Browser/MCP capture is not implemented yet. Real logged-in browser capture,
X-like thread capture, forum capture, and ecommerce browser capture remain
future hardening work.

Closeout: `docs/planning/archive/m0-m2-closeout.md`.

Read:

- `docs/active/current.md` for current scope.
- `docs/planning/archive/m0-m2-closeout.md` for the completed M0-M2 closeout.
- `docs/architecture.md` for system design.
- `docs/testing.md` for testing and eval strategy.

## Planned Repository Shape

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
- Validate one page-to-md run: `python scripts/validation/validate_page_to_md.py <run_dir>`
- Validate JSON against schema: `python scripts/validation/validate_json_schema.py --schema <schema-path> --json <json-path>`
- Validate plugin: `python C:\Users\62406\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py "E:\Inward Eyes"`
- Build/package plugin: not implemented yet.

## Safety Baseline

Inward Eyes is read-only by default. It must not buy, pay, post, comment, like, follow, send messages, claim coupons, add to cart, change account settings, process passwords, submit CAPTCHA, bypass anti-bot systems, or export unrelated personal data.
