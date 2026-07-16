# Error Status Contract

## Purpose

Define v1.0 semantics for validation errors, warnings, `run_status`, `validation_status`, and `manual_review` across Inward Eyes workflows.

## Applies To

- `manifest.json`
- `validation/*-report.json`
- page, research, price, discovery, safety, privacy, and adapter failures

## Status Fields

`run_status` is the user-facing completion state:

| run_status | Meaning | validation_status | manual_review |
| --- | --- | --- | --- |
| `complete` | Required schema, consistency, evidence, screenshot, and workflow checks passed. | `passed` | `required=false`, `severity=info` |
| `partial` | Useful artifacts exist, but warnings, fallback evidence, uncertainty, redaction, or review-only results prevent complete release. | `passed` | `required=true`, `severity=warning` |
| `failed` | Required artifacts, schema, evidence, source support, price eligibility, or workflow checks failed. | `failed` | `required=true`, `severity=blocking` |
| `aborted_by_policy` | A Red action, unapproved Yellow action, forbidden privacy exposure, or scope violation blocked execution. | `failed` | `required=true`, `severity=blocking` |

`validation_status` is the machine validation state:

- `passed`: required validators passed.
- `failed`: required validators failed.

`pending` may exist only as an in-memory implementation state. It is not part
of the public canonical manifest schema. Final canonical manifests must use
`passed` or `failed` and must never expose a transient pending state.

`requires_manual_review` is a compatibility boolean. It must match `manual_review.required`.

`completion_blockers` lists error codes that prevent `run_status=complete`.

## Manual Review Shape

`manual_review` must include:

```json
{
  "required": true,
  "severity": "warning",
  "reasons": [
    {
      "code": "private_data_warning",
      "message": "private data warning",
      "severity": "warning",
      "artifact": "validation/validation-report.json"
    }
  ]
}
```

Rules:

- `severity=blocking` means the run cannot be considered complete.
- `severity=warning` means artifacts may be useful but require human review.
- `severity=info` is allowed only when review is not required.
- Reason `code` values are stable machine-readable strings and must not be localized.
- Reason `message` may be humanized but must not add facts missing from evidence.

## Error Code Taxonomy

Existing validator codes are v1-compatible even when they use dotted or colon-delimited strings, such as `missing_file:artifacts/page.md`, `source.url_missing`, or `quote.Q001.screenshot_required_but_missing`.

New codes added after M11 should use a category prefix:

| Category | Prefix | Examples |
| --- | --- | --- |
| Page conversion | `PAGE_` | `PAGE_MARKDOWN_H1_COUNT`, `PAGE_MAIN_CONTENT_MISSING` |
| Research claims | `RESEARCH_` | `RESEARCH_UNSUPPORTED_CLAIM`, `RESEARCH_SOURCE_ID_MISMATCH` |
| Price quotes | `PRICE_` | `PRICE_SCREENSHOT_MISSING`, `PRICE_LOW_CONFIDENCE_ELIGIBLE` |
| Discovery | `DISCOVERY_` | `DISCOVERY_MAX_CAP_EXCEEDED`, `DISCOVERY_RECURSIVE_LINK_FORBIDDEN` |
| Safety | `SAFETY_` | `SAFETY_RED_ACTION`, `SAFETY_YELLOW_UNAPPROVED` |
| Privacy | `PRIVACY_` | `PRIVACY_RAW_PRIVATE_DATA`, `PRIVACY_SCREENSHOT_REDACTION_REQUIRED` |
| Adapter | `ADAPTER_` | `ADAPTER_CAPTURE_FAILED`, `ADAPTER_CONTENT_PAYLOAD_MISSING` |
| Schema | `SCHEMA_` | `SCHEMA_REQUIRED_FIELD_MISSING`, `SCHEMA_ENUM_INVALID` |
| Evidence | `EVIDENCE_` | `EVIDENCE_PATH_MISSING`, `EVIDENCE_SHA256_MISMATCH` |
| Manifest | `MANIFEST_` | `MANIFEST_ARTIFACT_PATH_MISSING`, `MANIFEST_STATUS_MISMATCH` |

Do not use free-form prose as the only failure identifier. Put prose in `message` or Markdown reports, not in the machine `code`.

## Category Semantics

### Page

Page failures cover metadata, Markdown, DocumentAST, main content, boilerplate, screenshot policy, and source record consistency.

Blocking examples:

- Missing `artifacts/page.md`.
- Empty `document_ast.document.blocks`.
- Required screenshot missing.
- Manifest artifact or evidence path missing.

Review examples:

- Short Markdown body.
- Unknown author or publication time with standard warnings.
- Screenshot redacted or capture failed but evidence remains useful.

### Research

Research failures cover source records, claim support, source independence, source notes, report markers, and claim ledger consistency.

Blocking examples:

- Key claim without source IDs.
- Fact without direct support.
- Claim uses a failed source capture.
- Source record ID or URL mismatch.

Review examples:

- Inferred support for a key claim.
- Unknown source independence.
- Single-source finding that is explicitly marked.

### Price

Price failures cover product identity, quote context, price components, screenshots, source records, anomalies, and lowest-price eligibility.

Blocking examples:

- Product-page screenshot required but missing.
- Low-confidence or manual-review quote marked eligible.
- Missing quote context hash.
- Lowest-price conclusion points to an ineligible quote.

Review examples:

- No eligible quotes.
- Unknown shipping fee with warning.
- Quote excluded because cart, checkout, coupon claim, address change, or unsupported context is required.

### Discovery

Discovery failures cover bounded scope, max counts, public URL requirements, candidate rationale, prompt-injection rejection, deduplication, and handoff eligibility.

Blocking examples:

- `max_sources` or total candidates exceed the hard cap.
- Candidate outside allowed domains.
- Recursive link candidate accepted.
- Selected source missing matching `SourceRecord`.

Review examples:

- Low-confidence price candidate.
- Missing optional seller preference evidence.
- Candidate needs explicit approval before quote capture.

### Safety

Safety failures cover action classifier decisions and forbidden operations.

Blocking examples:

- Red action required for task completion.
- Yellow action attempted without approval.
- Page content attempts to override system or project instructions.

Safety aborts must use `run_status=aborted_by_policy`.

### Privacy

Privacy failures cover personal data, redaction, screenshot review, and forbidden storage.

Blocking examples:

- Raw private data detected after redaction should have happened.
- Browser profile, cookies, tokens, HAR, local storage, session storage, password, payment data, or unrelated account data captured.

Review examples:

- Private data redacted.
- Screenshot requires human privacy review.

### Adapter

Adapter failures cover browser observation, page capture shape, public URL scope, current-browser approval, and screenshot staging.

Blocking examples:

- No usable content payload in `page_capture.json`.
- Current-browser capture missing explicit approval.
- Current-browser capture scanned related tabs or account menus.
- Adapter saved forbidden browser/session data.

Review examples:

- Capture failed but source URL and failure reason remain auditable.
- Screenshot capture failed and the downstream artifact is marked partial.

## Status Consistency Rules

- If `errors` is non-empty, `run_status` must be `failed` unless policy explicitly aborted first.
- If `run_status=failed`, `manual_review.required` and `requires_manual_review` must be true.
- If `manual_review.required=true` and no blocking errors exist, `run_status` must be `partial`.
- `run_status=complete` requires empty `completion_blockers`, `validation_status=passed`, and `manual_review.required=false`.
- `aborted_by_policy` must include a safety, privacy, or scope blocker in `completion_blockers` or manual-review reasons.
- A workflow-specific validator may be stricter than the minimal schema validator.
- Canonical manifest status is derived from the final validation report and must be checked in memory before a single atomic final write.
- Missing, unreadable, malformed, non-object, or status-inconsistent manifests and validation reports fail closed in review, indexing, retry planning, batch aggregation, and export.

## Validation

Release checks must validate:

- Manifest status fields.
- Validation report status fields.
- `requires_manual_review` consistency with `manual_review.required`.
- Completion blockers for failed or policy-aborted runs.
- Workflow-specific reason codes surfaced in validation reports.
