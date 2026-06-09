# M0-M2 Closeout

## What Shipped

- Codex plugin manifest for `inward-eyes`.
- `page-to-md` skill with focused trigger boundaries and read-only safety rules.
- Local HTML and `page_capture.json` runner.
- Evidence-backed run directories with `manifest.json`, `source_record.json`, metadata, Document AST, Markdown, warnings, and validation report.
- Screenshot policy model with explicit status.
- Shared schemas for M2 outputs.
- Placeholder schemas for M3/M4 research and price comparison.
- Deterministic Markdown renderer.
- Page-to-md validation script.
- Minimal JSON schema validator.
- Safety action classifier and safety evals.
- Synthetic M2 fixture set.
- Capture adapter contract for future browser/MCP integration.

## Frozen Behavior

- Browser tools are not default dependencies.
- Runtime outputs are written outside the plugin package.
- `source_record.json` is the canonical source evidence object.
- `page_capture.json` is the adapter boundary for browser observations.
- `document_ast.json` is rendered to Markdown; Markdown is not the source of truth.
- Missing author/publish time must remain explicit warnings.
- Screenshot absence is valid only when `screenshot_policy.status` allows it.
- Red browser actions remain prohibited by default.

## Tests / Gates

Passed in this closeout:

- Python compile check.
- `python evals\run_eval.py`
- `python evals\run_safety_eval.py`
- Schema checks for page capture, manifest, metadata, Document AST, source record, and validation report samples.
- Official Codex plugin validator.
- Markdown local link check.

## Evidence Retained

- Synthetic fixtures under `evals/fixtures/page-to-md/`.
- Safety action fixtures under `evals/fixtures/safety-actions/`.
- Eval outputs are generated under `evals/.tmp/` and ignored by default.

## Known Limitations

- No real browser, Chrome extension, Playwright, Chrome DevTools, Browser Use, or Computer Use adapter is implemented.
- Screenshot files are not captured or copied by the runner yet.
- Local HTML extraction uses a small Python standard-library parser, not a production-grade readability engine.
- JSON schema validation is minimal and not a full JSON Schema implementation.
- Research and price comparison schemas are placeholders only.
- The project is not yet connected to a remote git origin in this workspace.

## Superseded Docs or Rules

- The active M0-M2 phase plan is archived at `docs/planning/archive/m0-m2-foundation-and-page-to-md.md`.
