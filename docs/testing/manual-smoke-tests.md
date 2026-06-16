# Manual Smoke Tests

Real webpage content, screenshots, cookies, HAR files, and browser profiles must not be committed. Keep runtime outputs under ignored local directories such as `evals/.tmp/`.

## Smoke Test: current Chrome logged-in page

Use this only for local manual verification. Do not commit real logged-in page content, screenshots, copied visible text, cookies, tokens, HAR files, local storage, session storage, browser profiles, passwords, payment details, order data, inbox data, or private dashboard content.

Suggested safe procedure:

1. Open the target page in Chrome yourself and confirm the visible page is the only approved scope.
2. Capture only visible URL, visible page title, and a redacted/approved visible text excerpt or structured snapshot.
3. Save a screenshot only after privacy review/redaction policy is applied.
4. Run `python scripts\capture\current_chrome_page_to_md_runner.py --url <visible-url> --user-approved-current-page --page-title "<visible-title>" --selected-main-content-file <redacted-text-file> --screenshot <reviewed-screenshot> --screenshot-privacy-reviewed --login-state confirmed --requires-login --output-root <ignored-output-root> --run-id <run-id>`.
5. Validate with `python scripts\validation\validate_page_capture.py <run_dir>\capture\page_capture.json` and `python scripts\validation\validate_page_to_md.py <run_dir>`.
6. Record only high-level notes here: date, adapter command shape, run directory path under an ignored location, validation result, and warnings. Do not include content or screenshots.

## Smoke Test: browser-research provided URLs

Use this only for local manual verification. Do not commit copied webpage content, screenshots with private data, cookies, tokens, HAR files, browser profiles, passwords, payment details, or unrelated private data.

Suggested safe scenarios:

- 3-source public research run.
- 5-source public research run.
- One source unavailable.
- One source with conflicting metadata.

Suggested procedure:

1. Prepare a small JSON spec with the research question, approved source URLs, source titles or reviewed source text snippets, source independence notes, and a claim ledger.
2. Run `python scripts\research_capture_runner.py --input <spec.json> --output-root <ignored-output-root> --run-id <run-id>`.
3. Validate with `python scripts\validation\validate_browser_research.py <run_dir>`.
4. Record only high-level notes here: date, source count, command shape, ignored run directory, validation result, warnings, and whether any source failed. Do not include source content.

## Smoke Test: browser-research small-scope discovery

Use this only for local manual verification. Do not commit copied webpage content, screenshots with private data, cookies, tokens, HAR files, browser profiles, passwords, payment details, or unrelated private data.

Suggested safe scenarios:

- 3-source public discovery.
- 5-source public discovery.
- Conflicting public sources.
- Source unavailable.
- Source excluded by domain policy.

Suggested procedure:

1. Prepare a small JSON discovery spec with the research question, `max_sources`, allowed domains or allowed source types, excluded domains or source types when relevant, recency when relevant, search queries, candidate URLs, candidate title/snippet if available, and selection rationale for selected candidates.
2. Keep `max_sources` at 5 by default and never above 20.
3. Run `python scripts\research_discovery_runner.py --input <discovery-spec.json> --output-root <ignored-output-root> --run-id <run-id>`.
4. Validate with `python scripts\validation\validate_research_discovery.py <run_dir>` and `python scripts\validation\validate_browser_research.py <run_dir>`.
5. Record only high-level notes here: date, selected source count, rejected candidate count, command shape, ignored run directory, validation result, warnings, and whether any source failed. Do not include source content.

## Smoke Test: price-compare product URLs

Use this only for local manual verification. Do not commit real ecommerce screenshots containing personal account data, copied account-visible content, cookies, tokens, HAR files, browser profiles, passwords, payment details, addresses, order data, cart data, or checkout data.

Suggested safe scenarios:

- Public/simple product page.
- Product page with visible coupon price.
- Product page with unknown shipping.
- Product page with variant/spec ambiguity.

Suggested procedure:

1. Prepare a small JSON spec with the target product, required specs, approved product URLs, reviewed product-page text snippets, visible quote fields, and reviewed/redacted screenshot paths.
2. Run `python scripts\price_capture_runner.py --input <spec.json> --output-root <ignored-output-root> --run-id <run-id>`.
3. Validate with `python scripts\validation\validate_price_compare.py <run_dir>`.
4. Record only high-level notes here: date, product URL count, command shape, ignored run directory, validation result, warnings, and whether any quote was excluded. Do not include page content or screenshots.

## Smoke Test: price-compare approved candidate discovery

Use this only for local manual verification. Do not commit real ecommerce screenshots containing personal account data, copied account-visible content, cookies, tokens, HAR files, browser profiles, passwords, payment details, addresses, order data, cart data, or checkout data.

Suggested safe scenarios:

- One approved platform with 3 candidates.
- Two approved platforms with 5 total candidates.
- Spec mismatch.
- Duplicate or variant confusion.
- Suspiciously low price.

Suggested procedure:

1. Prepare a small JSON candidate discovery spec with `target_product`, `required_specs`, `allowed_platforms`, `allowed_domains`, `max_candidates_per_platform`, region, currency, candidate URLs, visible product names/specs, seller, condition, provisional visible price, match confidence, mismatch flags, and selection rationale.
2. Keep total candidates at or below 20. Use `approval_policy=review_only` unless automatic high-confidence handoff is explicitly intended.
3. Run `python scripts\price_candidate_discovery_runner.py --input <candidate-discovery-spec.json> --output-root <ignored-output-root> --run-id <run-id>`.
4. Validate candidate review with `python scripts\validation\validate_price_candidate_discovery.py <run_dir>`.
5. If quote extraction proceeds, validate with `python scripts\validation\validate_price_compare.py <run_dir>`.
6. Record only high-level notes here: date, platform count, candidate count, approved count, command shape, ignored run directory, validation result, warnings, and whether quote extraction proceeded. Do not include page content or screenshots.

## Smoke Test: public article

- Date: 2026-06-10
- URL: `https://blog.python.org/2024/10/python-3130-final-released/`
- Adapter: Playwright MCP via `@playwright/mcp` `0.0.76`; MCP server reported Playwright `1.61.0-alpha-1781023400000`; `msedge`, headless, isolated, no real browser profile.
- Run dir: capture `evals/.tmp/stable-smoke-public-article/capture-run/playwright-mcp-public-article/`; render `evals/.tmp/stable-smoke-public-article/render-run/playwright-mcp-public-article-render/`
- Result: pass; adapter wrote `capture/page_capture.json`; `page_to_md_runner.py --input <capture/page_capture.json>` rendered page artifacts without browser logic.
- Validation: `page_capture.schema.json`, `validate_page_capture.py`, render `validate_page_to_md.py`, capture/render `run_manifest.schema.json`, and capture/render `validation_report.schema.json` passed.
- Warnings: none.
- Human notes: Public, unauthenticated article. Browser actions were `browser_navigate`, `browser_snapshot`, `browser_evaluate`, and `browser_close`. Screenshots were not required and none were saved. No HAR, cookies, tokens, or browser profiles were intentionally saved.

## Smoke Test: public docs

- Date: 2026-06-10
- URL: `https://docs.python.org/3/library/json.html`
- Adapter: Playwright MCP via `@playwright/mcp` `0.0.76`; MCP server reported Playwright `1.61.0-alpha-1781023400000`; `msedge`, headless, isolated, no real browser profile.
- Run dir: capture `evals/.tmp/m6-playwright-mcp-smoke-real/capture-run/playwright-mcp-python-json/`; render `evals/.tmp/m6-playwright-mcp-smoke-real/render-run/playwright-mcp-python-json-render/`
- Result: pass; adapter wrote `capture/page_capture.json`; `page_to_md_runner.py --input <capture/page_capture.json>` rendered page artifacts without browser logic.
- Validation: `page_capture.schema.json`, `validate_page_capture.py`, render `validate_page_to_md.py`, capture/render `run_manifest.schema.json`, and capture/render `validation_report.schema.json` passed.
- Warnings: render validation reported non-blocking `possible_boilerplate:recommended`.
- Human notes: Public, unauthenticated docs page. Browser actions were `browser_navigate`, `browser_snapshot`, `browser_evaluate`, and `browser_close`. Screenshots were not required and none were saved. No HAR, cookies, tokens, or browser profiles were intentionally saved. MCP title text had a local encoding anomaly around em dashes; the capture preserved the observed title rather than inventing a correction.
