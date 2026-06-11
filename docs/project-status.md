# Project Status

Last updated: 2026-06-11

## Summary

Inward Eyes v0.2 is complete: deterministic local evidence workflows are complete.

Current active work: none.

Current release class: v0.3 adapter-boundary MVP on top of the frozen local deterministic baseline.

M0-M5 MVP has local deterministic workflows for:

- `page-to-md`: local HTML and page capture JSON to evidence-backed Markdown.
- `browser-research`: local research input JSON to claim ledger, source records, report, source notes, and claim coverage validation.
- `price-compare`: local price input JSON to price records, CSV, report, anomalies, chart, source records, screenshot-policy validation, and price validation report.

The local Codex plugin is packaged as version `0.2.0` with all three skills and a GitHub Actions CI workflow for repository-contained checks.

Version semantics:

- `0.1.x`: `page-to-md` local deterministic workflow.
- `0.2.x`: three local workflows plus local plugin validation and CI.
- `0.3.x`: optional Playwright MCP browser capture adapter MVP for `page-to-md` public article/docs pages. Completed in M6.
- `0.4.x`: optional MCP configuration packaging or broader page-type capture, disabled by default unless explicitly approved.
- `0.5.x`: `browser-research` discovery/capture MVP.
- `0.6.x`: `price-compare` real ecommerce URL capture MVP.
- `1.0.0`: stable browser-backed plugin, still read-only.

## Frozen Behavior

- `page-to-md` supports local HTML and `page_capture.json`.
- `browser-research` supports local research input JSON.
- `price-compare` supports local price input JSON.
- M6 browser capture adapter boundary is implemented for `page-to-md`; live browser execution remains optional and environment-dependent.
- Runtime output stays outside the plugin package.
- `source_record.json` is canonical evidence.
- `page_capture.json` is the browser adapter boundary.
- Red browser actions are prohibited by default.

## Active Work

None.

M6 Browser Capture Adapter MVP is complete. It uses Playwright MCP as the only adapter backend boundary and targets one `page-to-md` workflow for one public article/docs URL. The adapter writes `capture/page_capture.json`; the existing local runner consumes that JSON without browser-specific logic and stages screenshot assets into `evidence/screenshots/` when policy requires them.

M6 is not a pluginization expansion. It did not add hooks, enable MCP by default, implement research discovery, or implement ecommerce/price capture.

Closeouts:

- M0-M2: `docs/planning/archive/m0-m2-closeout.md`
- M3: `docs/planning/archive/m3-browser-research-mvp-closeout.md`
- M4-M5: `docs/planning/archive/m4-m5-price-pluginization-mvp-closeout.md`
- M6: `docs/planning/archive/m6-browser-capture-adapter-mvp-closeout.md`

## Next Work

Later work remains planned but not active:

- Real browser/MCP capture for `browser-research` and `price-compare`.
- Broad product discovery.
- Site-specific ecommerce extraction profiles.
- Marketplace installation and plugin distribution workflow.
- Optional bundled MCP configuration, disabled by default.
- Plugin hooks only if a future phase proves they are necessary.

Canonical latest closeout: `docs/planning/archive/m6-browser-capture-adapter-mvp-closeout.md`.

## Known Unknowns

- Whether the first stable release should keep Python-only scripts or add a package manifest.
- Exact Codex plugin distribution workflow and marketplace setup.
- Whether optional MCP tools beyond the M6 Playwright MCP setup will be bundled, documented, or left as user-installed dependencies.
- Evaluation fixture licensing and storage policy.
- Real browser capture accuracy beyond public article/docs pages.
- Remote CI status for the first GitHub PR.

## Evidence Archive

Synthetic eval outputs are generated under `evals/.tmp/` and ignored by default.
