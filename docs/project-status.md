# Project Status

Last updated: 2026-06-09

## Summary

M0-M2 is complete. Inward Eyes has a closed `page-to-md` MVP baseline: plugin manifest, skill instructions, schema files, Python standard-library runner, Markdown renderer, validation scripts, manifest/evidence path checks, screenshot policy, source records, safety classifier, and synthetic eval fixtures.

## Frozen Behavior

- `page-to-md` supports local HTML and `page_capture.json`.
- Browser/MCP capture is outside M2.
- Runtime output stays outside the plugin package.
- `source_record.json` is canonical evidence.
- `page_capture.json` is the browser adapter boundary.
- Red browser actions are prohibited by default.

## Active Work

None.

M0-M2 closeout: `docs/planning/archive/m0-m2-closeout.md`.

## Next Work

M3-M5 is planned but not active:

- `browser-research` with claim ledger.
- `price-compare` with strict product identity and quote extraction.
- Plugin packaging and optional MCP dependencies.

Canonical next plan: `docs/planning/next/m3-m5-research-price-pluginization.md`.

## Known Unknowns

- Whether the first stable release should keep Python-only scripts or add a package manifest.
- Exact Codex plugin distribution workflow and marketplace setup.
- Whether optional MCP tools will be bundled, documented, or left as user-installed dependencies.
- Evaluation fixture licensing and storage policy.
- Real browser capture accuracy on logged-in pages.
- Remote git origin URL for this workspace.

## Evidence Archive

Synthetic eval outputs are generated under `evals/.tmp/` and ignored by default.
