# Evidence Contract

## Purpose

Every Inward Eyes output must be auditable. Evidence is the product boundary between browser observation and trusted artifacts.

## Applies To

- `page-to-md`
- `browser-research`
- `price-compare`
- Future browser extraction skills

## Terms

**Run**: One scoped execution.

**Run manifest**: Top-level file describing inputs, artifacts, evidence, validation, warnings, and manual review status.

**Evidence**: Source records, screenshots, selected text summaries, capture notes, timestamps, and validation reports used to support output artifacts.

## Required Run Directory Shape

```text
<output_root>/<run_id>/
  input.json
  manifest.json
  artifacts/
  evidence/
    screenshots/
  validation/
```

The plugin package must not be used as the default runtime output location.

## Required Manifest Fields

Future `manifest.json` must include:

- `run_id`
- `task`
- `started_at`
- `finished_at`
- `operator`
- `skill`
- `inputs`
- `artifacts`
- `evidence`
- `validation`
- `warnings`
- `requires_manual_review`
- `run_status`
- `validation_status`
- `manual_review`
- `completion_blockers`
- `screenshot_policy`

Allowed `run_status` values:

- `complete`
- `partial`
- `failed`
- `aborted_by_policy`

`manual_review` must include `required`, `severity`, and `reasons`. Severity values are `info`, `warning`, and `blocking`.

## Evidence Minimums

For each source:

- URL.
- Canonical URL when available.
- Page title.
- Site name when available.
- Access time.
- Capture method.
- Included content scope.
- Excluded content scope.
- Warnings.

For M8 browser-research capture, each provided source URL must have a stable source directory:

```text
capture/source-###/page_capture.json
evidence/source-###/source_record.json
evidence/source-###/screenshots/
```

The `source_id` must agree with the `source-###` directory name. Source capture failures must remain auditable through run warnings and partial/failed run status.

For M9 product-URL price capture, each provided product URL must use the same stable source directory shape:

```text
capture/source-###/page_capture.json
evidence/source-###/source_record.json
evidence/source-###/screenshots/
```

Product-page screenshots are required. Missing screenshot evidence fails validation for included product-page quotes unless the quote is explicitly excluded and the run is partial.

Screenshot policy must be explicit. Allowed statuses:

- `required_and_present`
- `required_but_missing`
- `not_required`
- `capture_failed`
- `redacted`

Screenshot evidence is required for:

- Logged-in pages.
- X-like or social threads.
- Forum threads.
- Ecommerce product pages.
- Infinite-scroll or dynamic pages.
- Ambiguous extraction.
- Any output likely to be manually challenged.

Screenshot evidence staged into `evidence/screenshots/` must be recorded in `manifest.json` with a `sha256:<hex>` digest. Validators must fail when a required screenshot is missing on disk or when the manifest screenshot digest is absent or does not match the staged file.

## Default Exclusions

Do not save by default:

- HAR/network logs.
- Cookies.
- Tokens.
- Browser profiles.
- Passwords.
- Payment data.
- Full account pages unrelated to the task.

Network evidence may be enabled only by an explicit future debug policy with redaction.

## SourceRecord Shape

Future schemas should include this shared object:

```json
{
  "source_id": "S001",
  "url": "https://example.com/page",
  "canonical_url": "https://example.com/page",
  "title": "Page title",
  "site_name": "Example",
  "page_type": "article",
  "accessed_at": "2026-06-09T10:30:00Z",
  "requires_login": false,
  "capture_method": "playwright_accessibility_snapshot",
  "evidence": {
    "screenshot": "evidence/S001.png",
    "snapshot": "evidence/S001.snapshot.json"
  },
  "content_scope": {
    "included": ["main_article"],
    "excluded": ["nav", "footer", "recommendations", "ads"]
  },
  "warnings": []
}
```

`source_record.json` is the canonical evidence file name for this object. Do not create a competing source summary evidence object.

## Validation

Validators must check:

- Artifact paths in the manifest exist.
- Evidence paths in the manifest exist.
- Required source fields exist.
- Timestamps are present.
- Screenshot requirements are enforced through `screenshot_policy`.
- Output artifacts reference source IDs or source URLs consistently.
