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

### page-to-md

- Metadata title exists or `title_not_found` warning exists.
- Markdown contains one primary H1.
- Metadata title and H1 are consistent.
- Author and publish time are not invented.
- Boilerplate pollution is checked.
- Image captions are preserved or marked missing.

### browser-research

- Every key finding has one or more source IDs.
- Claim type is one of fact, inference, or unknown.
- Direct support and inferred support are separate.
- Sources table and claim ledger agree.
- Duplicated syndications are not counted as independent sources without note.

### price-compare

- Every quote has product identity, specs, seller, platform, region, currency, timestamp, URL, and screenshot.
- Price components remain separate.
- Coupon actions are represented explicitly.
- Low-confidence matches are excluded from final lowest-price conclusions.
- Anomalies are listed.

## Non-Goals

- Do not let Markdown prose become the only canonical record.
- Do not use screenshots as the only machine-readable source.
- Do not silently coerce missing fields into null without warning.
