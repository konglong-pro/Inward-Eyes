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
