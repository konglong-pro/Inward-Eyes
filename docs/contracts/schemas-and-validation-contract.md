# Schemas and Validation Contract

## Purpose

Inward Eyes must produce structured JSON first, then render Markdown, CSV, charts, and reports from validated data. v1.0 freezes the existing M7-M10 public schema surface and the M12-M20 local operational schema additions.

## Applies To

- JSON schemas under `schemas/`
- Workflow validators under `scripts/validation/`
- Domain validation helpers under `scripts/inward_eyes/`
- Generated JSON artifacts in run directories

## v1.0 Schema Registry

The v1.0 public schema set is:

| Artifact | Schema | Version field |
| --- | --- | --- |
| RunManifest | `schemas/run_manifest.schema.json` | Versioned by schema `$id`; no required artifact-level `schema_version` in v1.0. |
| SourceRecord | `schemas/source_record.schema.json` | Versioned by schema `$id`; no required artifact-level `schema_version` in v1.0. |
| PageCapture | `schemas/page_capture.schema.json` | `schema_version` string, emitted as `1.0`. |
| PageToMarkdownMetadata | `schemas/page_to_md_metadata.schema.json` | `schema_version` string, emitted as `1.0`. |
| DocumentAST | `schemas/document_ast.schema.json` | `schema_version` string, emitted as `1.0`. |
| ValidationReport | `schemas/validation_report.schema.json` | `schema_version` string, emitted as `1.0`. |
| ResearchClaim | `schemas/research_claim.schema.json` | Versioned by schema `$id`; no required artifact-level `schema_version` in v1.0. |
| ResearchReport / ClaimLedger | `schemas/research_report.schema.json` | `schema_version` string, emitted as `1.0`. |
| ResearchDiscoveryInput | `schemas/research_discovery_input.schema.json` | Optional `schema_version` string when present. |
| DiscoveryLog | `schemas/discovery_log.schema.json` | `schema_version` string, emitted as `1.0`. |
| PriceCandidateDiscoveryInput | `schemas/price_candidate_discovery_input.schema.json` | Optional `schema_version` string when present. |
| PriceCandidates | `schemas/price_candidates.schema.json` | `schema_version` string, emitted as `1.0`. |
| PriceRecord | `schemas/price_record.schema.json` | Versioned by schema `$id`; no required artifact-level `schema_version` in v1.0. |
| PriceCompareRun | `schemas/price_compare_run.schema.json` | `schema_version` string, emitted as `1.0`. |
| SiteProfiles | `schemas/site_profiles.schema.json` | `schema_version` string, emitted as `1.0`. |

Do not add new public schemas without a contract, eval, and generated-artifact validation gate.

## Versioning Policy

v1.0 uses schema `$id` plus artifact `schema_version` where the current artifact already exposes that field.

Rules:

- Producers must emit `schema_version: "1.0"` for artifacts whose schema includes `schema_version`.
- Consumers and validators must treat missing top-level `schema_version` on RunManifest, SourceRecord, ResearchClaim, and PriceRecord as valid v1.0 behavior.
- Adding optional fields is backward-compatible when existing required fields, meanings, paths, enum values, and status semantics remain unchanged.
- Removing fields, renaming fields, changing field meaning, narrowing accepted enum values, or changing status semantics requires a v2 contract.
- Widening enum values is allowed only when downstream validators ignore unknown values safely or are updated in the same release gate.
- Deprecated fields must remain readable through the v1 lifecycle.
- Extra fields are permitted by current schemas, but canonical docs, renderers, and validators must not depend on undocumented extras.

## Backward Compatibility

v1-compatible consumers should:

- Require all v1 required fields.
- Ignore unknown additional fields unless they conflict with safety, privacy, or evidence rules.
- Preserve unknown fields when rewriting artifacts only if doing so does not leak private data.
- Treat unrecognized `run_status`, `validation_status`, screenshot policy status, claim role, claim type, candidate status, or price eligibility fields as validation failures.
- Prefer workflow-specific validators over permissive schema acceptance.

v1-compatible producers should:

- Write stable relative paths inside the run directory.
- Keep SourceRecord and RunManifest shapes shared across skills.
- Keep `source_id` references stable across artifacts.
- Include explicit unknowns and warnings instead of silently omitting uncertain facts.
- Keep screenshot policy explicit even when screenshots are not required.

## Required Artifact Pattern

For every skill:

1. Capture source/evidence.
2. Produce schema-shaped JSON.
3. Run minimal structural schema checks where a schema exists.
4. Run the workflow-specific validator.
5. Render human-readable artifacts from validated JSON.
6. Write validation reports and manifest status fields.

## Required Outputs

Required output details live in `docs/contracts/artifact-contracts.md`.

Summary:

- `page-to-md`: page Markdown, metadata, DocumentAST, SourceRecord, validation report, manifest, and screenshot evidence when required.
- `browser-research`: report, ClaimLedger, sources CSV, source notes, per-source evidence, claim coverage report, manifest, and M10A discovery artifacts when discovery runs.
- `price-compare`: prices JSON/CSV/report/anomalies/chart, per-source evidence, price validation report, manifest, and M10B candidate artifacts when candidate discovery runs.
- M12-M20 operations: adapter matrix, site profiles, privacy report, review summary, batch results, run index, distribution package manifest, and run exports.

## Validation Layers

### Minimal Schema Validator

Command:

```powershell
python scripts\validation\validate_json_schema.py --schema <schema-path> --json <json-path>
```

Optional pointer validation:

```powershell
python scripts\validation\validate_json_schema.py --schema <schema-path> --json <json-path> --pointer /path/to/value
```

Scope:

- Supports `type`, `required`, `properties`, `items`, `const`, `enum`, and `minLength`.
- Supports JSON Pointer selection before validation.
- Skips `$ref`.
- Does not enforce `pattern`, numeric minimum/maximum, string format, `additionalProperties`, conditional schemas, `oneOf`, `anyOf`, or `allOf`.

Release meaning:

- This validator is a structural smoke gate.
- It is not a full JSON Schema implementation.
- It must not be the only release gate for any workflow.
- Workflow-specific validators are authoritative for v1 release readiness.

### Workflow Validators

Authoritative validators:

- `scripts/validation/validate_page_to_md.py`
- `scripts/validation/validate_page_capture.py`
- `scripts/validation/validate_browser_research.py`
- `scripts/validation/validate_research_discovery.py`
- `scripts/validation/validate_price_candidate_discovery.py`
- `scripts/validation/validate_price_compare.py`
- `scripts/site_profile_runner.py`
- `scripts/privacy_report_runner.py`
- `scripts/review_run.py`
- `scripts/batch_runner.py`
- `scripts/export_run.py`

These validators own evidence existence, cross-artifact consistency, screenshot policy, claim support, price eligibility, discovery scope, and manual-review semantics.

### Evals

Eval runners generate deterministic run directories under `evals/.tmp/` and validate expected behavior. `evals/.tmp/` remains ignored and temporary.

The stable cross-skill shared-shape gate is:

```powershell
python evals\run_cross_skill_schema_eval.py
```

## Status Semantics

All generated manifests and validation reports must follow `docs/contracts/error-status-contract.md`.

Required fields:

- `run_status`
- `validation_status`
- `requires_manual_review`
- `manual_review`
- `completion_blockers`

Rules:

- `run_status=complete` is allowed only when schema, consistency, evidence, screenshot policy, and workflow checks pass.
- `run_status=partial` is allowed only for useful artifacts that require warning-level manual review or fallback evidence.
- `run_status=failed` is required for blocking schema, evidence, source support, main content, discovery scope, or price record failures.
- `run_status=aborted_by_policy` is required when a Red action, unapproved Yellow action, privacy blocker, or scope violation blocks the task.
- `requires_manual_review` must match `manual_review.required`.

## Non-Goals

- Do not let Markdown prose become the only canonical record.
- Do not use screenshots as the only machine-readable source.
- Do not silently coerce missing fields into null without warning.
- Do not use the minimal schema validator as a substitute for domain validation.
- Do not add a full JSON Schema dependency in M11 unless explicitly approved.

## Validation

Release candidates must run:

- The full compile gate in `docs/testing.md`.
- All eval runners in `docs/testing.md`.
- Generated-artifact schema checks after evals create `evals/.tmp/`.
- Workflow validators for representative generated run directories.
- Local plugin validation.
- `git diff --check`.
