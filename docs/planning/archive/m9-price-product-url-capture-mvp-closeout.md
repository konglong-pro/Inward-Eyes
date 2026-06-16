# M9 Price Product URL Capture MVP Closeout

Date: 2026-06-16
Status: completed

## What Shipped

- Added `scripts/price_capture_runner.py` for approved product URL capture into the existing price-compare workflow.
- Added per-source product page capture output:
  - `capture/source-###/page_capture.json`
  - `evidence/source-###/source_record.json`
  - `evidence/source-###/screenshots/`
- Added generated local price input at `capture/price-input.json`.
- Reused `scripts/price_compare_runner.py` for `prices.json`, CSV, Markdown report, anomalies, chart, source records, manifest, and validation.
- Added M9 price capture fixtures and `evals/run_price_capture_eval.py`.
- Hardened price validation for candidate assessment method, quote context completeness, compatible eligible quote context, estimated-total explanation, source directory agreement, and manual-review status propagation.
- Updated CI, phase manifest, project status, active work doc, contracts, manual smoke test docs, and price-compare skill docs.

## Frozen Behavior

- M9 accepts only user-provided, approved ecommerce product URLs.
- Default batch size is 2-20 URLs.
- Candidate assessment is `provided_url_candidate_assessment`; no search or broad discovery is implemented.
- Product-page screenshot policy is required for browser-captured product URL quotes.
- Missing required product-page screenshot evidence fails validation.
- Product identity and selected specs remain separate from seller, stock, region, currency, and price fields.
- List price, sale price, coupon price, shipping fee, and estimated total remain separate.
- `quote_context`, `quote_context_hash`, and `estimated_total.calculation` are present in rendered price records.
- Coupon claim, cart, checkout, address-change, low-confidence, incomplete-spec, out-of-stock, unknown-total, and manual-review-required quotes cannot produce a complete lowest-price conclusion.
- Red browser actions are not performed; adapter policy aborts are preserved as `aborted_by_policy`.

## Tests And Gates Run

- `python -m py_compile scripts\page_to_md_runner.py scripts\capture\playwright_mcp_capture.py scripts\capture\page_to_md_browser_runner.py scripts\capture\current_chrome_capture.py scripts\capture\current_chrome_page_to_md_runner.py scripts\research_capture_runner.py scripts\price_capture_runner.py scripts\markdown\render_page_md.py scripts\validation\validate_page_to_md.py scripts\validation\validate_page_capture.py scripts\validation\validate_json_schema.py scripts\validation\classify_browser_action.py scripts\validation\validate_browser_research.py scripts\validation\validate_price_compare.py scripts\inward_eyes\__init__.py scripts\inward_eyes\capture.py scripts\inward_eyes\html_extract.py scripts\inward_eyes\io.py scripts\inward_eyes\markdown.py scripts\inward_eyes\safety.py scripts\inward_eyes\validation.py scripts\inward_eyes\research.py scripts\inward_eyes\price.py scripts\browser_research_runner.py scripts\price_compare_runner.py evals\run_eval.py evals\run_safety_eval.py evals\run_research_eval.py evals\run_research_capture_eval.py evals\run_price_eval.py evals\run_price_capture_eval.py evals\run_capture_adapter_eval.py evals\run_cross_skill_schema_eval.py`
- `python evals\run_eval.py`
- `python evals\run_safety_eval.py`
- `python evals\run_research_eval.py`
- `python evals\run_research_capture_eval.py`
- `python evals\run_price_eval.py`
- `python evals\run_price_capture_eval.py`
- `python evals\run_capture_adapter_eval.py`
- `python evals\run_cross_skill_schema_eval.py`
- `python scripts\validation\validate_json_schema.py --schema schemas\page_capture.schema.json --json evals\.tmp\price-capture\eval-two-matching-product-urls\capture\source-001\page_capture.json`
- `python scripts\validation\validate_json_schema.py --schema schemas\price_compare_run.schema.json --json evals\.tmp\price-capture\eval-two-matching-product-urls\artifacts\prices.json`
- `python scripts\validation\validate_json_schema.py --schema schemas\price_record.schema.json --json evals\.tmp\price-capture\eval-two-matching-product-urls\artifacts\prices.json --pointer /quotes/0`
- `python scripts\validation\validate_json_schema.py --schema schemas\run_manifest.schema.json --json evals\.tmp\price-capture\eval-two-matching-product-urls\manifest.json`
- `python scripts\validation\validate_json_schema.py --schema schemas\validation_report.schema.json --json evals\.tmp\price-capture\eval-two-matching-product-urls\validation\price-validation-report.json`
- `python scripts\validation\validate_price_compare.py evals\.tmp\price-capture\eval-two-matching-product-urls`
- `python C:\Users\62406\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py "E:\Inward Eyes"`
- `git diff --check`

`git diff --check` exited 0 with CRLF normalization warnings on edited Markdown files.

## Known Limitations

- M9 synthetic fixtures use user-provided structured quote fields and reviewed screenshot fixtures; they do not prove extraction accuracy on arbitrary real ecommerce pages.
- Public URL capture remains the default capture path. Logged-in/current-browser ecommerce capture is not broadened.
- Missing screenshots fail validation for included product-page quotes; excluding a missing-screenshot quote for a partial run remains a future refinement.
- Region and currency are validated as quote context, but site-specific region selectors and delivery-address workflows are not implemented.
- Real-world ecommerce anti-bot, CAPTCHA, unavailable pages, and dynamic variant UI behavior require manual smoke testing.

## Deferred Work

- Broad product discovery is deferred to M10 or later.
- Search-term price comparison is deferred.
- Cross-platform automatic same-product discovery is deferred.
- Site-specific ecommerce extraction profiles are deferred.
- Coupon claiming, add-to-cart price reveal, checkout shipping reveal, and address mutation remain prohibited by default.
