# M9 Price Product URL Capture MVP

Status: completed
Last updated: 2026-06-16

## Goal

Add browser-backed quote capture for user-provided ecommerce product URLs only.

The workflow is:

```text
approved product URLs
  -> capture/source-###/page_capture.json
  -> capture/price-input.json
  -> price_compare_runner.py
  -> validated price-compare artifacts
```

`price_compare_runner.py` remains the source of truth for `prices.json`, CSV, Markdown report, anomalies, chart rendering, source records, and validation.

## Scope

- User-provided product URLs only.
- Default batch size: 2-20 URLs.
- Product page capture only.
- Public URL capture first.
- One `page_capture.json` and one `SourceRecord` per source.
- Product-page screenshots are required by policy.
- Missing screenshot evidence fails validation for included product-page quotes.
- Product identity and selected specs remain separate.
- List price, sale price, coupon price, shipping fee, and estimated total remain separate.
- Candidate assessment is `provided_url_candidate_assessment`.

## Out Of Scope

- Search-term price comparison.
- Platform search or keyword search.
- Broad product discovery.
- Following recommendation links.
- Automatic same-product discovery across platforms.
- Coupon claiming.
- Adding to cart.
- Checkout.
- Address or region mutation without explicit Yellow-action approval.
- Stealth browsing, proxies, anti-bot bypass, CAPTCHA handling, or access-control bypass.
- Saving cookies, tokens, HAR, browser profiles, passwords, payment details, or unrelated account data.

## Implementation

- `scripts/price_capture_runner.py` accepts a target product, required specs, approved product URLs, optional region/currency constraints, and an output root.
- Each source URL is captured through the existing public URL capture adapter into `capture/source-###/page_capture.json`.
- Reviewed screenshots are staged into `evidence/source-###/screenshots/` and manifest evidence entries include `sha256`.
- The runner generates `capture/price-input.json` and invokes `scripts/price_compare_runner.py`.
- Existing price artifacts are preserved:
  - `artifacts/prices.json`
  - `artifacts/prices.csv`
  - `artifacts/price-report.md`
  - `artifacts/anomalies.md`
  - `artifacts/price-chart.png`
  - `validation/price-validation-report.json`

## Validation

M9 hardens price validation so that:

- every quote has URL, access time, platform, region, currency, seller, product specs, source record path, and screenshot policy;
- product-page screenshots are required;
- missing required screenshots fail validation;
- low-confidence, incomplete-spec, out-of-stock, unknown-total, cart, checkout, coupon-claim, address-change, and manual-review-required quotes are excluded from lowest-price conclusions by the price model;
- eligible lowest-price quotes must match the comparison region, currency, and required specs;
- `quote_context` and `quote_context_hash` must exist;
- `estimated_total` must expose calculation basis, components, confidence, and warnings.

## Output Shape

```text
<run_dir>/
  input.json
  manifest.json
  capture/
    price-input.json
    source-001/page_capture.json
    source-002/page_capture.json
  artifacts/
    prices.json
    prices.csv
    price-report.md
    anomalies.md
    price-chart.png
  evidence/
    source-001/source_record.json
    source-001/screenshots/
    source-002/source_record.json
    source-002/screenshots/
  validation/
    price-validation-report.json
    warnings.md
```

## Synthetic Fixtures

`evals/run_price_capture_eval.py` covers:

- two matching product URLs;
- low-confidence spec mismatch;
- coupon action required;
- cart required;
- missing shipping fee;
- missing screenshot failure;
- out-of-stock quote exclusion;
- different region manual review.

## Closeout

Closeout is recorded in `docs/planning/archive/m9-price-product-url-capture-mvp-closeout.md`.
