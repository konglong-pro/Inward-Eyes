# M10B price-compare Approved Candidate Discovery MVP Closeout

Date: 2026-06-16
Status: completed

## What Shipped

- M10B approved candidate discovery orchestration for `price-compare`.
- `scripts/price_candidate_discovery_runner.py` to:
  - accept scoped product candidate discovery input;
  - enforce target product, required specs, approved platforms/domains, region, currency, per-platform cap, total candidate cap, excluded sellers, and approval policy;
  - write `artifacts/candidates.json`, `artifacts/candidates.csv`, and `artifacts/candidate-review.md`;
  - stop for review when no candidate is approved;
  - generate `capture/approved-candidates-price-input.json`;
  - run the existing M9 `price_capture_runner.py` for approved candidates;
  - preserve M9/M4 price validation as the quote and lowest-price source of truth.
- `scripts/inward_eyes/price_discovery.py` for candidate normalization, public URL checks, platform/domain scope checks, duplicate/recommendation rejection, review rendering, and candidate validation.
- `scripts/validation/validate_price_candidate_discovery.py` for standalone candidate run validation.
- Price validation now includes candidate discovery checks when `artifacts/candidates.json` exists.
- Schemas:
  - `schemas/price_candidate_discovery_input.schema.json`
  - `schemas/price_candidates.schema.json`
- Synthetic M10B eval coverage:
  - matching candidates within cap;
  - candidate outside allowed domain fails;
  - low-confidence spec mismatch excluded from automatic handoff;
  - duplicate product URL rejected;
  - recommendation link ignored;
  - candidate cap exceeded fails;
  - coupon-action quote excluded from lowest-price conclusion.
- CI, testing docs, contracts, phase docs, manual smoke docs, and `price-compare` skill docs updated.

## Frozen Behavior

- M10B is for `price-compare` only.
- Candidate discovery requires explicit user-approved task scope.
- Target product and required specs are mandatory.
- Approved platforms and domains are mandatory.
- Region and currency are mandatory for this MVP.
- Default maximum candidates per platform is 3.
- Hard maximum total candidates is 20.
- Candidate records use `approved_candidate_discovery`.
- M9 product URL quote records still use `provided_url_candidate_assessment`.
- Quote extraction proceeds automatically only for high-confidence candidates when `auto_high_confidence` policy allows it, or for explicitly approved candidates.
- Low-confidence, missing-spec, spec-mismatch, seller-mismatch, and condition-mismatch candidates require manual review.
- Rejected candidates remain in candidate artifacts with rejection rationale.
- Approved candidates are captured through the M9 product URL capture pipeline.
- Existing price validation continues to enforce screenshots, quote context, coupon/cart/checkout/address exclusions, and lowest-price eligibility.

## Contracts Updated

- `docs/contracts/browser-operation-contract.md`: M10B approved product candidate discovery boundary.
- `docs/contracts/evidence-contract.md`: candidate artifacts and M9 handoff evidence requirements.
- `docs/contracts/schemas-and-validation-contract.md`: candidate discovery schemas and validation rules.
- `docs/contracts/safety-contract.md`: M10B approval boundary and ecommerce prohibitions.

## Tests / Gates

Passed during closeout:

- `python -m py_compile scripts\page_to_md_runner.py scripts\capture\playwright_mcp_capture.py scripts\capture\page_to_md_browser_runner.py scripts\capture\current_chrome_capture.py scripts\capture\current_chrome_page_to_md_runner.py scripts\research_discovery_runner.py scripts\research_capture_runner.py scripts\price_candidate_discovery_runner.py scripts\price_capture_runner.py scripts\markdown\render_page_md.py scripts\validation\validate_page_to_md.py scripts\validation\validate_page_capture.py scripts\validation\validate_json_schema.py scripts\validation\classify_browser_action.py scripts\validation\validate_research_discovery.py scripts\validation\validate_browser_research.py scripts\validation\validate_price_candidate_discovery.py scripts\validation\validate_price_compare.py scripts\inward_eyes\__init__.py scripts\inward_eyes\capture.py scripts\inward_eyes\discovery.py scripts\inward_eyes\price_discovery.py scripts\inward_eyes\html_extract.py scripts\inward_eyes\io.py scripts\inward_eyes\markdown.py scripts\inward_eyes\safety.py scripts\inward_eyes\validation.py scripts\inward_eyes\research.py scripts\inward_eyes\price.py scripts\browser_research_runner.py scripts\price_compare_runner.py evals\run_eval.py evals\run_safety_eval.py evals\run_research_eval.py evals\run_research_discovery_eval.py evals\run_research_capture_eval.py evals\run_price_eval.py evals\run_price_candidate_discovery_eval.py evals\run_price_capture_eval.py evals\run_capture_adapter_eval.py evals\run_cross_skill_schema_eval.py`
- `python evals\run_eval.py`
- `python evals\run_safety_eval.py`
- `python evals\run_research_eval.py`
- `python evals\run_price_eval.py`
- `python evals\run_research_discovery_eval.py`
- `python evals\run_price_candidate_discovery_eval.py`
- `python evals\run_research_capture_eval.py`
- `python evals\run_price_capture_eval.py`
- `python evals\run_capture_adapter_eval.py`
- `python evals\run_cross_skill_schema_eval.py`
- `python scripts\validation\validate_json_schema.py --schema schemas\research_discovery_input.schema.json --json evals\.tmp\research-discovery\eval-bounded-three-sources\input.json`
- `python scripts\validation\validate_json_schema.py --schema schemas\discovery_log.schema.json --json evals\.tmp\research-discovery\eval-bounded-three-sources\artifacts\discovery-log.json`
- `python scripts\validation\validate_json_schema.py --schema schemas\research_report.schema.json --json evals\.tmp\research-discovery\eval-bounded-three-sources\artifacts\claims.json`
- `python scripts\validation\validate_json_schema.py --schema schemas\run_manifest.schema.json --json evals\.tmp\research-discovery\eval-bounded-three-sources\manifest.json`
- `python scripts\validation\validate_json_schema.py --schema schemas\validation_report.schema.json --json evals\.tmp\research-discovery\eval-bounded-three-sources\validation\discovery-validation-report.json`
- `python scripts\validation\validate_json_schema.py --schema schemas\validation_report.schema.json --json evals\.tmp\research-discovery\eval-bounded-three-sources\validation\claim-coverage-report.json`
- `python scripts\validation\validate_json_schema.py --schema schemas\price_candidate_discovery_input.schema.json --json evals\.tmp\price-candidate-discovery\eval-matching-candidates-within-cap\input.json`
- `python scripts\validation\validate_json_schema.py --schema schemas\price_candidates.schema.json --json evals\.tmp\price-candidate-discovery\eval-matching-candidates-within-cap\artifacts\candidates.json`
- `python scripts\validation\validate_json_schema.py --schema schemas\price_compare_run.schema.json --json evals\.tmp\price-candidate-discovery\eval-matching-candidates-within-cap\artifacts\prices.json`
- `python scripts\validation\validate_json_schema.py --schema schemas\price_record.schema.json --json evals\.tmp\price-candidate-discovery\eval-matching-candidates-within-cap\artifacts\prices.json --pointer /quotes/0`
- `python scripts\validation\validate_json_schema.py --schema schemas\run_manifest.schema.json --json evals\.tmp\price-candidate-discovery\eval-matching-candidates-within-cap\manifest.json`
- `python scripts\validation\validate_json_schema.py --schema schemas\validation_report.schema.json --json evals\.tmp\price-candidate-discovery\eval-matching-candidates-within-cap\validation\candidate-validation-report.json`
- `python scripts\validation\validate_json_schema.py --schema schemas\validation_report.schema.json --json evals\.tmp\price-candidate-discovery\eval-matching-candidates-within-cap\validation\price-validation-report.json`
- `python scripts\validation\validate_research_discovery.py evals\.tmp\research-discovery\eval-bounded-three-sources`
- `python scripts\validation\validate_browser_research.py evals\.tmp\research-discovery\eval-bounded-three-sources`
- `python scripts\validation\validate_price_candidate_discovery.py evals\.tmp\price-candidate-discovery\eval-matching-candidates-within-cap`
- `python scripts\validation\validate_price_compare.py evals\.tmp\price-candidate-discovery\eval-matching-candidates-within-cap`
- `python scripts\validation\validate_price_compare.py evals\.tmp\price-candidate-discovery\eval-coupon-action-required-excluded`
- `python C:\Users\62406\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py "E:\Inward Eyes"`
- `git diff --check`

`git diff --check` exited 0 and reported only Git line-ending normalization warnings on touched Markdown files.

## Known Limitations

- Candidate discovery ranking is deterministic and fixture/input-driven in this MVP; it does not implement a live platform search adapter.
- Real ecommerce search quality, product ranking, and visible spec fidelity remain unproven beyond synthetic fixtures.
- M10B does not perform login-required discovery.
- M10B does not follow recommendation carousels or recursive product links.
- M10B does not claim coupons, add to cart, check out, mutate address/account state, use stealth/proxies, handle CAPTCHA, or bypass anti-bot systems.
- Live quote capture remains environment-dependent through the existing M9/M6 adapter path.

## Deferred Work

- Live approved-platform candidate search behind the same bounded contract.
- Site-specific ecommerce extraction profiles.
- Explicit manual approval UI for candidate review.
- Cross-platform variant/product identity clustering beyond deterministic candidate records.
- Search-term price comparison remains out of scope.
