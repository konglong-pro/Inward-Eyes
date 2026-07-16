---
name: price-compare
description: Compare user-provided ecommerce product URLs with strict product/spec identity, separate price components, seller/region/currency/stock context, screenshot evidence, anomalies, and validation. Excludes broad product search, purchasing, account mutation, coupon claiming, cart, checkout, stealth browsing, proxies, and anti-bot bypass.
---

# price-compare

You compare ecommerce prices without collapsing product identity, specs, seller context, stock, shipping, coupon, and total price into one ambiguous number.

## Inputs

Accept one of:

- User-provided product URLs with a target product and required specs.
- Approved candidate discovery scope with target product, required specs, approved platforms/domains, caps, region/currency, and candidate records.
- Captured product page records prepared for Inward Eyes.
- Local price-compare input JSON.

Start with user-provided product URLs unless the user explicitly requests M10B approved candidate discovery with bounded platform/domain scope.

## Required Outputs

Create a run directory outside the plugin package:

- `input.json`
- `manifest.json`
- `artifacts/prices.json`
- `artifacts/prices.csv`
- `artifacts/price-report.md`
- `artifacts/anomalies.md`
- `artifacts/price-chart.png`
- `capture/source-###/page_capture.json` for each browser-captured quote
- `evidence/source-###/source_record.json` for each quote
- `evidence/source-###/screenshots/` for required product-page screenshots
- `validation/price-validation-report.json`

For M10B approved candidate discovery, also create:

- `artifacts/candidates.json`
- `artifacts/candidates.csv`
- `artifacts/candidate-review.md`
- `capture/candidate-search/`
- `validation/candidate-validation-report.json`
- `validation/warnings.md`

Candidate records do not replace M9 quote records, source records, product-page screenshots, or price validation reports. Missing product-page screenshots block complete included browser-captured quotes unless the quote is explicitly excluded and the run is partial.

## Procedure

1. Resolve scope without asking when possible:
   - If product URLs are provided, use only those URLs.
   - If required specs are provided, use them as the target identity.
   - If region or currency is omitted, use page-visible/default context and mark `region_source` or `currency_source`.
   - If output root is omitted, use `browser-operator-runs/` under the workspace.
   - Ask only when product identity is ambiguous, required specs are missing, multiple regions/currencies are possible, output root is not writable, or a Yellow action is required.
2. Classify browser actions with `docs/contracts/safety-contract.md`.
3. Provided URL candidate assessment:
   - For each provided URL or captured product record, extract product identity fields.
   - Do not search for additional candidates.
   - Gather product name, model number, specs, platform, seller, condition, URL, provisional price, and `match_confidence`.
   - Route low-confidence or incomplete spec matches to manual review.
4. Approved candidate discovery:
   - Use only when the user provides target product, required specs, approved platforms/domains, and candidate caps.
   - Record candidate product URLs, visible product names/specs, seller, condition, provisional visible price, match confidence, mismatch flags, and rationale.
   - Reject candidates outside scope, duplicate product URLs, recommendation links, recursive links, non-public URLs, or login-required discovery.
   - Route low-confidence, incomplete spec, seller-mismatched, and condition-mismatched candidates to manual review.
   - Pass candidates to quote extraction only when explicitly approved or when `auto_high_confidence` policy allows it.
5. Quote extraction:
   - Confirm selected specs.
   - Extract list price, sale price, coupon price, shipping fee, estimated total, stock, seller, region, currency, condition, URL, and timestamp.
   - Record `quote_context`, `quote_context_hash`, and `estimated_total.calculation`.
   - Capture screenshot evidence for product pages.
6. Keep product names and product specs separate.
7. Keep list price, sale price, coupon price, shipping fee, and estimated total separate.
8. Mark coupon, cart, checkout, membership, and address-change requirements explicitly.
9. Exclude low-confidence, incomplete-spec, out-of-stock, unknown-total, cart/checkout/coupon-claim, address-change, incompatible context, and manual-review-required quotes from final lowest-price conclusions.
10. Render CSV, Markdown report, anomalies, and chart from validated structured data.
11. Do not mark a run complete if validation fails.

Broad web product search, platform crawling, recommendation following, coupon claiming, cart, checkout, address/account mutation, login-required discovery, stealth, proxies, CAPTCHA handling, and anti-bot bypass remain out of scope.

## Quote Context

Every quote should include:

- `quote_context.platform`
- `quote_context.region`
- `quote_context.currency`
- `quote_context.seller_type`
- `quote_context.condition`
- `quote_context.selected_specs`
- `quote_context.membership_required`
- `quote_context.coupon_action_required`
- `quote_context.cart_required`
- `quote_context.checkout_required`
- `quote_context.shipping_known`
- `quote_context.stock_status`
- `quote_context_hash`

Lowest-price conclusions require the same product group, normalized required specs, compatible quote context, `match_confidence >= threshold`, `manual_review_required=false`, and `excluded_from_lowest_price=false`.

## Estimated Total

`estimated_total` must explain itself with `amount`, `currency`, `calculation`, `components`, `confidence`, and `warnings`. Do not treat page-visible "coupon price", "estimated total", "membership price", or "cart price" as interchangeable.

## Completion Status

Use `complete`, `partial`, `failed`, or `aborted_by_policy` consistently with the run manifest. Any quote requiring cart, checkout, coupon claiming, address change, missing screenshot evidence, or unsupported context must not produce a complete lowest-price conclusion.

## Hard Rules

- Never click purchase, cart, coupon-claim, checkout, payment, account, security, post, comment, like, follow, or message actions.
- If coupon price is directly visible, record it. If claiming is required, do not click; set `coupon_action_required=true`.
- If cart is required, do not add to cart; set `cart_required=true`.
- If checkout is required, do not proceed; set `checkout_required=true`.
- If address, region, or delivery context must change, stop unless explicitly approved.
- Never invent missing product specifications, seller, stock, shipping fee, estimated total, or price fields.
- Do not save cookies, tokens, HAR files, browser profiles, passwords, payment details, addresses, or unrelated private account data.

## Local Runner

When working from approved product URLs, use:

```bash
python scripts/price_capture_runner.py --input <m9-spec.json> --output-root <output-root>
```

When working from approved bounded candidate discovery scope, use:

```bash
python scripts/price_candidate_discovery_runner.py --input <m10b-candidate-discovery-spec.json> --output-root <output-root>
```

When working from a local price input JSON, use:

```bash
python scripts/price_compare_runner.py --input <path> --output-root <output-root>
```

Use the project root as the working directory.
