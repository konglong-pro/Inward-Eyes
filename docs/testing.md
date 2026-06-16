# Testing and Evaluation

## Purpose

Testing for Inward Eyes must prove that outputs are structured, evidence-backed, and failure-aware. Pretty Markdown or charts are not enough.

## Current Command Status

Run from `E:\Inward Eyes`.

The current release class is M10 small-scope discovery closeout. CI covers repository-contained local workflows and synthetic adapter/discovery contract tests, not live browser/network smoke tests.

- Compile check: `python -m py_compile scripts\page_to_md_runner.py scripts\markdown\render_page_md.py scripts\validation\validate_page_to_md.py scripts\validation\validate_json_schema.py scripts\validation\classify_browser_action.py scripts\inward_eyes\__init__.py scripts\inward_eyes\html_extract.py scripts\inward_eyes\io.py scripts\inward_eyes\markdown.py scripts\inward_eyes\safety.py scripts\inward_eyes\validation.py evals\run_eval.py evals\run_safety_eval.py`
- M3 research compile check: `python -m py_compile scripts\browser_research_runner.py scripts\validation\validate_browser_research.py scripts\inward_eyes\research.py scripts\inward_eyes\validation.py evals\run_research_eval.py`
- M4 price compile check: `python -m py_compile scripts\price_compare_runner.py scripts\validation\validate_price_compare.py scripts\inward_eyes\price.py scripts\inward_eyes\validation.py evals\run_price_eval.py`
- M9 price capture compile check: `python -m py_compile scripts\price_capture_runner.py scripts\price_compare_runner.py scripts\validation\validate_price_compare.py scripts\inward_eyes\price.py scripts\inward_eyes\validation.py evals\run_price_capture_eval.py`
- M10A research discovery compile check: `python -m py_compile scripts\research_discovery_runner.py scripts\validation\validate_research_discovery.py scripts\inward_eyes\discovery.py scripts\inward_eyes\validation.py evals\run_research_discovery_eval.py`
- M10B price candidate discovery compile check: `python -m py_compile scripts\price_candidate_discovery_runner.py scripts\validation\validate_price_candidate_discovery.py scripts\inward_eyes\price_discovery.py scripts\inward_eyes\validation.py evals\run_price_candidate_discovery_eval.py`
- Capture adapter compile check: `python -m py_compile scripts\capture\playwright_mcp_capture.py scripts\capture\page_to_md_browser_runner.py scripts\capture\current_chrome_capture.py scripts\capture\current_chrome_page_to_md_runner.py scripts\validation\validate_page_capture.py scripts\inward_eyes\capture.py evals\run_capture_adapter_eval.py evals\run_cross_skill_schema_eval.py`
- M10 full compile check: `python -m py_compile scripts\page_to_md_runner.py scripts\capture\playwright_mcp_capture.py scripts\capture\page_to_md_browser_runner.py scripts\capture\current_chrome_capture.py scripts\capture\current_chrome_page_to_md_runner.py scripts\research_discovery_runner.py scripts\research_capture_runner.py scripts\price_candidate_discovery_runner.py scripts\price_capture_runner.py scripts\markdown\render_page_md.py scripts\validation\validate_page_to_md.py scripts\validation\validate_page_capture.py scripts\validation\validate_json_schema.py scripts\validation\classify_browser_action.py scripts\validation\validate_research_discovery.py scripts\validation\validate_browser_research.py scripts\validation\validate_price_candidate_discovery.py scripts\validation\validate_price_compare.py scripts\inward_eyes\__init__.py scripts\inward_eyes\capture.py scripts\inward_eyes\discovery.py scripts\inward_eyes\price_discovery.py scripts\inward_eyes\html_extract.py scripts\inward_eyes\io.py scripts\inward_eyes\markdown.py scripts\inward_eyes\safety.py scripts\inward_eyes\validation.py scripts\inward_eyes\research.py scripts\inward_eyes\price.py scripts\browser_research_runner.py scripts\price_compare_runner.py evals\run_eval.py evals\run_safety_eval.py evals\run_research_eval.py evals\run_research_discovery_eval.py evals\run_research_capture_eval.py evals\run_price_eval.py evals\run_price_candidate_discovery_eval.py evals\run_price_capture_eval.py evals\run_capture_adapter_eval.py evals\run_cross_skill_schema_eval.py`
- Eval runner: `python evals\run_eval.py`
- Safety eval runner: `python evals\run_safety_eval.py`
- Research eval runner: `python evals\run_research_eval.py`
- Research discovery eval runner: `python evals\run_research_discovery_eval.py`
- Research capture eval runner: `python evals\run_research_capture_eval.py`
- Price eval runner: `python evals\run_price_eval.py`
- Price candidate discovery eval runner: `python evals\run_price_candidate_discovery_eval.py`
- Price capture eval runner: `python evals\run_price_capture_eval.py`
- Capture adapter eval runner: `python evals\run_capture_adapter_eval.py`
- Cross-skill schema reuse eval runner: `python evals\run_cross_skill_schema_eval.py`
- M6 wrapper runner: `python scripts\capture\page_to_md_browser_runner.py --url <public-url> --run-id <run-id> --output-root <output-root>`
- M7 current Chrome wrapper runner: `python scripts\capture\current_chrome_page_to_md_runner.py --url <visible-url> --user-approved-current-page --page-title "<visible-title>" --selected-main-content-file <redacted-text-file> --output-root <output-root> --run-id <run-id>`
- M8 provided-URL research capture runner: `python scripts\research_capture_runner.py --question "<question>" --url <approved-url-1> --url <approved-url-2> --output-root <output-root> --run-id <run-id>`
- M10A small-scope research discovery runner: `python scripts\research_discovery_runner.py --input <discovery-spec.json> --output-root <output-root> --run-id <run-id>`
- M9 product-URL price capture runner: `python scripts\price_capture_runner.py --target-name "<product>" --required-spec key=value --url <approved-product-url-1> --url <approved-product-url-2> --output-root <output-root> --run-id <run-id>`
- M10B approved candidate discovery runner: `python scripts\price_candidate_discovery_runner.py --input <candidate-discovery-spec.json> --output-root <output-root> --run-id <run-id>`
- Validate one page-to-md run: `python scripts\validation\validate_page_to_md.py <run_dir>`
- Validate one page capture: `python scripts\validation\validate_page_capture.py <run_dir>\capture\page_capture.json`
- Validate one browser-research run: `python scripts\validation\validate_browser_research.py <run_dir>`
- Validate one research discovery run: `python scripts\validation\validate_research_discovery.py <run_dir>`
- Validate one price candidate discovery run: `python scripts\validation\validate_price_candidate_discovery.py <run_dir>`
- Validate one price-compare run: `python scripts\validation\validate_price_compare.py <run_dir>`
- Minimal schema validation: `python scripts\validation\validate_json_schema.py --schema <schema-path> --json <json-path>`
- Nested schema validation: `python scripts\validation\validate_json_schema.py --schema <schema-path> --json <json-path> --pointer /path/to/value`
- CI workflow: `.github/workflows/ci.yml`
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
- `research_discovery_input`
- `discovery_log`
- `price_candidate_discovery_input`
- `price_candidates`
- `price_record`
- `price_compare_run`
- `validation_report`
- `run_manifest` status fields: `run_status`, `validation_status`, `manual_review`, and `completion_blockers`

Cross-skill schema reuse must also prove that `page-to-md`, `browser-research`, and `price-compare` use the same shared object shapes:

- `SourceRecord`
- `RunManifest`
- `ScreenshotPolicy`
- `ManualReview`
- `ValidationReport`

The stable gate for this is `python evals\run_cross_skill_schema_eval.py`.

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
- browser-research claim ledger pass fixture
- browser-research unsupported claim fail fixture
- price-compare valid quotes fixture
- price-compare low-confidence exclusion fixture
- price-compare missing screenshot fail fixture
- M6 valid page capture contract fixture
- M6 invalid capture contract fixtures for missing URL, missing title, no content payload, missing screenshot, non-public URL, redacted private data, and prompt injection text
- M6 wrapper and screenshot-staging synthetic checks
- M7 current Chrome synthetic checks for logged-in screenshot present, logged-in screenshot missing, private-data manual review, prompt-injection text as data, and Red action abort
- M8 research capture synthetic checks for two-source support, unsupported claim failure, single-source marking, syndicated/non-independent sources, source capture failure, and prompt-injection text as data
- M9 price capture synthetic checks for two matching product URLs, low-confidence spec mismatch, coupon action required, cart required, missing shipping fee, missing screenshot failure, out-of-stock quote exclusion, and different-region manual review
- M10A research discovery synthetic checks for 3-source bounded discovery, hard max-source cap failure, rejected source with reason, unsupported claim failure after discovery, syndicated duplicate not independent, and prompt-injection search result rejection
- M10B price candidate discovery synthetic checks for matching candidates within cap, outside allowed domain failure, low-confidence spec mismatch review exclusion, duplicate product URL rejection, recommendation link rejection, total cap failure, and coupon-action quote exclusion from lowest-price conclusions

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
- Discovery is bounded by user-approved scope.
- Discovery selected source count never exceeds `max_sources`.
- Every selected discovery source has rationale and a `SourceRecord`.
- Discovery logs preserve accepted/rejected candidate reasons.
- Prompt-injection search result text is data, not instruction.

### price-compare

- Every quote has URL, access time, screenshot, platform, region, currency, seller, and product specs.
- Candidate discovery is bounded by approved platforms/domains and candidate caps.
- Every candidate has match confidence, mismatch flags, and rationale.
- Low-confidence or incomplete candidates do not enter quote extraction unless explicitly approved.
- `match_confidence` exists for every candidate and final quote.
- Low-confidence candidates do not enter "lowest price" conclusions.
- Coupon, shipping, stock, list price, sale price, and estimated total remain separate fields.
- Product-page screenshots are required for browser-captured product URL quotes.
- Coupon/cart/checkout/address-change requirements are explicit and excluded from lowest-price conclusions.
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
