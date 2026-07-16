---
doc_type: phase_plan
phase_id: m6_browser_capture_adapter_mvp
title: Browser capture adapter MVP
status: completed
canonical: true
read_by_default: false
closeout: docs/planning/archive/m6-browser-capture-adapter-mvp-closeout.md
related_contracts:
  - docs/contracts/capture-adapter-contract.md
  - docs/contracts/browser-operation-contract.md
  - docs/contracts/evidence-contract.md
  - docs/contracts/safety-contract.md
---

# M6 Browser Capture Adapter MVP

## Goal

Implement the smallest real browser capture adapter that produces `page_capture.json` compatible with the existing local `page-to-md` workflow.

M6 proves the adapter boundary. It does not expand `browser-research`, `price-compare`, reports, charts, or schemas.

## Scope

Start with exactly one backend, one workflow, and one page class:

- Backend: Playwright MCP.
- Workflow: `page-to-md`.
- Input: one user-provided public URL.
- Page class: static public article or docs page.
- Browser state: fresh, non-profile context only.
- Browser actions: navigate, wait, read DOM/accessibility/text, and screenshot only when policy requires it.
- Output boundary: `<run_dir>/capture/page_capture.json`.
- Rendering boundary: existing `scripts\page_to_md_runner.py` consumes the capture JSON without browser logic.
- Wrapper boundary: `scripts\capture\page_to_md_browser_runner.py` runs capture, capture validation, deterministic rendering, and run validation for one run directory.

The adapter must be optional, minimal-permission, and read-only by default. M6 must not add hooks, enable browser MCP by default, or require a bundled browser backend. Local Python Playwright capture is optional: if it is unavailable, the adapter writes an auditable failed run instead of installing dependencies or faking success.

## Required Outputs

```text
<run_dir>/
  input.json
  capture/
    page_capture.json
  manifest.json
  artifacts/
    page.md
    metadata.json
    document_ast.json
  evidence/
    source_record.json
    screenshots/
  validation/
    validation-report.json
    warnings.md
```

The capture adapter owns only the capture step. Deterministic rendering, source-record generation, Markdown output, and validation stay in the existing local runner layer unless a narrow compatibility fix is explicitly required.

## Schema Policy

- Use the existing `schemas/page_capture.schema.json`.
- Do not add new schemas for M6.
- Do not broaden `page_capture.schema.json` unless an existing schema contradicts an already-written contract.
- Do not create separate page, research, or price variants of shared evidence objects.

## Failure Semantics

Browser failures must produce auditable failure output, not fake success.

If navigation or capture fails:

- Create `input.json`.
- Create `manifest.json`.
- Create `validation/warnings.md`.
- Set `run_status` to `failed` or `partial`.
- Set `validation_status` to `failed` or `pending`.
- Set `screenshot_policy.status` to `capture_failed` when known.
- Include the source URL when known.
- Do not create fake `artifacts/page.md`.

If the page opens but content is insufficient:

- Set `run_status` to `partial`.
- Set `manual_review.required` to `true`.
- Include `insufficient_content_payload` in `completion_blockers`.
- Run `page_to_md_runner.py` only when `page_capture.json` satisfies the minimum capture contract.

## Acceptance Criteria

- Adapter writes valid, contract-shaped `capture/page_capture.json`.
- Capture includes source URL, page title, accessed time, capture method, and content payload.
- Capture includes browser context, screenshot policy, privacy flags, and warnings.
- Existing `page_to_md_runner.py` consumes the capture JSON without special browser logic.
- Run outputs include `evidence/source_record.json`, screenshot policy status, and validation report.
- Screenshot assets declared by capture are staged into `evidence/screenshots/` and recorded in metadata, source record, manifest, and validation.
- Does not save cookies, tokens, HAR files, browser profiles, passwords, payment details, or unrelated account data.
- Red actions are refused.
- Unapproved Yellow actions stop the run or produce `aborted_by_policy`.
- Browser failure produces `run_status=failed` or `run_status=partial`, never fake complete.
- Existing M0-M5 evals still pass.

## Out of Scope

- Browser research source discovery.
- Ecommerce quote extraction.
- Price comparison.
- Multiple browser backends.
- Logged-in private data export.
- User Chrome profile attachment.
- Current-tab capture.
- Browser history.
- Infinite scroll.
- Stealth browsing, proxies, anti-bot bypass, CAPTCHA handling.
- Marketplace distribution.
- Plugin hooks.

## Tests / Gates

- Existing M0-M5 compile, eval, schema, and plugin validation gates remain required.
- Validate captured `page_capture.json` with `schemas/page_capture.schema.json`.
- Verify `scripts\page_to_md_runner.py --input <run_dir>\capture\page_capture.json` produces valid `page-to-md` artifacts.
- Run `scripts\capture\page_to_md_browser_runner.py` in synthetic observation mode to verify capture -> render -> validation orchestration.
- Adapter contract tests must cover valid capture, missing URL, missing title, no content payload, screenshot-required-but-missing, screenshot staging, non-public URL refusal, redacted private data, red action abort, and prompt injection text treated as page content.
- Keep real-world smoke test records out of committed webpage fixtures; store only non-private notes and paths in `docs/testing/manual-smoke-tests.md` when the first smoke test exists.

## Closeout Requirements

- Document the selected Playwright MCP setup and approval boundary.
- Record at least one local public article/docs smoke test in `docs/testing/manual-smoke-tests.md` without committing webpage content, private screenshots, cookies, or copied article fixtures.
- Report checks run, checks skipped, limitations, and whether optional MCP configuration remains user-controlled.
