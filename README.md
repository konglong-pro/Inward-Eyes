# Inward Eyes

Inward Eyes is a Codex plugin MVP for local deterministic evidence workflows. It processes local HTML, page capture JSON, research input JSON, price input JSON, and bounded discovery specs into validated, evidence-backed artifacts.

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

Current release class: repository-contained small-scope discovery MVP.

The current repository includes deterministic local runners plus adapter-boundary wrappers for approved browser captures and bounded discovery. Runtime browser operation remains tightly scoped and evidence-backed; marketplace distribution is not implemented.

Version semantics:

- `0.1.x`: `page-to-md` local deterministic workflow.
- `0.2.x`: three local workflows plus local plugin validation and CI.
- `0.3.x`: optional Playwright MCP browser capture adapter MVP for public article/docs pages.
- `0.4.x`: current Chrome / logged-in page capture MVP for one approved visible page.
- `0.5.x`: `browser-research` provided-URL capture MVP.
- `0.6.x`: `price-compare` provided product-URL quote capture MVP.
- `0.7.x`: `browser-research` small-scope public source discovery MVP.
- `0.8.x`: M10 small-scope discovery consolidation, including approved price candidate discovery.
- `1.0.0`: stable browser-backed plugin, still read-only.

## Current State

M0-M10 small-scope evidence workflows are complete:

- `page-to-md`: local HTML, page capture JSON, public URL adapter captures, and one user-approved current Chrome page capture to evidence-backed Markdown.
- `browser-research`: local research input JSON, provided-URL capture, claim ledger validation, source records, reports, source notes, and M10A small-scope public source discovery.
- `price-compare`: local price input JSON, provided product-URL quote capture, strict product/spec matching, anomalies, CSV/Markdown/chart rendering, screenshot-policy validation, and M10B approved candidate discovery.

Still not implemented:

- broad crawling or crawler replacement behavior
- marketplace-wide product crawling or monitoring
- automated purchasing, coupon claiming, cart, checkout, or address/account mutation
- unrestricted logged-in browsing
- stealth, proxy, CAPTCHA, or anti-bot bypass workflows
- marketplace distribution package

Closeouts:

- `docs/planning/archive/m0-m2-closeout.md`
- `docs/planning/archive/m3-browser-research-mvp-closeout.md`
- `docs/planning/archive/m4-m5-price-pluginization-mvp-closeout.md`
- `docs/planning/archive/m6-browser-capture-adapter-mvp-closeout.md`
- `docs/planning/archive/m7-current-chrome-capture-mvp-closeout.md`
- `docs/planning/archive/m8-research-provided-url-capture-mvp-closeout.md`
- `docs/planning/archive/m9-price-product-url-capture-mvp-closeout.md`
- `docs/planning/archive/m10-small-scope-discovery-closeout.md`

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
- Run research discovery evals: `python evals/run_research_discovery_eval.py`
- Run price evals: `python evals/run_price_eval.py`
- Run price candidate discovery evals: `python evals/run_price_candidate_discovery_eval.py`
- Validate one page-to-md run: `python scripts/validation/validate_page_to_md.py <run_dir>`
- Validate one browser-research run: `python scripts/validation/validate_browser_research.py <run_dir>`
- Validate one research discovery run: `python scripts/validation/validate_research_discovery.py <run_dir>`
- Validate one price candidate discovery run: `python scripts/validation/validate_price_candidate_discovery.py <run_dir>`
- Validate one price-compare run: `python scripts/validation/validate_price_compare.py <run_dir>`
- Validate JSON against schema: `python scripts/validation/validate_json_schema.py --schema <schema-path> --json <json-path>`
- Validate plugin: `python C:\Users\62406\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py "E:\Inward Eyes"`
- Build/package plugin: not implemented yet.

## Safety Baseline

Inward Eyes is read-only by default. It must not buy, pay, post, comment, like, follow, send messages, claim coupons, add to cart, change account settings, process passwords, submit CAPTCHA, bypass anti-bot systems, or export unrelated personal data.
