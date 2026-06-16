# M7 Current Chrome / Logged-in Page Capture MVP Closeout

## What Shipped

- M7 current-browser capture boundary for one user-approved currently visible Chrome page.
- `scripts/capture/current_chrome_capture.py` for approved current-page observations to `capture/page_capture.json`.
- `scripts/capture/current_chrome_page_to_md_runner.py` for capture -> capture validation -> deterministic page-to-md rendering -> run validation.
- Top-level `page_capture.json` aliases for `login_state`, `contains_private_data`, `redaction_applied`, and `redaction_notes`.
- Current-browser contract validation requiring explicit approval, `current_visible_page` scope, screenshot/privacy policy, and no unrelated tab/account/profile/session artifacts.
- Screenshot evidence staging with `sha256` recorded in manifest evidence entries.
- Page-to-md validation failures for required screenshot evidence missing on disk or screenshot digest mismatch.
- Private-data warnings propagated into page-to-md metadata and manual review status.
- Synthetic adapter eval coverage for:
  - logged-in current page with screenshot present
  - logged-in current page with missing screenshot failure
  - current page with private-data warning requiring manual review
  - current page with prompt-injection text preserved as data
  - attempted Red action aborting with `run_status=aborted_by_policy`
- Manual smoke documentation for current Chrome capture without committing real logged-in content or screenshots.
- CI updates for M7 compile and generated current-browser `page_capture.json` schema validation.

## Frozen Behavior

- M7 supports `page-to-md` only.
- M7 captures exactly one user-approved current Chrome page per run.
- Current-browser capture is represented as `browser_context.tool=current_chrome` and `browser_context.scope=current_visible_page`.
- Current-browser capture may record `login_state=not_required|suspected|confirmed|unknown`.
- Logged-in, private-data, dynamic, thread, forum, ecommerce, ambiguous, and personal-context pages require screenshot policy enforcement.
- Screenshots are accepted only after privacy review/redaction policy is applied.
- Required screenshots must be staged under `evidence/screenshots/` and manifest screenshot entries must include a matching `sha256`.
- Private-data warnings force manual review.
- Prompt-injection text is preserved as page data and not executed as instruction.
- Red actions and unapproved current-page scope abort the run.
- The deterministic `page_to_md_runner.py` remains the renderer; browser adapters only produce `page_capture.json`.

## Tests / Gates

Passed during closeout:

- `python -m py_compile scripts\page_to_md_runner.py scripts\capture\playwright_mcp_capture.py scripts\capture\page_to_md_browser_runner.py scripts\capture\current_chrome_capture.py scripts\capture\current_chrome_page_to_md_runner.py scripts\markdown\render_page_md.py scripts\validation\validate_page_to_md.py scripts\validation\validate_page_capture.py scripts\validation\validate_json_schema.py scripts\validation\classify_browser_action.py scripts\validation\validate_browser_research.py scripts\validation\validate_price_compare.py scripts\inward_eyes\__init__.py scripts\inward_eyes\capture.py scripts\inward_eyes\html_extract.py scripts\inward_eyes\io.py scripts\inward_eyes\markdown.py scripts\inward_eyes\safety.py scripts\inward_eyes\validation.py scripts\inward_eyes\research.py scripts\inward_eyes\price.py scripts\browser_research_runner.py scripts\price_compare_runner.py evals\run_eval.py evals\run_safety_eval.py evals\run_research_eval.py evals\run_price_eval.py evals\run_capture_adapter_eval.py evals\run_cross_skill_schema_eval.py`
- `python evals\run_eval.py`
- `python evals\run_safety_eval.py`
- `python evals\run_research_eval.py`
- `python evals\run_price_eval.py`
- `python evals\run_capture_adapter_eval.py`
- `python evals\run_cross_skill_schema_eval.py`
- `python scripts\validation\validate_json_schema.py --schema schemas\page_capture.schema.json --json evals\.tmp\capture-adapter\valid-capture\capture\page_capture.json`
- `python scripts\validation\validate_json_schema.py --schema schemas\page_capture.schema.json --json evals\.tmp\capture-adapter\current-chrome-output\eval-current-chrome-logged-in\capture\page_capture.json`
- `python scripts\validation\validate_json_schema.py --schema schemas\page_to_md_metadata.schema.json --json evals\.tmp\page-to-md\eval-public-article\artifacts\metadata.json`
- `python scripts\validation\validate_json_schema.py --schema schemas\run_manifest.schema.json --json evals\.tmp\page-to-md\eval-public-article\manifest.json`
- `python scripts\validation\validate_json_schema.py --schema schemas\validation_report.schema.json --json evals\.tmp\page-to-md\eval-public-article\validation\validation-report.json`
- `python scripts\validation\validate_json_schema.py --schema schemas\research_report.schema.json --json evals\.tmp\browser-research\eval-evidence-backed-research\artifacts\claims.json`
- `python scripts\validation\validate_json_schema.py --schema schemas\run_manifest.schema.json --json evals\.tmp\browser-research\eval-evidence-backed-research\manifest.json`
- `python scripts\validation\validate_json_schema.py --schema schemas\validation_report.schema.json --json evals\.tmp\browser-research\eval-evidence-backed-research\validation\claim-coverage-report.json`
- `python scripts\validation\validate_json_schema.py --schema schemas\price_compare_run.schema.json --json evals\.tmp\price-compare\eval-product-quotes\artifacts\prices.json`
- `python scripts\validation\validate_json_schema.py --schema schemas\price_record.schema.json --json evals\.tmp\price-compare\eval-product-quotes\artifacts\prices.json --pointer /quotes/0`
- `python scripts\validation\validate_json_schema.py --schema schemas\run_manifest.schema.json --json evals\.tmp\price-compare\eval-product-quotes\manifest.json`
- `python scripts\validation\validate_json_schema.py --schema schemas\validation_report.schema.json --json evals\.tmp\price-compare\eval-product-quotes\validation\price-validation-report.json`
- `python scripts\validation\validate_page_to_md.py evals\.tmp\capture-adapter\current-chrome-output\eval-current-chrome-logged-in`
- `python scripts\validation\validate_page_capture.py evals\.tmp\capture-adapter\current-chrome-output\eval-current-chrome-logged-in\capture\page_capture.json`
- `python scripts\validation\validate_browser_research.py evals\.tmp\browser-research\eval-evidence-backed-research`
- `python scripts\validation\validate_price_compare.py evals\.tmp\price-compare\eval-product-quotes`
- `python C:\Users\62406\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py "E:\Inward Eyes"`
- `git diff --check`

`git diff --check` exited 0 and reported only Git line-ending normalization warnings for touched Markdown files.

## Known Limitations

- M7 does not attach to Chrome by itself; it defines the safe artifact interface for approved current-page observations.
- Live current-browser capture remains environment/tool dependent.
- Real logged-in page smoke tests must remain local and must not commit content or screenshots.
- The deterministic private-data scanner is minimal and currently catches only narrow text patterns.
- Screenshot privacy review/redaction is represented by policy flags; image redaction tooling is not implemented.
- Current-browser capture is not a broad browser operator.

## Deferred Work

- Real browser connector integration for current-page observation.
- Better privacy scanning and optional image redaction tooling.
- Full X/forum thread capture and infinite-scroll handling.
- `browser-research` source capture from browser observations.
- `price-compare` ecommerce URL capture and quote extraction.
- Marketplace distribution, package release workflow, and plugin hooks.
