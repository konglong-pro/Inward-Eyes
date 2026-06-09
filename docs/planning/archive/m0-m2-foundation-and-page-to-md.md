---
doc_type: phase_plan
phase_id: m0_m2_foundation_page_to_md
title: Foundation and page-to-md
status: completed
canonical: true
related_contracts:
  - docs/contracts/evidence-contract.md
  - docs/contracts/browser-operation-contract.md
  - docs/contracts/schemas-and-validation-contract.md
  - docs/contracts/safety-contract.md
related_adrs:
  - docs/adr/0001-evidence-first-browser-workflows.md
---

# M0-M2 Foundation and page-to-md

## Goal

Build the non-code and then implementation foundation for Inward Eyes, ending with a tested `page-to-md` MVP that converts one scoped page/thread into auditable Markdown.

This document defines the execution plan and current M1-M2 implementation target.

## Product Principle

Do not build a universal browser agent. Build evidence-backed browser workflows for Codex.

## Milestone 0: Documentation and Contracts

### Scope

- Project entry docs.
- Architecture.
- Testing strategy.
- Evidence contract.
- Browser operation contract.
- Schema and validation contract.
- Safety contract.
- ADR for evidence-first workflow.

### Acceptance Criteria

- `AGENTS.md` routes agents to canonical docs.
- `docs/phase-manifest.yaml` declares the active phase.
- Durable rules live in `docs/contracts/`.
- Active and next work are separated.
- Commands are marked unknown until implementation exists.

Status: complete for the initial documentation baseline.

## Milestone 1: Foundation Scaffold

### Planned Files

```text
.codex-plugin/plugin.json
skills/page-to-md/SKILL.md
skills/page-to-md/agents/openai.yaml
skills/page-to-md/references/
schemas/source_record.schema.json
schemas/run_manifest.schema.json
schemas/page_to_md_metadata.schema.json
schemas/document_ast.schema.json
scripts/validation/
scripts/markdown/
scripts/reports/
evals/fixtures/page-to-md/
evals/goldens/page-to-md/
```

### Implementation Tasks

1. Create minimal plugin manifest with `skills` only.
2. Write `page-to-md/SKILL.md` with clear trigger boundaries.
3. Add optional `agents/openai.yaml` with UI metadata.
4. Define shared schemas.
5. Implement validators after schema files exist.
6. Implement deterministic Markdown renderer from `document_ast`.
7. Implement run directory writer.
8. Implement manifest writer.
9. Add synthetic fixtures.

### Acceptance Criteria

- No browser task can produce a final artifact without `manifest.json`.
- Schema validation failure prevents "complete" status.
- Runtime output directory is configurable.
- Plugin source stays free of runtime captured evidence.

Status: initial baseline implemented for local HTML and page capture JSON. Manifest artifact/evidence path checks, source records, screenshot policy, and safety action evals are implemented. Browser/MCP capture is not implemented.

## Milestone 2: page-to-md MVP

### Supported Inputs

- Local HTML file.
- `page_capture.json`.
- URL/current browser page through future browser adapters.
- Screenshot plus URL only as fallback and marked partial.

### Supported Page Types

- Public article.
- Blog/newsletter.
- Docs page.
- X-like thread.
- Forum thread.
- Ecommerce product page as page conversion only, not comparison.
- Unknown page type with warnings.

### Required Output Directory

```text
<output_root>/<run_id>-page-to-md/
  input.json
  manifest.json
  artifacts/
    page.md
    metadata.json
    document_ast.json
  evidence/
    source_record.json
    screenshots/
      screenshot-full.png        # only when required or captured
  validation/
    validation-report.json
    warnings.md
```

### Required Metadata

- Source URL.
- Canonical URL when available.
- Page title.
- Site name when available.
- Access time.
- Requires login.
- Document title with confidence and evidence.
- Author with confidence and evidence, or explicit unknown.
- Published time with confidence and evidence, or explicit unknown.
- Language when available.
- Page type.
- Extraction method.
- Tool chain.
- Excluded blocks.
- Warnings.

### Extraction Procedure

1. Identify page type.
2. Select the least-privileged structured extraction route.
3. Capture source record.
4. Capture screenshot when required.
5. Extract metadata.
6. Extract main content into Document AST.
7. Remove navigation, ads, cookie banners, recommendations, sidebars, and unrelated comments.
8. Preserve headings, paragraphs, lists, quotes, code blocks, tables, images, and captions.
9. Mark unknown fields explicitly.
10. Validate metadata, AST, Markdown, and evidence.
11. Render Markdown from structured data.
12. Write manifest and warnings.

### page.md Required Shape

```md
---
title: "..."
author: null
published_at: null
source_url: "..."
canonical_url: "..."
accessed_at: "..."
page_type: "article"
extraction_method: "..."
warnings:
  - author_not_found
---

# Title

> Source: ...
> Accessed: ...

...
```

### Validation Requirements

- `source.url` exists.
- `accessed_at` exists.
- Title exists or `title_not_found` warning exists.
- Author and published time are never invented.
- Markdown has one primary H1.
- Metadata title and Markdown H1 are consistent.
- Boilerplate terms are detected and warned.
- Body length is not suspiciously short without warning.
- URL count does not unexpectedly explode.
- Images include captions/alt text or `no_caption` warning.
- Screenshot requirements are enforced.
- Extraction method is recorded.

## Testing Plan

### MVP Fixture Set

M2 closeout fixture set:

- 2 public articles.
- 1 docs page.
- 1 synthetic X-like thread.
- 1 synthetic forum thread.
- 1 synthetic ecommerce product page.
- 1 broken metadata page.
- 1 noisy boilerplate page.
- 1 partial/screenshot-fallback run.
- 1 prompt injection page.
- 1 conflicting timestamps page.
- 1 missing main content page.

### Stable Fixture Set

Expand toward the matrix in `docs/testing.md` before stable release.

### Gates

Current gates:

- `python -m py_compile scripts\page_to_md_runner.py scripts\markdown\render_page_md.py scripts\validation\validate_page_to_md.py scripts\validation\validate_json_schema.py scripts\validation\classify_browser_action.py scripts\inward_eyes\__init__.py scripts\inward_eyes\html_extract.py scripts\inward_eyes\io.py scripts\inward_eyes\markdown.py scripts\inward_eyes\safety.py scripts\inward_eyes\validation.py evals\run_eval.py evals\run_safety_eval.py`
- `python evals\run_eval.py`
- `python evals\run_safety_eval.py`
- `python scripts\validation\validate_page_to_md.py <run_dir>`
- `python scripts\validation\validate_json_schema.py --schema <schema-path> --json <json-path>`
- `python C:\Users\62406\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py "E:\Inward Eyes"`

## Closeout Requirements

M2 can close only when:

- `page-to-md` skill exists.
- Required schemas exist.
- Deterministic renderer exists.
- Validation report exists for each run.
- At least the MVP fixture set passes.
- Known limitations are documented.
- `docs/project-status.md` is updated.

Status: complete. See `docs/planning/archive/m0-m2-closeout.md`.
