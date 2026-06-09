---
doc_type: phase_plan
phase_id: m3_m5_research_price_pluginization
title: browser-research, price-compare, and pluginization
status: next
canonical: true
related_contracts:
  - docs/contracts/evidence-contract.md
  - docs/contracts/browser-operation-contract.md
  - docs/contracts/schemas-and-validation-contract.md
  - docs/contracts/safety-contract.md
related_adrs:
  - docs/adr/0001-evidence-first-browser-workflows.md
---

# M3-M5 browser-research, price-compare, and Pluginization

## Status

Next. Do not implement until M0-M2 closes or the user explicitly reprioritizes.

## Milestone 3: browser-research

### Goal

Produce source-backed research reports where every key fact maps to a claim ledger entry and source evidence.

### Required Outputs

```text
artifacts/
  report.md
  claims.json
  sources.csv
  source_notes.md
evidence/
  source-001/
    screenshot.png
    source_record.json
validation/
  claim-coverage-report.json
  missing-sources.md
manifest.json
```

### Claim Rules

- Every key fact must have one or more source IDs.
- Claims must be typed as `fact`, `inference`, or `unknown`.
- Direct source support and inferred support are different.
- Unknowns must be listed explicitly.
- Comments, ads, recommendations, and marketing copy are not factual sources by default.
- Reposted/syndicated copies do not count as independent confirmation without note.

### Acceptance Criteria

- `claims.json`, `sources.csv`, and `report.md` agree.
- Every source has URL, title, accessed time, source type, and evidence status.
- Single-source findings are marked.
- Unsupported claims fail validation.

## Milestone 4: price-compare

### Goal

Compare ecommerce prices while preventing product/spec mismatch.

### First Scope

Start with user-provided product URLs. Do not begin with broad search discovery.

### Two-Step Workflow

1. Candidate discovery:
   - Gather candidate product identity fields.
   - Extract specs, seller, condition, platform, URL, and provisional price.
   - Assign `match_confidence`.
   - Route low-confidence items to manual review.

2. Quote extraction:
   - Confirm selected specs.
   - Confirm region/delivery context.
   - Extract list price, sale price, coupon price, shipping fee, estimated total, stock, seller, and timestamp.
   - Capture screenshot evidence.
   - Validate price fields.

### Required Outputs

```text
artifacts/
  prices.json
  prices.csv
  price-report.md
  anomalies.md
  price-chart.png
evidence/
  <platform>-<product>.png
validation/
  price-validation-report.json
manifest.json
```

### Price Rules

- Product specs must remain separate from product names.
- Region, currency, seller, condition, and stock are required.
- Coupon price is not the same as sale price.
- Shipping fee is not the same as estimated total.
- Coupon claiming, cart, and checkout are Red actions by default.
- If final price requires account mutation, record the limitation and require manual review.

### Anomaly Rules

Flag:

- Incomplete spec match.
- Suspiciously low price.
- Third-party seller vs official seller.
- Out of stock with visible price.
- Unknown shipping fee.
- Coupon action required.
- Region mismatch.
- Product page redirect or expiry.

## Milestone 5: Pluginization

### Goal

Package stable skills into an installable Codex plugin.

### Planned Plugin Contents

- `page-to-md`
- `browser-research`
- `price-compare`
- Shared schemas.
- Deterministic scripts.
- Safety and routing references.
- Optional MCP dependency documentation.
- Examples.
- Local marketplace entry if needed.

### Manifest Guidance

First plugin manifest should be conservative:

- `name`: `inward-eyes`
- `description`: evidence-backed browser workflows for Codex
- `skills`: `./skills/`
- Avoid write-like capability claims in first release.
- Treat MCP dependencies as optional until versioning and approval behavior are tested.

### Distribution

Use a local or repo-scoped Codex marketplace only after the plugin package is stable. Workspace sharing can come later.

## Deferred Work

- Browser Use cloud backend.
- Site-specific ecommerce profiles.
- Large-scale monitoring.
- Network log capture.
- Automated coupon/cart/checkout workflows.
- Private data export workflows.
