# M8 browser-research Provided-URL Capture MVP Closeout

## What Shipped

- M8 provided-URL capture orchestration for `browser-research`.
- `scripts/research_capture_runner.py` to:
  - accept a research question and approved source URLs or an M8 JSON spec
  - call existing browser capture adapters per source
  - write `capture/source-###/page_capture.json`
  - stage per-source screenshot evidence when declared
  - generate `capture/research-input.json`
  - run the existing `browser_research_runner.py`
  - post-process manifest and validation warnings for capture evidence
- Hardened browser-research validation for:
  - source directory/source ID agreement
  - failed source captures used as claim support
  - non-independent/syndicated sources incorrectly treated as independent support
- Synthetic M8 integration evals covering:
  - two-source supported claim
  - unsupported claim failure
  - single-source claim marked with `single_source=true`
  - syndicated/non-independent source handling
  - source capture failure partial run
  - prompt-injection text treated as source data
- CI updates for M8 compile, eval, schema, and validation gates.
- Manual smoke documentation for 3-source, 5-source, unavailable-source, and conflicting-metadata public research runs.

## Frozen Behavior

- M8 supports `browser-research` only.
- M8 accepts user-provided approved source URLs only.
- Default source count is 2-10 per run.
- Public URL capture uses the M6 adapter boundary.
- Current-browser captures are allowed only when already user-approved and task-scoped under M7 rules.
- The existing `browser_research_runner.py` remains the owner of claim ledger rendering, report output, source notes, CSV, source records, and claim coverage validation.
- If no claim ledger is provided, M8 creates an explicit unknown/no-synthesis ledger entry instead of inventing claims.
- Source capture failures remain auditable and produce partial or failed run status.
- Prompt-injection text remains page data.

## Tests / Gates

Passed during closeout:

- `python -m py_compile scripts\page_to_md_runner.py scripts\capture\playwright_mcp_capture.py scripts\capture\page_to_md_browser_runner.py scripts\capture\current_chrome_capture.py scripts\capture\current_chrome_page_to_md_runner.py scripts\research_capture_runner.py scripts\markdown\render_page_md.py scripts\validation\validate_page_to_md.py scripts\validation\validate_page_capture.py scripts\validation\validate_json_schema.py scripts\validation\classify_browser_action.py scripts\validation\validate_browser_research.py scripts\validation\validate_price_compare.py scripts\inward_eyes\__init__.py scripts\inward_eyes\capture.py scripts\inward_eyes\html_extract.py scripts\inward_eyes\io.py scripts\inward_eyes\markdown.py scripts\inward_eyes\safety.py scripts\inward_eyes\validation.py scripts\inward_eyes\research.py scripts\inward_eyes\price.py scripts\browser_research_runner.py scripts\price_compare_runner.py evals\run_eval.py evals\run_safety_eval.py evals\run_research_eval.py evals\run_research_capture_eval.py evals\run_price_eval.py evals\run_capture_adapter_eval.py evals\run_cross_skill_schema_eval.py`
- `python evals\run_eval.py`
- `python evals\run_safety_eval.py`
- `python evals\run_research_eval.py`
- `python evals\run_research_capture_eval.py`
- `python evals\run_price_eval.py`
- `python evals\run_capture_adapter_eval.py`
- `python evals\run_cross_skill_schema_eval.py`
- `python scripts\validation\validate_json_schema.py --schema schemas\research_report.schema.json --json evals\.tmp\research-capture\eval-two-source-supported\artifacts\claims.json`
- `python scripts\validation\validate_json_schema.py --schema schemas\run_manifest.schema.json --json evals\.tmp\research-capture\eval-two-source-supported\manifest.json`
- `python scripts\validation\validate_json_schema.py --schema schemas\validation_report.schema.json --json evals\.tmp\research-capture\eval-two-source-supported\validation\claim-coverage-report.json`
- Existing browser-research, page-to-md, and price schema checks for generated eval artifacts.
- `python scripts\validation\validate_browser_research.py evals\.tmp\research-capture\eval-two-source-supported`
- `python scripts\validation\validate_browser_research.py evals\.tmp\browser-research\eval-evidence-backed-research`
- `python scripts\validation\validate_price_compare.py evals\.tmp\price-compare\eval-product-quotes`
- `python C:\Users\62406\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py "E:\Inward Eyes"`
- `git diff --check`

`git diff --check` exited 0 and reported only Git line-ending normalization warnings for touched Markdown files.

## Known Limitations

- Live browser capture remains environment-dependent.
- M8 does not perform automatic source discovery or web search.
- M8 does not follow related links, pagination, or search result pages.
- M8 does not synthesize claims from source text; it requires an explicit claim ledger or emits an unknown/no-synthesis ledger entry.
- The synthetic evals use provided source text and do not prove real-world extraction quality.
- Current-browser source capture remains constrained by M7 current-page approval and privacy rules.

## Deferred Work

- M10: automatic source discovery/search.
- Multi-hop browsing and result-page collection.
- Source quality ranking and deduplication beyond explicit independence metadata.
- Browser-backed claim drafting or assisted claim extraction.
- `price-compare` browser capture and ecommerce quote extraction.
