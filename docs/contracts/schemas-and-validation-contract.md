# Schemas and Validation Contract

## Purpose

Inward Eyes must produce structured JSON first, then render Markdown, CSV, charts, and reports from validated data. This prevents unchecked model prose from becoming the source of truth.

## Planned Shared Schemas

- `source_record.schema.json`
- `run_manifest.schema.json`
- `page_capture.schema.json`
- `page_to_md_metadata.schema.json`
- `document_ast.schema.json`
- `research_claim.schema.json`
- `research_report.schema.json`
- `research_discovery_input.schema.json`
- `discovery_log.schema.json`
- `price_candidate_discovery_input.schema.json`
- `price_candidates.schema.json`
- `price_record.schema.json`
- `price_compare_run.schema.json`

In M2, only `run_manifest`, `source_record`, `page_capture`, `page_to_md_metadata`, `document_ast`, and validation reports are enforced. Research and price schemas may exist as planned placeholders until M3/M4.

## Required Artifact Pattern

For every skill:

1. Capture source/evidence.
2. Produce schema-shaped JSON.
3. Validate JSON.
4. Render human-readable artifacts from validated JSON.
5. Write validation report.

## page-to-md Required Outputs

- `artifacts/page.md`
- `artifacts/metadata.json`
- `artifacts/document_ast.json`
- `evidence/` screenshot when required
- `validation/validation-report.json`
- `manifest.json`

## browser-research Required Outputs

- `artifacts/report.md`
- `artifacts/claims.json`
- `artifacts/sources.csv`
- `artifacts/source_notes.md`
- source evidence directories
- `validation/claim-coverage-report.json`
- `manifest.json`

M10A discovery runs additionally require:

- `artifacts/discovery-log.json`
- `artifacts/discovery-log.md`
- `validation/discovery-validation-report.json`

M10B candidate discovery runs additionally require:

- `artifacts/candidates.json`
- `artifacts/candidates.csv`
- `artifacts/candidate-review.md`
- `validation/candidate-validation-report.json`
- `validation/warnings.md`

When quote extraction proceeds, M10B must also produce the normal `price-compare` artifacts and `validation/price-validation-report.json`.

## price-compare Required Outputs

- `artifacts/prices.json`
- `artifacts/prices.csv`
- `artifacts/price-report.md`
- `artifacts/anomalies.md`
- optional chart artifacts after chart renderer exists
- source screenshots
- `validation/price-validation-report.json`
- `manifest.json`

## Validation Rules

### Common

- Required fields must exist.
- URLs and source IDs must be consistent.
- Artifact paths must exist.
- Manifest artifact and evidence paths must exist.
- Evidence requirements must be met.
- Unknown fields must be explicit.
- Run manifests must include `run_status`, `validation_status`, `manual_review`, and `completion_blockers`.
- `run_status=complete` is allowed only when required schema, consistency, evidence, and screenshot policy checks pass.
- `run_status=partial` is allowed for useful outputs that require manual review or fallback evidence.
- `run_status=failed` is required for core schema, evidence, main content, claim support, or price record failures.
- `run_status=aborted_by_policy` is required when a Red action or unapproved Yellow action blocks the task.

### page-to-md

- Metadata title exists or `title_not_found` warning exists.
- Markdown contains one primary H1.
- Metadata title and H1 are consistent.
- Author and publish time are not invented.
- Boilerplate pollution is checked.
- Image captions are preserved or marked missing.
- Logged-in, private-data, dynamic, thread, forum, ecommerce, ambiguous, and personal-context pages must satisfy screenshot policy with evidence on disk.
- Staged screenshot evidence in the manifest must include a matching `sha256`.
- Private-data warnings must force manual review.
- Prompt-injection text from the page must be preserved as data, not treated as instructions.
- Red actions or unapproved current-browser scope must produce `run_status=aborted_by_policy`.

### browser-research

- Every key finding has one or more source IDs.
- Claims use `claim_role`: `key_claim`, `background`, `method_note`, `unknown`, or `limitation`.
- Claim type is one of fact, inference, or unknown.
- Direct support and inferred support are separate.
- Sources table and claim ledger agree.
- Duplicated syndications are not counted as independent sources without note.
- Sources record independence as `primary_source`, `independent`, `not_independent`, or `unknown`.
- Source evidence directories must agree with source IDs.
- Key claims must not rely on failed source captures.
- Non-independent or syndicated sources must not make a claim count as independently supported unless the claim is marked `single_source=true`.
- Browser-captured source runs must keep `capture/source-###/page_capture.json`, `evidence/source-###/source_record.json`, `artifacts/claims.json`, `artifacts/sources.csv`, report, manifest, and validation report consistent.
- Discovery runs must keep selected source count at or below `max_sources`.
- Discovery `max_sources` must not exceed 20.
- Discovery requires allowed domains or allowed source types.
- Every selected discovery source must have selection rationale.
- Every selected discovery source must have a matching `SourceRecord`.
- Rejected discovery candidates must retain rejection reasons.
- Discovery must not record recursive link following.
- Prompt-injection text in search results must be treated as data and must not be accepted as an instruction.

### price-compare

- Every quote has product identity, specs, seller, platform, region, currency, timestamp, URL, and screenshot.
- Price components remain separate.
- Quote context and `quote_context_hash` must exist.
- Estimated total must include calculation explanation.
- Coupon actions are represented explicitly.
- Low-confidence matches are excluded from final lowest-price conclusions.
- Product-page screenshot policy must be present and required screenshot evidence must exist on disk.
- Eligible lowest-price quotes must match comparison region, currency, and required specs.
- Out-of-stock, unknown-total, incomplete-spec, cart-required, checkout-required, coupon-claim-required, address-change-required, and manual-review-required quotes must not enter final lowest-price conclusions.
- Browser-captured price runs must keep `capture/source-###/page_capture.json`, `evidence/source-###/source_record.json`, `artifacts/prices.json`, CSV, report, manifest, and validation report consistent.
- Anomalies are listed.

### price-candidate-discovery

- Candidate discovery requires target product, required specs, allowed platforms, allowed domains, region, and currency.
- `max_candidates_per_platform` must be positive and defaults to 3.
- Total candidates must not exceed 20.
- Candidate URL domains must remain inside approved domains.
- Candidate platforms must remain inside approved platforms.
- Public HTTP(S) product URLs are required.
- Duplicate product URLs must be rejected or deduped before quote capture.
- Recommendation links must be rejected.
- Recursive link candidates must be rejected.
- Every non-rejected candidate must have selection rationale.
- Every candidate must have `match_confidence`, `mismatch_flags`, and a rationale field appropriate to its status.
- Missing required specs, required spec mismatches, low match confidence, seller exclusions, and condition mismatches must force manual review.
- Automatic quote extraction may include only high-confidence candidates with no manual-review flags when policy allows it.
- Explicitly approved low-confidence or incomplete candidates may be passed to M9 quote capture, but M9 price validation must still exclude invalid quotes from lowest-price conclusions.
- M9 `provided_url_candidate_assessment` remains the assessment method for product URLs after handoff. M10B `approved_candidate_discovery` is only for candidate records.

## Non-Goals

- Do not let Markdown prose become the only canonical record.
- Do not use screenshots as the only machine-readable source.
- Do not silently coerce missing fields into null without warning.
