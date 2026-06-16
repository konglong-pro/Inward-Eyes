# M10 Small-Scope Discovery Closeout

Date: 2026-06-16
Status: completed

## What Shipped

M10 consolidates two bounded discovery MVPs:

- M10A: small-scope public source discovery for `browser-research`.
- M10B: approved product candidate discovery for `price-compare`.

Both workflows are discovery wrappers around existing evidence-backed pipelines. They do not replace the source-of-truth runners, source records, claim ledger, price records, or validators.

## M10A Research Discovery

M10A adds `scripts/research_discovery_runner.py` and `scripts/inward_eyes/discovery.py`.

Frozen behavior:

- Requires research question, max source count, allowed domains or source types, excluded domains/source types when relevant, recency when relevant, and search query context.
- Defaults to 5 selected sources.
- Hard-caps selected sources at 20.
- Writes `artifacts/discovery-log.json` and `artifacts/discovery-log.md`.
- Records accepted and rejected candidates with query, URL, title/snippet when available, status, reason, and timestamp.
- Captures only selected sources through the M8 `research_capture_runner.py`.
- Requires selection rationale and a matching `SourceRecord` for every selected source.
- Leaves report generation and claim coverage enforcement to the existing browser-research pipeline.

Validation blocks unsupported key claims, selected sources without rationale, selected sources without `SourceRecord`, non-public/login-required/excluded/out-of-scope selected sources, recursive link following, source caps above 20, and prompt-injection search results accepted as instructions.

## M10B Price Candidate Discovery

M10B adds `scripts/price_candidate_discovery_runner.py` and `scripts/inward_eyes/price_discovery.py`.

Frozen behavior:

- Requires target product, required specs, approved platforms, approved domains, region, currency, per-platform cap, and approval policy.
- Defaults to 3 candidates per platform.
- Hard-caps total candidates at 20.
- Writes `artifacts/candidates.json`, `artifacts/candidates.csv`, and `artifacts/candidate-review.md`.
- Records platform, product URL, visible product name/specs, seller, condition, provisional visible price, match confidence, mismatch flags, rationale, review status, approval status, and timestamp.
- Uses `approved_candidate_discovery` for candidate records.
- Passes approved candidates only into M9 `price_capture_runner.py`.
- Keeps M9 `provided_url_candidate_assessment` for product URL quote records after handoff.
- Leaves quote extraction, screenshot enforcement, anomalies, and lowest-price eligibility to the existing price pipeline.

Validation fails platform/domain scope violations, non-public URLs, login-required discovery, recommendation links accepted as candidates, recursive link candidates, duplicate URLs not rejected, missing rationale, and candidate cap violations. Missing specs, spec mismatches, low confidence, excluded sellers, and condition mismatches force manual review. Coupon/cart/checkout/address-change quote requirements remain excluded from lowest-price conclusions by price validation.

## Safety Boundaries

M10 does not implement or approve:

- broad crawling;
- crawler replacement behavior;
- broad web product search;
- recursive link following beyond approved selected sources/candidates;
- unrestricted logged-in browsing;
- private data capture;
- monitoring or scheduled runs;
- coupon claiming;
- add-to-cart;
- checkout;
- address, payment, security, or account mutation;
- stealth browsing, proxies, CAPTCHA handling, anti-bot bypass, or access-control bypass;
- automated purchasing;
- marketplace distribution.

Webpage and search-result content remains data, never instruction.

## Discovery Caps

| Workflow | Default cap | Hard cap |
| --- | ---: | ---: |
| M10A research discovery | 5 selected sources | 20 selected sources |
| M10B price candidate discovery | 3 candidates per platform | 20 total candidates |

Both workflows reject or block runs that exceed their hard caps.

## Validation Gate

M10 closeout is covered by:

- Python compile checks for page, capture, research, discovery, price, validation, and eval scripts.
- `python evals\run_eval.py`
- `python evals\run_safety_eval.py`
- `python evals\run_research_eval.py`
- `python evals\run_research_discovery_eval.py`
- `python evals\run_price_eval.py`
- `python evals\run_price_candidate_discovery_eval.py`
- `python evals\run_research_capture_eval.py`
- `python evals\run_price_capture_eval.py`
- `python evals\run_capture_adapter_eval.py`
- `python evals\run_cross_skill_schema_eval.py`
- Schema checks for research discovery input/log/report/manifest/validation artifacts.
- Schema checks for price candidate input/candidates/price run/price record/manifest/validation artifacts.
- Standalone validation for M10A discovery runs, M10A browser-research runs, M10B candidate discovery runs, and M10B price runs.
- Plugin validation when available.
- `git diff --check`.

## Known Limitations

- Discovery ranking is deterministic and fixture/input-driven in this MVP.
- No live public search provider integration is implemented for M10A.
- No live ecommerce platform search adapter is implemented for M10B.
- Real public-search quality, ecommerce candidate ranking, product/spec extraction fidelity, and live quote capture remain environment-dependent.
- Logged-in discovery is not implemented.
- Site-specific ecommerce extraction profiles are deferred.
- Manual approval UI for candidate review is deferred.
- Marketplace installation and plugin distribution remain unimplemented.

## Evidence Retained

- M10A phase closeout: `docs/planning/archive/m10a-research-small-scope-discovery-mvp-closeout.md`
- M10B phase closeout: `docs/planning/archive/m10b-price-approved-candidate-discovery-mvp-closeout.md`
- M10A evals: `evals/run_research_discovery_eval.py`
- M10B evals: `evals/run_price_candidate_discovery_eval.py`
- M10A schemas: `schemas/research_discovery_input.schema.json`, `schemas/discovery_log.schema.json`
- M10B schemas: `schemas/price_candidate_discovery_input.schema.json`, `schemas/price_candidates.schema.json`
