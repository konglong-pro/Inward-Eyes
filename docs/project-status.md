# Project Status

Last updated: 2026-06-16

## Summary

Inward Eyes is complete through M20 as a repository-contained Codex plugin for deterministic evidence workflows and local operational tooling.

Current active implementation phase: none.

Current release class: post-M12-M20 local operations hardening. The repository includes browser-backed workflow boundaries, v1 contract hardening, adapter matrix reporting, deterministic replay evals, privacy scans, advisory site profiles, CLI review, local package dry-run, sequential batch/retry/indexing, and view-only exporters.

The local Codex plugin package version remains `0.2.0`. Repository phase/version semantics document the implementation baseline; marketplace publication and release tagging are separate work.

## Frozen Behavior

- `page-to-md` supports local HTML and `page_capture.json`.
- M6 browser capture adapter boundary supports one public article/docs URL for `page-to-md`.
- M7 current Chrome adapter boundary supports one explicitly user-approved currently visible page for `page-to-md`.
- M8 provided-URL research capture uses approved source URLs only and leaves claim rendering/validation to `browser_research_runner.py`.
- M9 product-URL price capture uses approved ecommerce product URLs only and leaves quote rendering/validation to `price_compare_runner.py`.
- M10A discovery is bounded by user-approved research question, max source count, allowed/excluded domains or source types, recency when relevant, and search queries.
- M10B candidate discovery is bounded by user-approved product target, required specs, approved platforms/domains, candidate caps, region, currency, excluded sellers, and approval policy.
- Current-browser capture may record login/privacy/screenshot policy, but it must not save browser session data.
- Screenshot-required pages must have screenshot evidence staged into `evidence/screenshots/`; manifest screenshot evidence entries include `sha256`.
- Private-data warnings force manual review.
- Red browser actions are prohibited and produce `run_status=aborted_by_policy`.
- Runtime output stays outside the plugin package.
- `source_record.json` is canonical evidence.
- `page_capture.json` is the browser adapter boundary.
- Site profiles are advisory extraction hints and never grant browser permission.
- Review, run index, package, batch, retry, and export outputs are derived local operational views.

## Completed Phase Timeline

- M0-M2: foundation and page-to-md.
- M3: browser-research MVP.
- M4-M5: price-compare and local pluginization MVP.
- M6: browser capture adapter MVP.
- M7: current Chrome capture MVP.
- M8: browser-research provided-URL capture MVP.
- M9: price product-URL capture MVP.
- M10: small-scope discovery consolidation.
- M11: v1.0 hardening and release-candidate contracts.
- M12: adapter matrix.
- M13: real-world-style deterministic replay evals.
- M14: privacy/security hardening.
- M15: advisory site profiles.
- M16: CLI/text review UI.
- M17: local distribution package dry-run.
- M18-M19: batch, retry planning, and rebuildable run index.
- M20: view-only exporters and extension boundary.

Latest closeout: `docs/planning/archive/m12-m20-post-rc-expansion-closeout.md`.

Closeouts:

- M0-M2: `docs/planning/archive/m0-m2-closeout.md`
- M3: `docs/planning/archive/m3-browser-research-mvp-closeout.md`
- M4-M5: `docs/planning/archive/m4-m5-price-pluginization-mvp-closeout.md`
- M6: `docs/planning/archive/m6-browser-capture-adapter-mvp-closeout.md`
- M7: `docs/planning/archive/m7-current-chrome-capture-mvp-closeout.md`
- M8: `docs/planning/archive/m8-research-provided-url-capture-mvp-closeout.md`
- M9: `docs/planning/archive/m9-price-product-url-capture-mvp-closeout.md`
- M10: `docs/planning/archive/m10-small-scope-discovery-closeout.md`
- M11: `docs/planning/archive/m11-v1-release-risk-report.md`
- M12-M20: `docs/planning/archive/m12-m20-post-rc-expansion-closeout.md`

## Still Out of Scope

- Broad crawling or crawler replacement behavior.
- Marketplace-wide product crawling or monitoring.
- Automated purchasing, coupon claiming, cart, checkout, address/account mutation, posting, messaging, or following.
- Unrestricted logged-in browsing.
- Stealth, proxy, CAPTCHA, or anti-bot bypass workflows.
- Marketplace publication.
- Dynamic third-party extension loading.
- Parallel batch execution or service/SQLite run database.
- XLSX/PDF exporters unless a future dependency decision approves them.

## Known Unknowns

- Exact marketplace publication workflow, metadata, screenshots, and release ownership.
- Whether the plugin package version should be bumped before a tagged release.
- Live browser/network quality beyond deterministic replay and synthetic evals.
- Live ecommerce platform behavior beyond deterministic fixtures.
- Whether optional MCP tools beyond the M6 Playwright MCP setup will be bundled, documented, or left as user-installed dependencies.
- Remote CI status for the first GitHub PR.

## Evidence Archive

Synthetic eval outputs are generated under `evals/.tmp/` and ignored by default.
