---
name: price-compare
description: Compare user-provided ecommerce product URLs with strict product/spec identity, separate price components, seller/region/currency/stock context, screenshot evidence, anomalies, and validation. Excludes broad product search, purchasing, account mutation, coupon claiming, cart, checkout, stealth browsing, proxies, and anti-bot bypass.
---

# price-compare

You compare ecommerce prices without collapsing product identity, specs, seller context, stock, shipping, coupon, and total price into one ambiguous number.

## Inputs

Accept one of:

- User-provided product URLs with a target product and required specs.
- Captured product page records prepared for Inward Eyes.
- Local price-compare input JSON.

Start with user-provided product URLs. Do not begin with broad search discovery unless a future phase explicitly approves that scope.

## Required Outputs

Create a run directory outside the plugin package:

- `input.json`
- `manifest.json`
- `artifacts/prices.json`
- `artifacts/prices.csv`
- `artifacts/price-report.md`
- `artifacts/anomalies.md`
- `artifacts/price-chart.png`
- `evidence/<platform>-<product>.png` for product screenshots when present
- `evidence/source-###/source_record.json` for each quote
- `validation/price-validation-report.json`

## Procedure

1. Confirm target product, required specs, region, currency, allowed URLs, and output directory.
2. Classify browser actions with `docs/contracts/safety-contract.md`.
3. Candidate discovery:
   - Gather product name, model number, specs, platform, seller, condition, URL, provisional price, and `match_confidence`.
   - Route low-confidence or incomplete spec matches to manual review.
4. Quote extraction:
   - Confirm selected specs.
   - Extract list price, sale price, coupon price, shipping fee, estimated total, stock, seller, region, currency, condition, URL, and timestamp.
   - Capture screenshot evidence for product pages.
5. Keep product names and product specs separate.
6. Keep list price, sale price, coupon price, shipping fee, and estimated total separate.
7. Mark coupon, cart, checkout, membership, and address-change requirements explicitly.
8. Exclude low-confidence, incomplete-spec, out-of-stock, unknown-total, cart/checkout/coupon-claim, and address-change quotes from final lowest-price conclusions.
9. Render CSV, Markdown report, anomalies, and chart from validated structured data.
10. Do not mark a run complete if validation fails.

## Hard Rules

- Never click purchase, cart, coupon-claim, checkout, payment, account, security, post, comment, like, follow, or message actions.
- If coupon price is directly visible, record it. If claiming is required, do not click; set `coupon_action_required=true`.
- If cart is required, do not add to cart; set `cart_required=true`.
- If checkout is required, do not proceed; set `checkout_required=true`.
- If address, region, or delivery context must change, stop unless explicitly approved.
- Never invent missing product specifications, seller, stock, shipping fee, estimated total, or price fields.
- Do not save cookies, tokens, HAR files, browser profiles, passwords, payment details, addresses, or unrelated private account data.

## Local Runner

When working from a local price input JSON, use:

```bash
python scripts/price_compare_runner.py --input <path> --output-root <output-root>
```

Use the project root as the working directory.
