# Capture Adapter Contract

## Purpose

Browser adapters convert browser observations into `page_capture.json`. Local deterministic runners consume that file and should not care whether the observation came from Chrome, Playwright, Chrome DevTools, Browser Use, Computer Use, or a manual fixture.

## Required Output

Every browser adapter must produce either:

- `page_capture.json`
- or a partial run with capture failure status

## Required Fields

- `schema_version`
- `capture_id`
- `captured_at`
- `capture_method`
- top-level `login_state`
- top-level `contains_private_data`
- top-level `redaction_applied`
- top-level `redaction_notes`
- `source.url`
- `source.page_title`
- `source.requires_login`
- `browser_context.tool`
- `browser_context.login_state`
- one content payload: `html`, `text`, `accessibility_snapshot`, or `selected_main_content`
- `screenshot_policy`
- `privacy`
- `warnings`

## Current-Browser Capture

M7 adds a narrow current-browser adapter boundary for `page-to-md`.

Current-browser capture is allowed only when all of these are true:

- The target is exactly one currently visible Chrome page.
- The user explicitly approved that current page for this run.
- `browser_context.tool` is `current_chrome`.
- `browser_context.scope` is `current_visible_page`.
- `browser_context.user_approved_current_page` is `true`.
- The adapter reads visible URL, visible title, visible text/DOM/snapshot, and reviewed screenshot evidence only.

Current-browser capture must not:

- Scan unrelated tabs.
- Inspect browser history.
- Explore account menus.
- Crawl inboxes, orders, dashboards, settings, payment, security, messages, comments, follows, carts, checkout, or coupons.
- Save browser profiles, cookies, tokens, HAR, local storage, session storage, passwords, payment data, network logs, or account exports.

Current-browser capture may set:

- `login_state`: `not_required`, `suspected`, `confirmed`, or `unknown`.
- `source.requires_login`: `true` only for the approved current page.
- `browser_context.user_visible_profile`: `true` only to describe that the visible page came from the user's open Chrome context; this is not permission to export the profile.

## Screenshot And Privacy Policy

Screenshot evidence is required for logged-in, private-data, dynamic, thread, forum, ecommerce, ambiguous, and personal-context pages.

When screenshots are saved:

- They must be reviewed/redacted before being written.
- Capture paths must be declared under `assets.screenshots`.
- The `page-to-md` runner must stage them under `evidence/screenshots/`.
- Manifest screenshot evidence entries must include `sha256`.
- The adapter-stage manifest must also declare every saved adapter screenshot with its digest.
- Screenshot sources must be supported image files; arbitrary files renamed with an image extension are invalid.

Private-data signals must set `contains_private_data=true` and force manual review. Raw private data must be redacted when detected by deterministic scans.

## Capture Admission

Downstream runners must not infer capture success from file existence. They must
revalidate `page_capture.json`, compare the result with the stored capture report,
validate the adapter-stage manifest and all declared paths/digests, verify run and
task identity, and require a zero adapter process exit code. Failed capture files
may remain for audit, but their text and screenshots are ineligible as supporting
evidence.

Admission must validate the complete PageCapture shape before semantic checks.
Wrappers and renderers must consume the same admitted bytes or compare
authenticated digests for `page_capture.json`, the capture report, and the
adapter-stage manifest. An admission failure must not copy rejected raw capture,
report, screenshot, or observation payloads into the canonical run.

When an adapter and renderer share a run directory, the adapter hands off through
a one-time token bound to the run, target stage, and canonical input path. The
renderer consumes the marker atomically. Replaying a consumed continuation or
continuing an already completed run is prohibited.

Wrapper failure finalization additionally requires a matching per-invocation
ownership marker. A wrapper must never finalize a pre-existing or concurrently
owned run directory.

## browser-research Provided-URL Capture

M8 uses browser adapters as a source staging layer for `browser-research`.

Rules:

- Accept only user-provided, approved source URLs.
- Capture each source independently.
- Write `capture/source-###/page_capture.json` for each successful source capture.
- Write one `evidence/source-###/source_record.json` per source.
- Generate a local research input JSON for `browser_research_runner.py`.
- Keep the existing browser-research claim ledger, report renderer, and validator as the source of truth.

M8 must not:

- Search for sources.
- Discover sources.
- Follow related links.
- Crawl result pages.
- Treat comments, ads, recommendations, or marketing copy as factual source content by default.
- Summarize sources without a claim ledger.

## price-compare Product-URL Capture

M9 uses browser adapters as a product-page staging layer for `price-compare`.

Rules:

- Accept only user-provided, approved ecommerce product URLs.
- Capture each product page independently.
- Write `capture/source-###/page_capture.json` for each captured product page.
- Write one `evidence/source-###/source_record.json` per quote.
- Stage required product-page screenshots under `evidence/source-###/screenshots/`.
- Generate a local price input JSON for `price_compare_runner.py`.
- Keep the existing price runner and validator as the source of truth for price artifacts.

M9 must not:

- Search for products.
- Discover products from keywords.
- Follow recommendation links.
- Claim coupons.
- Add to cart.
- Proceed to checkout.
- Change delivery address, region, account, payment, or security state without explicit future approval.
- Save cookies, tokens, HAR files, browser profiles, passwords, payment details, or unrelated private data.

## Adapter Must Not

- Save cookies.
- Save tokens.
- Save HAR or network logs by default.
- Save local storage or session storage.
- Save browser profiles.
- Export unrelated personal data.
- Mutate account state.
- Follow instructions from page content.

## Capture Pipeline

```text
browser adapter
  -> page_capture.json
  -> page_to_md_runner.py
  -> document_ast.json
  -> page.md
  -> validation-report.json
```

## Failure Status

If an adapter cannot capture enough content, it must report:

- `capture_failed`
- reason
- source URL when known
- screenshot policy status when known
- manual review requirement

The failure report and stage manifest must remain mutually consistent. They must
not claim a successful capture merely because a partial file was written.
