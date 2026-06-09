# Testing and Evaluation

## Purpose

Testing for Inward Eyes must prove that outputs are structured, evidence-backed, and failure-aware. Pretty Markdown or charts are not enough.

## Current Command Status

Run from `E:\Inward Eyes`.

- Compile check: `python -m py_compile scripts\page_to_md_runner.py scripts\markdown\render_page_md.py scripts\validation\validate_page_to_md.py scripts\validation\validate_json_schema.py scripts\validation\classify_browser_action.py scripts\inward_eyes\__init__.py scripts\inward_eyes\html_extract.py scripts\inward_eyes\io.py scripts\inward_eyes\markdown.py scripts\inward_eyes\safety.py scripts\inward_eyes\validation.py evals\run_eval.py evals\run_safety_eval.py`
- Eval runner: `python evals\run_eval.py`
- Safety eval runner: `python evals\run_safety_eval.py`
- Validate one page-to-md run: `python scripts\validation\validate_page_to_md.py <run_dir>`
- Minimal schema validation: `python scripts\validation\validate_json_schema.py --schema <schema-path> --json <json-path>`
- Plugin validation: `python C:\Users\62406\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py "E:\Inward Eyes"`
- Plugin packaging check: no package/distribution command exists yet.

Do not claim any command passed unless it was actually run in the current session.

## Test Layers

### Documentation Gate

Used before implementation exists:

- Entry files are compact.
- Current scope resolves through `docs/phase-manifest.yaml`.
- Contracts contain durable rules.
- Planning docs separate active and next work.
- Commands are verified or marked unknown.

### Schema Tests

Every generated JSON artifact must validate against its schema:

- `run_manifest`
- `source_record`
- `page_to_md_metadata`
- `document_ast`
- `research_claim`
- `research_report`
- `price_record`
- `price_compare_run`

### Script Unit Tests

Future deterministic scripts need focused tests:

- Markdown cleanup.
- Heading normalization.
- Boilerplate detection.
- Schema validation.
- Source/Markdown consistency checks.
- Price field normalization.
- Report rendering.
- CSV export.

### Current Fixture Set

Currently implemented:

- public article
- second public article
- docs page
- broken metadata
- page capture JSON
- prompt injection page
- noisy boilerplate page
- synthetic X-like thread
- synthetic forum thread
- synthetic ecommerce product page
- partial/screenshot fallback
- conflicting timestamps
- missing main content

### M2 Closeout Fixture Set

Required before closing M2:

- 2 public articles
- 1 docs page
- 1 synthetic X-like thread
- 1 synthetic forum thread
- 1 synthetic ecommerce product page
- 1 broken metadata page
- 1 noisy boilerplate page
- 1 partial/screenshot-fallback run
- 1 prompt injection page
- 1 conflicting timestamps page
- 1 missing main content page

### Stable Fixture Set

Fixtures should be stored only when licensing and privacy allow. Do not store private logged-in page content in the repository.

Recommended fixture matrix for stable `page-to-md`:

| Page type | Stable target |
| --- | ---: |
| Public news article | 5 |
| Blog/newsletter | 5 |
| Docs page | 3 |
| X-like thread | 5 |
| Forum thread | 5 |
| Ecommerce product page | 5 |
| Login-only synthetic page | 3 |
| Infinite-scroll synthetic page | 3 |
| Paywall/partial-content page | 3 |
| Broken metadata page | 3 |

Stable release should broaden coverage beyond M2 closeout.

## Acceptance Targets

### page-to-md

- Title accuracy target: at least 95% on stable fixtures.
- Unknown author/published time must be marked unknown, not invented.
- Main content coverage target: at least 90% by human review.
- Navigation/ad/recommendation pollution target: at most 5%.
- Login-state, thread, forum, ecommerce, and ambiguous pages must have screenshot evidence.
- All JSON artifacts must pass schema validation.

### browser-research

- Every key fact has a `source_id`.
- Facts, inferences, and unknowns are distinct.
- Comments, ads, and recommendations are not treated as factual sources by default.
- `sources.csv`, `claims.json`, and `report.md` references are consistent.
- Single-source facts are marked when no independent confirmation exists.

### price-compare

- Every quote has URL, access time, screenshot, platform, region, currency, seller, and product specs.
- `match_confidence` exists for every candidate and final quote.
- Low-confidence candidates do not enter "lowest price" conclusions.
- Coupon, shipping, stock, list price, sale price, and estimated total remain separate fields.
- Anomalies are surfaced in `anomalies.md`.
- CSV, JSON, and Markdown outputs agree.

## Manual Review Rules

Manual review is required when:

- Product/spec match confidence is low.
- Multiple publish times conflict.
- Source support is indirect.
- Page requires login and contains personal information.
- Screenshots include usernames, addresses, order state, or account details.
- A task would require a Yellow action without prior user approval.

## Privacy Rules for Tests

- Prefer synthetic fixtures for login-state, account, ecommerce, and dashboard cases.
- Do not commit screenshots containing real personal data.
- Do not commit HAR files, cookies, tokens, browser profiles, or private account data.
