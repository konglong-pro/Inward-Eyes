# Project Status

Last updated: 2026-06-09

## Summary

Inward Eyes v0.2 is complete: deterministic local evidence workflows are complete; the real browser adapter layer is not implemented.

Current release class: local deterministic MVP.

M0-M5 MVP has local deterministic workflows for:

- `page-to-md`: local HTML and page capture JSON to evidence-backed Markdown.
- `browser-research`: local research input JSON to claim ledger, source records, report, source notes, and claim coverage validation.
- `price-compare`: local price input JSON to price records, CSV, report, anomalies, chart, source records, screenshot-policy validation, and price validation report.

The local Codex plugin is packaged as version `0.2.0` with all three skills and a GitHub Actions CI workflow for repository-contained checks.

Version semantics:

- `0.1.x`: `page-to-md` local deterministic workflow.
- `0.2.x`: three local workflows plus local plugin validation and CI.
- `0.3.x`: browser capture adapter contract implemented for one backend.
- `0.4.x`: real `page-to-md` browser adapter MVP.
- `0.5.x`: `browser-research` discovery/capture MVP.
- `0.6.x`: `price-compare` real ecommerce URL capture MVP.
- `1.0.0`: stable browser-backed plugin, still read-only.

## Frozen Behavior

- `page-to-md` supports local HTML and `page_capture.json`.
- `browser-research` supports local research input JSON.
- `price-compare` supports local price input JSON.
- Browser/MCP capture is not implemented yet.
- Runtime output stays outside the plugin package.
- `source_record.json` is canonical evidence.
- `page_capture.json` is the browser adapter boundary.
- Red browser actions are prohibited by default.

## Active Work

None.

Closeouts:

- M0-M2: `docs/planning/archive/m0-m2-closeout.md`
- M3: `docs/planning/archive/m3-browser-research-mvp-closeout.md`
- M4-M5: `docs/planning/archive/m4-m5-price-pluginization-mvp-closeout.md`

## Next Work

Later work remains planned but not active:

- Real browser/MCP capture for `browser-research` and `price-compare`.
- M6 browser capture adapter MVP: `docs/planning/next/m6-browser-capture-adapter-mvp.md`.
- Broad product discovery.
- Site-specific ecommerce extraction profiles.
- Marketplace installation and plugin distribution workflow.

Canonical next plan: `docs/planning/next/m3-m5-research-price-pluginization.md`.

## Known Unknowns

- Whether the first stable release should keep Python-only scripts or add a package manifest.
- Exact Codex plugin distribution workflow and marketplace setup.
- Whether optional MCP tools will be bundled, documented, or left as user-installed dependencies.
- Evaluation fixture licensing and storage policy.
- Real browser capture accuracy on logged-in pages.
- Remote CI status for the first GitHub PR.

## Evidence Archive

Synthetic eval outputs are generated under `evals/.tmp/` and ignored by default.
