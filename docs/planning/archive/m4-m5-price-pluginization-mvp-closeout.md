# M4-M5 price-compare and Pluginization MVP Closeout

## What Shipped

- `price-compare` skill.
- Local `price_compare_runner.py`.
- Price comparison and price record schemas.
- Candidate discovery and quote extraction records.
- Price CSV, Markdown report, anomalies report, and deterministic PNG chart rendering.
- One source record per quote.
- Product-page screenshot policy enforcement.
- Price validation CLI.
- Synthetic pass, low-confidence exclusion, and missing-screenshot fail evals.
- Local plugin manifest update to version `0.2.0`.
- Pluginization reference doc and example input files.
- GitHub Actions CI for repository-contained compile, eval, schema, and validator checks.

## Frozen Behavior

- `price-compare` consumes local price input JSON.
- Product identity and specs remain separate.
- List price, sale price, coupon price, shipping fee, and estimated total remain separate.
- Low-confidence, incomplete-spec, out-of-stock, unknown-total, cart/checkout/coupon-claim, and address-change quotes are excluded from final lowest-price conclusions.
- Product-page screenshots are required by policy; missing screenshots fail validation.
- The plugin stays read-only and avoids write-like capability claims.

## Tests / Gates

Passed before closeout:

- Full Python compile check for page, research, price, validators, and evals.
- `python evals\run_eval.py`
- `python evals\run_safety_eval.py`
- `python evals\run_research_eval.py`
- `python evals\run_price_eval.py`
- Schema checks for page, research, price run, price record via `--pointer /quotes/0`, and manifests.
- `python scripts\validation\validate_price_compare.py evals\.tmp\price-compare\eval-product-quotes`
- `python C:\Users\62406\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py "E:\Inward Eyes"`
- `git diff --check`

## CI

Added `.github/workflows/ci.yml` for repository-contained checks. The CI intentionally does not run the local Codex plugin validator because that script lives under the developer machine's Codex skills directory, not inside this repository.

## Known Limitations

- No real browser, Chrome extension, Playwright, Chrome DevTools, Browser Use, Computer Use, or MCP adapter is implemented.
- No broad product discovery is implemented.
- No marketplace entry, install flow, or distribution package is created.
- Price chart rendering is intentionally minimal.
- The project still uses a minimal JSON schema validator rather than a full JSON Schema implementation.
- Eval fixtures remain synthetic.
