# Project Status

Last updated: 2026-06-16

## Summary

Inward Eyes v0.6 is complete as a price-compare product-URL browser quote capture MVP.

Current active work: none.

Current release class: v0.6 provided-product-URL quote capture MVP on top of the frozen local deterministic, public-URL adapter, current-browser safety, and provided-source research baselines.

M0-M9 MVP has:

- `page-to-md`: local HTML, page capture JSON, public URL adapter captures, and one user-approved current Chrome page capture to evidence-backed Markdown.
- `browser-research`: local research input JSON to claim ledger, source records, report, source notes, and claim coverage validation; M8 adds provided-URL capture in front of that local runner.
- `price-compare`: local price input JSON to price records, CSV, report, anomalies, chart, source records, screenshot-policy validation, and price validation report; M9 adds provided product URL capture in front of that local runner.

The local Codex plugin remains package version `0.2.0`; M6-M9 are repository-contained adapter-boundary implementation slices, not marketplace distribution releases.

Version semantics:

- `0.1.x`: `page-to-md` local deterministic workflow.
- `0.2.x`: three local workflows plus local plugin validation and CI.
- `0.3.x`: optional Playwright MCP browser capture adapter MVP for `page-to-md` public article/docs pages. Completed in M6.
- `0.4.x`: current Chrome / logged-in page capture MVP for one approved visible page. Completed in M7.
- `0.5.x`: `browser-research` provided-URL capture MVP. Completed in M8.
- `0.6.x`: `price-compare` product-URL browser quote capture MVP. Completed in M9.
- `1.0.0`: stable browser-backed plugin, still read-only.

## Frozen Behavior

- `page-to-md` supports local HTML and `page_capture.json`.
- M6 browser capture adapter boundary supports one public article/docs URL for `page-to-md`.
- M7 current Chrome adapter boundary supports one explicitly user-approved currently visible page for `page-to-md`.
- M8 provided-URL research capture uses approved source URLs only and leaves claim rendering/validation to `browser_research_runner.py`.
- M9 product-URL price capture uses approved ecommerce product URLs only and leaves quote rendering/validation to `price_compare_runner.py`.
- Current-browser capture may record `login_state=confirmed|suspected|not_required|unknown`, privacy flags, capture warnings, and screenshot policy, but it must not save browser session data.
- Screenshot-required pages must have screenshot evidence staged into `evidence/screenshots/`; manifest screenshot evidence entries include `sha256`.
- Private-data warnings force manual review.
- Red browser actions are prohibited and produce `run_status=aborted_by_policy`.
- Runtime output stays outside the plugin package.
- `source_record.json` is canonical evidence.
- `page_capture.json` is the browser adapter boundary.

## Active Work

None.

M9 price-compare product-URL capture is complete. It adds `scripts/price_capture_runner.py` to capture each approved product URL, write per-source `page_capture.json`, generate `capture/price-input.json`, and then run the existing local `price_compare_runner.py`.

M9 is not broad product discovery. It does not search, discover products, follow recommendation links, claim coupons, add to cart, proceed to checkout, change addresses, compare search terms, or add plugin hooks.

Closeouts:

- M0-M2: `docs/planning/archive/m0-m2-closeout.md`
- M3: `docs/planning/archive/m3-browser-research-mvp-closeout.md`
- M4-M5: `docs/planning/archive/m4-m5-price-pluginization-mvp-closeout.md`
- M6: `docs/planning/archive/m6-browser-capture-adapter-mvp-closeout.md`
- M7: `docs/planning/archive/m7-current-chrome-capture-mvp-closeout.md`
- M8: `docs/planning/archive/m8-research-provided-url-capture-mvp-closeout.md`
- M9: `docs/planning/archive/m9-price-product-url-capture-mvp-closeout.md`

## Next Work

Later work remains planned but not active:

- Automatic source discovery/search for browser research. Deferred to M10.
- Broad product discovery for price comparison. Deferred to M10 or later.
- Full X/forum thread capture and infinite-scroll handling.
- Search-term price comparison.
- Automatic cross-platform same-product discovery.
- Site-specific ecommerce extraction profiles.
- Marketplace installation and plugin distribution workflow.
- Optional bundled MCP configuration, disabled by default.
- Plugin hooks only if a future phase proves they are necessary.

Canonical latest closeout: `docs/planning/archive/m9-price-product-url-capture-mvp-closeout.md`.

## Known Unknowns

- Whether the first stable release should keep Python-only scripts or add a package manifest.
- Exact Codex plugin distribution workflow and marketplace setup.
- Whether optional MCP tools beyond the M6 Playwright MCP setup will be bundled, documented, or left as user-installed dependencies.
- Evaluation fixture licensing and storage policy.
- Real browser research and price capture accuracy beyond synthetic observations and manual local smoke.
- Remote CI status for the first GitHub PR.

## Evidence Archive

Synthetic eval outputs are generated under `evals/.tmp/` and ignored by default.
