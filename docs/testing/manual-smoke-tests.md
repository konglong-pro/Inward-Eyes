# Manual Smoke Tests

Real webpage content, screenshots, cookies, HAR files, and browser profiles must not be committed. Keep runtime outputs under ignored local directories such as `evals/.tmp/`.

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
