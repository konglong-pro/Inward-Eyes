# Architecture

## Purpose

Inward Eyes gives Codex evidence-backed browser workflows. It is not a standalone agent and not a high-throughput crawler. It is a plugin-shaped capability kit: skills decide the workflow, browser tools observe and interact, scripts normalize and validate outputs, and evidence records make results auditable.

## System Layers

```text
Codex
  -> Inward Eyes plugin
      -> focused skills
      -> shared contracts and references
      -> deterministic scripts
      -> schemas and validators
      -> optional browser MCP tooling
  -> browser tools
      -> Chrome extension for logged-in pages
      -> Playwright or Chrome DevTools for structured public page extraction
      -> Browser Use for local/public page review when appropriate
      -> Computer Use as GUI fallback
  -> runtime output directory
      -> manifest, artifacts, evidence, validation reports
```

## Planned Plugin Contents

```text
.codex-plugin/
  plugin.json
skills/
  page-to-md/
  browser-research/
  price-compare/
schemas/
scripts/
  capture/
  markdown/
  validation/
  reports/
  evals/
references/
evals/
docs/
```

Current implementation covers local HTML and page-capture JSON conversion for
`page-to-md`, browser adapter boundary captures for approved public/current
pages, provided-URL browser-research capture, provided product-URL price
capture, and M10 bounded discovery wrappers for research sources and price
candidates.

The implementation remains small-scope and evidence-first. It is not a broad
crawler, marketplace monitor, automated purchasing flow, unrestricted logged-in
browser operator, or marketplace-distributed package.

## Runtime Output Model

Runtime outputs are not plugin source files. A future run should create a directory like:

```text
browser-operator-runs/<run_id>/
  input.json
  manifest.json
  artifacts/
  evidence/
  validation/
```

The output root must be configurable by task or workspace.

## Shared Data Flow

1. Receive a scoped task and allowed input.
2. Classify task type and page/source type.
3. Route to the least-privileged suitable browser tool.
4. Capture `page_capture.json`, source record, and evidence.
5. Extract structured data.
6. Normalize data into schema-shaped JSON.
7. Validate schema and consistency.
8. Render human artifacts such as Markdown, CSV, charts, or reports.
9. Write manifest and warnings.
10. Report artifacts, checks, skipped checks, and risks.

## Skill Boundaries

`page-to-md` handles one page or one thread. It must not perform multi-source research or price comparison.

`browser-research` handles multi-source research. Its core artifact is a claim ledger, not just a prose summary.

`price-compare` handles product quote extraction and comparison. Its core problem is product/spec identity, not just price capture.

M10 discovery wrappers may propose scoped public research sources or approved ecommerce candidates, but the downstream research and price runners remain the source of truth for claims, quotes, source records, screenshots, and validation.

## Tool Routing Summary

Structured extraction is preferred. GUI control is fallback.

- Logged-in pages: Chrome extension or current Chrome context, with user approval.
- Public articles/docs: Playwright or Chrome DevTools structured extraction.
- SPA/infinite scroll: Playwright or Chrome DevTools with explicit scrolling and screenshots.
- X-like threads and forums: logged-in Chrome when required, plus screenshot evidence.
- Ecommerce: logged-in Chrome when account/region affects price; structured snapshots and screenshots required.
- Local development pages: Codex in-app browser or Playwright.
- Legacy GUI: Computer Use only when structured tools cannot work.

See `docs/contracts/browser-operation-contract.md`.

## Security Model

Inward Eyes is read-only by default. It must classify actions into Green, Yellow, and Red before interacting with browser pages. Red actions are prohibited unless future project policy explicitly changes, and first versions should not support them.

See `docs/contracts/safety-contract.md`.

## Evidence Model

All final fields must tie back to source evidence. Minimum evidence is:

- URL.
- Page title.
- Access time.
- Capture method.
- SourceRecord.
- Screenshot policy and screenshot evidence when login-state, dynamic, thread, forum, ecommerce, or ambiguity is involved.
- Validation report.

See `docs/contracts/evidence-contract.md`.
