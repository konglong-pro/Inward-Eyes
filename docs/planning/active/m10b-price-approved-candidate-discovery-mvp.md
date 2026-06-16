---
doc_type: phase_plan
phase_id: m10b_price_approved_candidate_discovery_mvp
title: price-compare approved candidate discovery MVP
status: completed
canonical: true
related_contracts:
  - docs/contracts/browser-operation-contract.md
  - docs/contracts/evidence-contract.md
  - docs/contracts/schemas-and-validation-contract.md
  - docs/contracts/safety-contract.md
related_adrs:
  - docs/adr/0001-evidence-first-browser-workflows.md
closeout: docs/planning/archive/m10b-price-approved-candidate-discovery-mvp-closeout.md
---

# M10B price-compare Approved Candidate Discovery MVP

## Goal

Add a small, bounded, user-approved product candidate discovery workflow for `price-compare`.

M10B may search within explicitly approved ecommerce platforms/domains, collect candidate product URLs, assess product/spec match, and pass only approved candidates into the existing M9 quote capture pipeline. The existing price-compare runner and validator remain the source of truth for quotes, lowest-price eligibility, anomalies, and product-page screenshot enforcement.

## Scope

- User-provided product target and required specs are mandatory.
- User-approved platforms and domains are mandatory.
- Region and currency are mandatory for this MVP.
- Default maximum candidates per platform: 3.
- Hard maximum total candidates: 20.
- Candidate discovery only; quote extraction uses the existing M9 product URL flow.
- Product identity and specs must remain separate.
- Low-confidence, incomplete, seller-mismatched, or condition-mismatched candidates go to manual review.
- Quote extraction proceeds automatically only for high-confidence candidates when policy allows it.
- No candidate enters lowest-price conclusions unless quote validation passes.
- Product-page screenshots remain required for captured quotes.

## Interfaces Touched

- `scripts/price_candidate_discovery_runner.py`: bounded candidate discovery orchestration and M9 handoff.
- `scripts/inward_eyes/price_discovery.py`: candidate normalization, review rendering, policy checks, and candidate validation.
- `scripts/validation/validate_price_candidate_discovery.py`: standalone candidate discovery run validation.
- `scripts/inward_eyes/validation.py`: price validation includes candidate checks when `artifacts/candidates.json` exists.
- `schemas/price_candidate_discovery_input.schema.json`: scoped M10B input shape.
- `schemas/price_candidates.schema.json`: candidate artifact shape.
- `evals/run_price_candidate_discovery_eval.py`: synthetic M10B coverage.

M9 wording stays `provided_url_candidate_assessment`. The `approved_candidate_discovery` assessment method is only for M10B candidate records.

## Output Shape

```text
<run_dir>/
  input.json
  manifest.json
  artifacts/
    candidates.json
    candidates.csv
    candidate-review.md
    prices.json
    prices.csv
    price-report.md
    anomalies.md
    price-chart.png
  capture/
    candidate-search/
    approved-candidates-price-input.json
    source-001/page_capture.json
  evidence/
    source-001/source_record.json
    source-001/screenshots/
  validation/
    candidate-validation-report.json
    price-validation-report.json
    warnings.md
```

Price artifacts, quote capture directories, and source evidence exist only when quote extraction proceeds. Candidate-only review runs stop after `candidate-review.md` and `candidate-validation-report.json`.

## Candidate Requirements

Each candidate record must include:

- platform;
- product URL;
- visible product name;
- visible specs;
- seller;
- condition;
- provisional price when visible;
- match confidence;
- mismatch flags;
- selection, rejection, approval, or review rationale;
- `requires_manual_review`;
- `approved_for_quote_capture`;
- timestamp;
- assessment method.

## Approval Gate

M10B supports two approval policies:

- `review_only`: write `candidate-review.md` and stop unless candidates were explicitly approved in the input.
- `auto_high_confidence`: automatically pass only high-confidence candidates with required specs, allowed platform/domain, selection rationale, and no manual-review flags.

Rejected candidates are never sent to M9 quote capture. Low-confidence or incomplete candidates are sent to quote capture only when explicitly approved and still remain subject to M9 price validation.

## Out of Scope

- Broad web product search.
- Unlimited platform crawling.
- Marketplace-wide monitoring.
- Recursive link following.
- Recommendation carousel following.
- Coupon claiming.
- Add-to-cart.
- Checkout.
- Address mutation.
- Login-required discovery unless explicitly approved in a later phase.
- Stealth browsing.
- Proxies.
- CAPTCHA or anti-bot bypass.

## Validation

M10B validation must fail when:

- target product is missing;
- required specs are missing;
- approved platforms or domains are missing;
- region or currency is missing;
- total candidates exceed 20;
- per-platform candidate cap is exceeded;
- a candidate is outside allowed platform/domain scope;
- a candidate URL is non-public or login-required;
- a recommendation link is accepted;
- recursive link following is recorded;
- duplicate product URLs are not rejected;
- a non-rejected candidate has no rationale.

M10B validation must route candidates to manual review when:

- required specs are missing from the visible candidate record;
- required specs conflict with visible specs;
- match confidence is below the price threshold;
- seller is excluded;
- condition conflicts with policy;
- explicit approval is required.

M9/M4 price validation must still enforce screenshot evidence, coupon/cart/checkout/address-change exclusions, stock/region/currency/spec compatibility, and lowest-price eligibility.

## Tests / Gates

- `python -m py_compile scripts\price_candidate_discovery_runner.py scripts\validation\validate_price_candidate_discovery.py scripts\inward_eyes\price_discovery.py scripts\inward_eyes\validation.py evals\run_price_candidate_discovery_eval.py`
- `python evals\run_eval.py`
- `python evals\run_safety_eval.py`
- `python evals\run_research_eval.py`
- `python evals\run_price_eval.py`
- `python evals\run_research_discovery_eval.py`
- `python evals\run_price_candidate_discovery_eval.py`
- Candidate schema checks:
  - `python scripts\validation\validate_json_schema.py --schema schemas\price_candidate_discovery_input.schema.json --json evals\.tmp\price-candidate-discovery\eval-matching-candidates-within-cap\input.json`
  - `python scripts\validation\validate_json_schema.py --schema schemas\price_candidates.schema.json --json evals\.tmp\price-candidate-discovery\eval-matching-candidates-within-cap\artifacts\candidates.json`
- Existing price compare run, price record, manifest, and validation report schema checks.
- `python scripts\validation\validate_price_candidate_discovery.py evals\.tmp\price-candidate-discovery\eval-matching-candidates-within-cap`
- `python scripts\validation\validate_price_compare.py evals\.tmp\price-candidate-discovery\eval-matching-candidates-within-cap`
- `python C:\Users\62406\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py "E:\Inward Eyes"`
- `git diff --check`

## Closeout Requirements

- Create `docs/planning/archive/m10b-price-approved-candidate-discovery-mvp-closeout.md`.
- Record shipped behavior, frozen boundaries, eval coverage, gates run, known limitations, and deferred live platform discovery work.
