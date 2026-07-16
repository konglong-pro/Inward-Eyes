# Testing and Evaluation

## Purpose

Testing for Inward Eyes must prove that outputs are structured, evidence-backed, and failure-aware. Pretty Markdown or charts are not enough.

## Current Command Status

Run from the repository root.

The current release class is post-M21 contract-integrity hardening. CI covers repository-contained local workflows, synthetic adapter/discovery contract tests, deterministic replay evals, profile validation, local review, batch/retry/indexing, reproducible package dry-run, exporters, contract drift, strict continuation/admission boundaries, and privacy-retention regression tests. It does not run live browser/network smoke tests.

- M0-M2/page-to-md compile check: `python -m py_compile scripts\page_to_md_runner.py scripts\markdown\render_page_md.py scripts\validation\validate_page_to_md.py scripts\validation\validate_json_schema.py scripts\validation\classify_browser_action.py scripts\inward_eyes\__init__.py scripts\inward_eyes\html_extract.py scripts\inward_eyes\io.py scripts\inward_eyes\markdown.py scripts\inward_eyes\safety.py scripts\inward_eyes\validation.py evals\run_eval.py evals\run_safety_eval.py`
- M3 research compile check: `python -m py_compile scripts\browser_research_runner.py scripts\validation\validate_browser_research.py scripts\inward_eyes\research.py scripts\inward_eyes\validation.py evals\run_research_eval.py`
- M4 price compile check: `python -m py_compile scripts\price_compare_runner.py scripts\validation\validate_price_compare.py scripts\inward_eyes\price.py scripts\inward_eyes\validation.py evals\run_price_eval.py`
- M9 price capture compile check: `python -m py_compile scripts\price_capture_runner.py scripts\price_compare_runner.py scripts\validation\validate_price_compare.py scripts\inward_eyes\price.py scripts\inward_eyes\validation.py evals\run_price_capture_eval.py`
- M10A research discovery compile check: `python -m py_compile scripts\research_discovery_runner.py scripts\validation\validate_research_discovery.py scripts\inward_eyes\discovery.py scripts\inward_eyes\validation.py evals\run_research_discovery_eval.py`
- M10B price candidate discovery compile check: `python -m py_compile scripts\price_candidate_discovery_runner.py scripts\validation\validate_price_candidate_discovery.py scripts\inward_eyes\price_discovery.py scripts\inward_eyes\validation.py evals\run_price_candidate_discovery_eval.py`
- Capture adapter compile check: `python -m py_compile scripts\capture\playwright_mcp_capture.py scripts\capture\page_to_md_browser_runner.py scripts\capture\current_chrome_capture.py scripts\capture\current_chrome_page_to_md_runner.py scripts\validation\validate_page_capture.py scripts\inward_eyes\capture.py evals\run_capture_adapter_eval.py evals\run_cross_skill_schema_eval.py`
- Release validation compile check: `python -m py_compile scripts\validation\validate_contract_drift.py scripts\validation\validate_plugin.py scripts\validation\validate_release.py scripts\inward_eyes\distribution.py scripts\plugin_package.py evals\run_distribution_eval.py`
- Full compile gate: `python -m py_compile scripts\page_to_md_runner.py scripts\capture\playwright_mcp_capture.py scripts\capture\page_to_md_browser_runner.py scripts\capture\current_chrome_capture.py scripts\capture\current_chrome_page_to_md_runner.py scripts\research_discovery_runner.py scripts\research_capture_runner.py scripts\price_candidate_discovery_runner.py scripts\price_capture_runner.py scripts\adapter_matrix_runner.py scripts\site_profile_runner.py scripts\privacy_report_runner.py scripts\review_run.py scripts\run_database.py scripts\export_run.py scripts\plugin_package.py scripts\batch_runner.py scripts\markdown\render_page_md.py scripts\validation\validate_page_to_md.py scripts\validation\validate_page_capture.py scripts\validation\validate_json_schema.py scripts\validation\validate_contract_drift.py scripts\validation\validate_plugin.py scripts\validation\validate_release.py scripts\validation\classify_browser_action.py scripts\validation\validate_research_discovery.py scripts\validation\validate_browser_research.py scripts\validation\validate_price_candidate_discovery.py scripts\validation\validate_price_compare.py scripts\inward_eyes\__init__.py scripts\inward_eyes\capture.py scripts\inward_eyes\discovery.py scripts\inward_eyes\price_discovery.py scripts\inward_eyes\adapter_matrix.py scripts\inward_eyes\html_extract.py scripts\inward_eyes\io.py scripts\inward_eyes\paths.py scripts\inward_eyes\markdown.py scripts\inward_eyes\safety.py scripts\inward_eyes\validation.py scripts\inward_eyes\research.py scripts\inward_eyes\price.py scripts\inward_eyes\site_profiles.py scripts\inward_eyes\privacy.py scripts\inward_eyes\review.py scripts\inward_eyes\run_index.py scripts\inward_eyes\exporters.py scripts\inward_eyes\distribution.py scripts\browser_research_runner.py scripts\price_compare_runner.py evals\run_eval.py evals\run_safety_eval.py evals\run_research_eval.py evals\run_research_discovery_eval.py evals\run_research_capture_eval.py evals\run_price_eval.py evals\run_price_candidate_discovery_eval.py evals\run_price_capture_eval.py evals\run_capture_adapter_eval.py evals\run_cross_skill_schema_eval.py evals\run_adapter_matrix_eval.py evals\run_real_world_eval.py evals\run_privacy_eval.py evals\run_site_profile_eval.py evals\run_review_ui_eval.py evals\run_distribution_eval.py evals\run_batch_retry_eval.py evals\run_export_eval.py`
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
- Adapter matrix eval runner: `python evals\run_adapter_matrix_eval.py`
- Real-world replay eval runner: `python evals\run_real_world_eval.py`
- Privacy eval runner: `python evals\run_privacy_eval.py`
- Site profile eval runner: `python evals\run_site_profile_eval.py`
- Review UI eval runner: `python evals\run_review_ui_eval.py`
- Distribution eval runner: `python evals\run_distribution_eval.py`
- Batch/retry eval runner: `python evals\run_batch_retry_eval.py`
- Export eval runner: `python evals\run_export_eval.py`
- Adapter matrix runner: `python scripts\adapter_matrix_runner.py --output-root <output-root> --run-id <run-id>`
- Site profile runner: `python scripts\site_profile_runner.py --url <url> --page-type <page-type> --output-root <output-root> --run-id <run-id>`
- Privacy report runner: `python scripts\privacy_report_runner.py <target> --output-root <output-root> --run-id <run-id>`
- Review one run: `python scripts\review_run.py <run_dir>`
- Build run index: `python scripts\run_database.py index --output-root <output-root> --index <index-jsonl>`
- Build retry plan: `python scripts\run_database.py retry-plan --index <index-jsonl> --output <retry-plan-json>`
- Batch runner: `python scripts\batch_runner.py --spec <batch-spec.json> --output-root <output-root> --run-id <run-id>`
- Export one run: `python scripts\export_run.py <run_dir> --output-dir <output-dir>`
- Package dry-run: `python scripts\plugin_package.py --output-dir <output-dir>`
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
- Contract drift validation: `python scripts\validation\validate_contract_drift.py`
- Portable plugin validation: `python scripts\validation\validate_plugin.py .`
- Release input validation: `python scripts\validation\validate_release.py .`
- Plugin packaging dry-run: `python scripts\plugin_package.py --output-dir dist`

Do not claim any command passed unless it was actually run in the current session.

The completed M21 gate is summarized in `docs/planning/archive/m21-contract-integrity-hardening-closeout.md#acceptance-gates`.

The standard-library schema validator is a structural smoke gate only. It supports local JSON Pointer `$ref`, composition keywords, core object/array/string/numeric constraints, and JSON Pointer selection. It rejects external refs and does not implement `format`, `if`/`then`/`else`, or the complete JSON Schema 2020-12 vocabulary. Workflow-specific validators remain authoritative for release readiness.

## Generated Artifact Validation Block

Run after the eval suite has generated `evals\.tmp\`.

```powershell
python scripts\validation\validate_json_schema.py --schema schemas\page_to_md_metadata.schema.json --json evals\.tmp\page-to-md\eval-public-article\artifacts\metadata.json
python scripts\validation\validate_json_schema.py --schema schemas\document_ast.schema.json --json evals\.tmp\page-to-md\eval-public-article\artifacts\document_ast.json
python scripts\validation\validate_json_schema.py --schema schemas\source_record.schema.json --json evals\.tmp\page-to-md\eval-public-article\evidence\source_record.json
python scripts\validation\validate_json_schema.py --schema schemas\page_capture.schema.json --json evals\.tmp\capture-adapter\valid-capture\capture\page_capture.json
python scripts\validation\validate_json_schema.py --schema schemas\page_capture.schema.json --json evals\.tmp\capture-adapter\current-chrome-output\eval-current-chrome-logged-in\capture\page_capture.json
python scripts\validation\validate_json_schema.py --schema schemas\run_manifest.schema.json --json evals\.tmp\page-to-md\eval-public-article\manifest.json
python scripts\validation\validate_json_schema.py --schema schemas\validation_report.schema.json --json evals\.tmp\page-to-md\eval-public-article\validation\validation-report.json
python scripts\validation\validate_json_schema.py --schema schemas\research_report.schema.json --json evals\.tmp\browser-research\eval-evidence-backed-research\artifacts\claims.json
python scripts\validation\validate_json_schema.py --schema schemas\research_claim.schema.json --json evals\.tmp\browser-research\eval-evidence-backed-research\artifacts\claims.json --pointer /claims/0
python scripts\validation\validate_json_schema.py --schema schemas\source_record.schema.json --json evals\.tmp\browser-research\eval-evidence-backed-research\evidence\source-001\source_record.json
python scripts\validation\validate_json_schema.py --schema schemas\research_discovery_input.schema.json --json evals\.tmp\research-discovery\eval-bounded-three-sources\input.json
python scripts\validation\validate_json_schema.py --schema schemas\discovery_log.schema.json --json evals\.tmp\research-discovery\eval-bounded-three-sources\artifacts\discovery-log.json
python scripts\validation\validate_json_schema.py --schema schemas\research_report.schema.json --json evals\.tmp\research-capture\eval-two-source-supported\artifacts\claims.json
python scripts\validation\validate_json_schema.py --schema schemas\run_manifest.schema.json --json evals\.tmp\browser-research\eval-evidence-backed-research\manifest.json
python scripts\validation\validate_json_schema.py --schema schemas\run_manifest.schema.json --json evals\.tmp\research-discovery\eval-bounded-three-sources\manifest.json
python scripts\validation\validate_json_schema.py --schema schemas\run_manifest.schema.json --json evals\.tmp\research-capture\eval-two-source-supported\manifest.json
python scripts\validation\validate_json_schema.py --schema schemas\validation_report.schema.json --json evals\.tmp\browser-research\eval-evidence-backed-research\validation\claim-coverage-report.json
python scripts\validation\validate_json_schema.py --schema schemas\validation_report.schema.json --json evals\.tmp\research-discovery\eval-bounded-three-sources\validation\discovery-validation-report.json
python scripts\validation\validate_json_schema.py --schema schemas\validation_report.schema.json --json evals\.tmp\research-discovery\eval-bounded-three-sources\validation\claim-coverage-report.json
python scripts\validation\validate_json_schema.py --schema schemas\validation_report.schema.json --json evals\.tmp\research-capture\eval-two-source-supported\validation\claim-coverage-report.json
python scripts\validation\validate_json_schema.py --schema schemas\price_compare_run.schema.json --json evals\.tmp\price-compare\eval-product-quotes\artifacts\prices.json
python scripts\validation\validate_json_schema.py --schema schemas\price_candidate_discovery_input.schema.json --json evals\.tmp\price-candidate-discovery\eval-matching-candidates-within-cap\input.json
python scripts\validation\validate_json_schema.py --schema schemas\price_candidates.schema.json --json evals\.tmp\price-candidate-discovery\eval-matching-candidates-within-cap\artifacts\candidates.json
python scripts\validation\validate_json_schema.py --schema schemas\price_compare_run.schema.json --json evals\.tmp\price-candidate-discovery\eval-matching-candidates-within-cap\artifacts\prices.json
python scripts\validation\validate_json_schema.py --schema schemas\price_compare_run.schema.json --json evals\.tmp\price-capture\eval-two-matching-product-urls\artifacts\prices.json
python scripts\validation\validate_json_schema.py --schema schemas\price_record.schema.json --json evals\.tmp\price-compare\eval-product-quotes\artifacts\prices.json --pointer /quotes/0
python scripts\validation\validate_json_schema.py --schema schemas\source_record.schema.json --json evals\.tmp\price-compare\eval-product-quotes\evidence\source-001\source_record.json
python scripts\validation\validate_json_schema.py --schema schemas\price_record.schema.json --json evals\.tmp\price-candidate-discovery\eval-matching-candidates-within-cap\artifacts\prices.json --pointer /quotes/0
python scripts\validation\validate_json_schema.py --schema schemas\price_record.schema.json --json evals\.tmp\price-capture\eval-two-matching-product-urls\artifacts\prices.json --pointer /quotes/0
python scripts\validation\validate_json_schema.py --schema schemas\site_profiles.schema.json --json profiles\site_profiles.json
python scripts\validation\validate_json_schema.py --schema schemas\run_manifest.schema.json --json evals\.tmp\price-compare\eval-product-quotes\manifest.json
python scripts\validation\validate_json_schema.py --schema schemas\run_manifest.schema.json --json evals\.tmp\price-candidate-discovery\eval-matching-candidates-within-cap\manifest.json
python scripts\validation\validate_json_schema.py --schema schemas\run_manifest.schema.json --json evals\.tmp\price-capture\eval-two-matching-product-urls\manifest.json
python scripts\validation\validate_json_schema.py --schema schemas\validation_report.schema.json --json evals\.tmp\price-compare\eval-product-quotes\validation\price-validation-report.json
python scripts\validation\validate_json_schema.py --schema schemas\validation_report.schema.json --json evals\.tmp\price-candidate-discovery\eval-matching-candidates-within-cap\validation\candidate-validation-report.json
python scripts\validation\validate_json_schema.py --schema schemas\validation_report.schema.json --json evals\.tmp\price-candidate-discovery\eval-matching-candidates-within-cap\validation\price-validation-report.json
python scripts\validation\validate_json_schema.py --schema schemas\validation_report.schema.json --json evals\.tmp\price-capture\eval-two-matching-product-urls\validation\price-validation-report.json
python scripts\validation\validate_page_to_md.py evals\.tmp\page-to-md\eval-public-article
python scripts\validation\validate_page_capture.py evals\.tmp\capture-adapter\current-chrome-output\eval-current-chrome-logged-in\capture\page_capture.json
python scripts\validation\validate_browser_research.py evals\.tmp\browser-research\eval-evidence-backed-research
python scripts\validation\validate_research_discovery.py evals\.tmp\research-discovery\eval-bounded-three-sources
python scripts\validation\validate_browser_research.py evals\.tmp\research-discovery\eval-bounded-three-sources
python scripts\validation\validate_browser_research.py evals\.tmp\research-capture\eval-two-source-supported
python scripts\validation\validate_price_compare.py evals\.tmp\price-compare\eval-product-quotes
python scripts\validation\validate_price_candidate_discovery.py evals\.tmp\price-candidate-discovery\eval-matching-candidates-within-cap
python scripts\validation\validate_price_compare.py evals\.tmp\price-candidate-discovery\eval-matching-candidates-within-cap
python scripts\validation\validate_price_compare.py evals\.tmp\price-capture\eval-two-matching-product-urls
```

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

The stable gate for this is `python evals\run_cross_skill_schema_eval.py`. Use `--generate` for a standalone invocation that must first regenerate the page, research, and price fixtures; CI runs those prerequisite evals separately and omits the flag.

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
- M12 adapter matrix inventory and validation
- M13 deterministic real-world replay without live browser fallback
- M14 privacy scanner and expanded safety action coverage
- M15 site profile catalog validation and URL matching
- M16 CLI/text run review generation
- M17 local package dry-run validation
- M18-M19 sequential batch, rebuildable run index, and retry-plan generation
- M20 JSON/CSV/Markdown run exports
- M21 strict run/path identity, atomic finalization, capture schema/admission, HMAC continuation, wrapper ownership, privacy-retention, schema-drift, operations fail-closed, and reproducible package fixtures

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
