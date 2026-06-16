---
doc_type: phase_plan
phase_id: m7_current_chrome_capture_mvp
title: Current Chrome / logged-in page capture MVP
status: completed
canonical: true
related_contracts:
  - docs/contracts/capture-adapter-contract.md
  - docs/contracts/browser-operation-contract.md
  - docs/contracts/evidence-contract.md
  - docs/contracts/schemas-and-validation-contract.md
  - docs/contracts/safety-contract.md
related_adrs:
  - docs/adr/0001-evidence-first-browser-workflows.md
closeout: docs/planning/archive/m7-current-chrome-capture-mvp-closeout.md
---

# M7 Current Chrome / Logged-in Page Capture MVP

## Goal

Safely capture one user-approved, currently visible Chrome page into `capture/page_capture.json`, then reuse the existing `page-to-md` runner and validators.

M7 proves the current-browser boundary only. It does not claim broad logged-in-page support.

## Scope

- One currently visible Chrome page.
- One explicit user approval per capture.
- `page-to-md` only.
- Capture visible URL, page title, access time, login-state signal, page text or structured snapshot, privacy flags, screenshot policy, and capture warnings.
- Screenshot evidence is required for logged-in, private-data, dynamic, thread, forum, ecommerce, ambiguous, and personal-context pages.
- Screenshots are accepted only after privacy review/redaction policy is applied.
- Existing `scripts/page_to_md_runner.py` consumes the resulting `capture/page_capture.json` without a browser-specific rendering path.

## Interfaces Touched

- `scripts/capture/current_chrome_capture.py`: writes current-browser `page_capture.json` from already-approved visible page observations.
- `scripts/capture/current_chrome_page_to_md_runner.py`: runs capture -> capture validation -> deterministic render -> run validation.
- `scripts/inward_eyes/capture.py`: shared capture shape, login/privacy aliases, current-browser contract validation, screenshot policy enforcement.
- `scripts/page_to_md_runner.py`: screenshot hash staging and privacy metadata propagation.
- `scripts/inward_eyes/validation.py`: missing screenshot evidence and screenshot hash validation.
- `schemas/page_capture.schema.json`: top-level login/privacy aliases.
- `evals/run_capture_adapter_eval.py`: synthetic current-browser contract cases.

## Out of Scope

- Multi-tab scanning.
- Account menu exploration.
- Inbox, order, dashboard, or private area crawling.
- Browser profile export.
- Cookies, tokens, HAR, local storage, session storage, passwords, payment details, or network logs.
- `browser-research` source capture.
- `price-compare` product capture.
- Broad crawling, automated search, X/forum infinite-scroll thread capture, ecommerce quote extraction, marketplace distribution, or plugin hooks.

## Acceptance Criteria

- Captures exactly one user-approved current browser page.
- Produces schema-valid `capture/page_capture.json`.
- Produces the standard `page-to-md` run directory: `input.json`, `manifest.json`, `capture/page_capture.json`, `artifacts/`, `evidence/source_record.json`, `evidence/screenshots/`, and `validation/`.
- Logged-in/private/dynamic pages enforce screenshot policy.
- Screenshot evidence copied into `evidence/screenshots/` is recorded in the manifest with `sha256`.
- Private-data warnings force manual review.
- Prompt-injection text remains page data.
- Red actions abort with `run_status=aborted_by_policy`.
- Existing M2/M3/M4/M5 evals still pass.

## Tests / Gates

- `python -m py_compile scripts\page_to_md_runner.py scripts\capture\playwright_mcp_capture.py scripts\capture\page_to_md_browser_runner.py scripts\capture\current_chrome_capture.py scripts\capture\current_chrome_page_to_md_runner.py scripts\markdown\render_page_md.py scripts\validation\validate_page_to_md.py scripts\validation\validate_page_capture.py scripts\validation\validate_json_schema.py scripts\validation\classify_browser_action.py scripts\validation\validate_browser_research.py scripts\validation\validate_price_compare.py scripts\inward_eyes\__init__.py scripts\inward_eyes\capture.py scripts\inward_eyes\html_extract.py scripts\inward_eyes\io.py scripts\inward_eyes\markdown.py scripts\inward_eyes\safety.py scripts\inward_eyes\validation.py scripts\inward_eyes\research.py scripts\inward_eyes\price.py scripts\browser_research_runner.py scripts\price_compare_runner.py evals\run_eval.py evals\run_safety_eval.py evals\run_research_eval.py evals\run_price_eval.py evals\run_capture_adapter_eval.py evals\run_cross_skill_schema_eval.py`
- `python evals\run_eval.py`
- `python evals\run_safety_eval.py`
- `python evals\run_research_eval.py`
- `python evals\run_price_eval.py`
- `python evals\run_capture_adapter_eval.py`
- `python evals\run_cross_skill_schema_eval.py`
- Schema validation for generated M7 `page_capture.json`.
- `python scripts\validation\validate_page_to_md.py <synthetic-current-browser-run-dir>`
- `python C:\Users\62406\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py "E:\Inward Eyes"`
- `git diff --check`

## Closeout Requirements

- Create `docs/planning/archive/m7-current-chrome-capture-mvp-closeout.md`.
- Record what shipped, frozen behavior, gates run, known limitations, and deferred work.
- Keep manual smoke documentation free of real logged-in page content and screenshots.
