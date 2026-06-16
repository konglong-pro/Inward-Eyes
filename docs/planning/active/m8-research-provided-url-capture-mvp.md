---
doc_type: phase_plan
phase_id: m8_research_provided_url_capture_mvp
title: browser-research provided-URL browser capture MVP
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
closeout: docs/planning/archive/m8-research-provided-url-capture-mvp-closeout.md
---

# M8 browser-research Provided-URL Capture MVP

## Goal

Add browser-backed source capture for `browser-research` using user-provided source URLs only.

M8 captures each approved source into per-source capture evidence, generates the local research input JSON, then runs the existing `browser_research_runner.py`. The existing claim ledger and validator remain the source of truth.

## Scope

- User-provided source URLs only.
- Default source count: 2-10 per run.
- Public URL capture first, using the M6 adapter boundary.
- Current-browser capture only when already user-approved and task-scoped under M7 rules.
- One `SourceRecord` per source.
- One source directory per source under `evidence/`.
- Claim ledger remains mandatory.
- Source independence represented as `independent`, `not_independent`, `unknown`, or `primary_source`.

## Interfaces Touched

- `scripts/research_capture_runner.py`: capture approved URLs, build local research input, run `browser_research_runner.py`, and post-process capture evidence/warnings.
- `scripts/inward_eyes/validation.py`: harden source directory agreement, failed-source support, and non-independent-source support checks.
- `evals/run_research_capture_eval.py`: synthetic integration coverage for the provided-URL capture workflow.
- `.github/workflows/ci.yml`: repository-contained M8 gate.
- `docs/contracts/`, `docs/testing.md`, and `skills/browser-research/SKILL.md`: M8 routing and safety rules.

## Output Shape

```text
<run_dir>/
  input.json
  manifest.json
  capture/
    research-input.json
    source-001/page_capture.json
    source-002/page_capture.json
  artifacts/
    report.md
    claims.json
    sources.csv
    source_notes.md
  evidence/
    source-001/source_record.json
    source-001/screenshots/
    source-002/source_record.json
    source-002/screenshots/
  validation/
    claim-coverage-report.json
    missing-sources.md
    warnings.md
```

## Out of Scope

- Automatic web search.
- Source discovery.
- Following related links.
- Multi-hop browsing.
- Open-ended research from search results.
- Price comparison or ecommerce quote extraction.
- Capturing comments, ads, recommendations, or marketing copy as factual sources by default.
- Cookies, tokens, HAR files, browser profiles, passwords, payment details, local storage, session storage, or unrelated private data.

## Acceptance Criteria

- Given approved URLs, the workflow captures sources and runs the existing research pipeline.
- Every source has `SourceRecord`, URL, title, accessed time, evidence status, and capture method.
- Every key fact/inference has source IDs and support entries.
- Unsupported key claims fail validation.
- Direct and inferred support remain distinct.
- Non-independent/syndicated sources do not count as independent support without note and `single_source=true`.
- Source directories and source IDs agree.
- Report, `sources.csv`, `claims.json`, and manifest agree.
- Source capture failure produces partial or failed run status.
- Prompt-injection text remains source data, not instructions.
- Existing page, safety, research, and price evals still pass.

## Tests / Gates

- `python -m py_compile scripts\page_to_md_runner.py scripts\capture\playwright_mcp_capture.py scripts\capture\page_to_md_browser_runner.py scripts\capture\current_chrome_capture.py scripts\capture\current_chrome_page_to_md_runner.py scripts\research_capture_runner.py scripts\markdown\render_page_md.py scripts\validation\validate_page_to_md.py scripts\validation\validate_page_capture.py scripts\validation\validate_json_schema.py scripts\validation\classify_browser_action.py scripts\validation\validate_browser_research.py scripts\validation\validate_price_compare.py scripts\inward_eyes\__init__.py scripts\inward_eyes\capture.py scripts\inward_eyes\html_extract.py scripts\inward_eyes\io.py scripts\inward_eyes\markdown.py scripts\inward_eyes\safety.py scripts\inward_eyes\validation.py scripts\inward_eyes\research.py scripts\inward_eyes\price.py scripts\browser_research_runner.py scripts\price_compare_runner.py evals\run_eval.py evals\run_safety_eval.py evals\run_research_eval.py evals\run_research_capture_eval.py evals\run_price_eval.py evals\run_capture_adapter_eval.py evals\run_cross_skill_schema_eval.py`
- `python evals\run_eval.py`
- `python evals\run_safety_eval.py`
- `python evals\run_research_eval.py`
- `python evals\run_research_capture_eval.py`
- `python evals\run_price_eval.py`
- `python evals\run_capture_adapter_eval.py`
- `python evals\run_cross_skill_schema_eval.py`
- Schema validation for generated M8 `claims.json`, manifest, and validation report.
- `python scripts\validation\validate_browser_research.py evals\.tmp\research-capture\eval-two-source-supported`
- `python C:\Users\62406\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py "E:\Inward Eyes"`
- `git diff --check`

## Closeout Requirements

- Create `docs/planning/archive/m8-research-provided-url-capture-mvp-closeout.md`.
- Record what shipped, frozen behavior, tests/gates run, known limitations, and M10 discovery deferral.
