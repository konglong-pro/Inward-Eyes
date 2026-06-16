# M6 Browser Capture Adapter MVP Closeout

## What Shipped

- M6 `page-to-md` browser capture adapter boundary for one public article/docs URL.
- `scripts/capture/playwright_mcp_capture.py` for Playwright MCP observation-to-`page_capture.json` capture, with optional local Python Playwright capture when already available.
- `scripts/capture/page_to_md_browser_runner.py` wrapper for capture -> capture validation -> deterministic page-to-md rendering -> run validation.
- `scripts/inward_eyes/capture.py` capture interface helpers, prompt-injection text detection, private text redaction, screenshot policy handling, public URL checks, and capture-stage manifests.
- `scripts/validation/validate_page_capture.py` for M6 capture contract validation.
- Hardened `schemas/page_capture.schema.json` for real capture shape: required title, required content keys, structured assets, screenshot records, privacy, and screenshot policy.
- Screenshot evidence staging from `page_capture.assets.screenshots` into `evidence/screenshots/`, recorded in metadata, source record, manifest, and validation.
- Synthetic adapter contract evals covering valid capture, missing URL, missing title, no content payload, screenshot-required-but-missing, screenshot staging, non-public URL refusal, redacted private data, red action abort, wrapper execution, and prompt injection text as page data.
- Cross-skill shared schema reuse eval for `SourceRecord`, `RunManifest`, `ScreenshotPolicy`, `ManualReview`, and `ValidationReport`.
- Manual smoke test notes in `docs/testing/manual-smoke-tests.md`.
- CI updates for M6 compile and synthetic eval gates.

## Frozen Behavior

- M6 is an adapter-boundary MVP, not a completed browser operator.
- M6 supports only `page-to-md`.
- M6 supports only one user-provided public article/docs URL per run.
- Playwright MCP is the selected backend boundary.
- Browser capture remains optional and read-only by default.
- Local Python Playwright capture is optional; if unavailable or failing, the adapter writes an auditable failed run instead of installing dependencies or faking success.
- Existing `page_to_md_runner.py` remains the deterministic rendering layer and consumes `capture/page_capture.json` without browser-specific logic.
- Runtime outputs remain outside the plugin package.
- Screenshot evidence is staged only from declared capture assets and must be recorded under `evidence/screenshots/`.
- Red actions are refused; unapproved out-of-scope actions produce `aborted_by_policy` or failed/partial runs.

## Scope Kept Out

- `browser-research` discovery/capture.
- Ecommerce or price browsing.
- X/forum/thread capture.
- Infinite scroll.
- Logged-in pages.
- User Chrome profile attachment.
- Current-tab capture and browser history.
- Cookies, tokens, HAR files, browser profiles, passwords, payment data, and unrelated account data.
- Broad crawling.
- Stealth, proxies, anti-bot bypass, CAPTCHA handling.
- Marketplace distribution.
- Plugin hooks or default MCP enablement.

## Tests / Gates

Passed before closeout:

- Full Python compile check for page, research, price, capture adapter, validators, and evals.
- `python evals\run_eval.py`
- `python evals\run_safety_eval.py`
- `python evals\run_research_eval.py`
- `python evals\run_price_eval.py`
- `python evals\run_capture_adapter_eval.py`
- `python evals\run_cross_skill_schema_eval.py`
- `python scripts\validation\validate_json_schema.py --schema schemas\page_capture.schema.json --json evals\.tmp\capture-adapter\valid-capture\capture\page_capture.json`
- Schema checks for page metadata, page manifest, page validation report, research report, research manifest, research validation report, price run, price record via `--pointer /quotes/0`, price manifest, and price validation report.
- `python scripts\validation\validate_page_to_md.py evals\.tmp\page-to-md\eval-public-article`
- `python scripts\validation\validate_page_capture.py evals\.tmp\capture-adapter\valid-capture\capture\page_capture.json`
- `python scripts\validation\validate_browser_research.py evals\.tmp\browser-research\eval-evidence-backed-research`
- `python scripts\validation\validate_price_compare.py evals\.tmp\price-compare\eval-product-quotes`
- `python C:\Users\62406\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py "E:\Inward Eyes"`
- `git diff --check`

## CI

Updated `.github/workflows/ci.yml` for repository-contained M6 checks:

- Compile M6 capture scripts, validators, and evals.
- Run M6 synthetic capture adapter eval.
- Run cross-skill schema reuse eval.
- Validate generated M6 `page_capture.json` against `schemas/page_capture.schema.json`.

CI intentionally does not run live browser/network smoke tests or the local Codex plugin validator.

## Manual Smoke

Manual smoke notes are recorded in `docs/testing/manual-smoke-tests.md`.

Live browser smoke was not rerun during closeout. The closeout relies on repository-contained synthetic adapter evals plus previously recorded manual smoke notes. Future live smoke should remain local and should not commit webpage content, screenshots, cookies, HAR files, or browser profiles.

## Known Limitations

- M6 is not a stable browser operator.
- Live browser capture remains environment-dependent.
- Python Playwright is optional and not installed by the project.
- Playwright MCP is not bundled or enabled by default.
- The project still uses a minimal JSON schema validator plus contract-specific validators.
- Eval fixtures remain synthetic.
- M6 does not implement research discovery, price comparison, ecommerce capture, login-state capture, X/forum capture, infinite-scroll capture, crawling, hooks, marketplace distribution, or package distribution.
