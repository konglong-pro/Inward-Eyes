---
doc_type: closeout
phase_id: m12_m20_post_rc_expansion
title: M12-M20 post-RC local operations expansion
status: completed
canonical: true
related_contracts:
  - docs/contracts/artifact-contracts.md
  - docs/contracts/error-status-contract.md
  - docs/contracts/evidence-contract.md
  - docs/contracts/safety-contract.md
  - docs/contracts/site-profile-contract.md
  - docs/contracts/runtime-operations-contract.md
related_adrs:
  - docs/adr/0001-evidence-first-browser-workflows.md
---

# M12-M20 Post-RC Expansion Closeout

## What Shipped

M12 adapter matrix:

- Added deterministic adapter inventory and validation in `scripts/inward_eyes/adapter_matrix.py`.
- Added `scripts/adapter_matrix_runner.py` and `evals/run_adapter_matrix_eval.py`.
- The matrix records existing supported boundaries only; it does not add Chrome DevTools, Browser Use, Computer Use, or other new browser backends.

M13 real-world-style evals:

- Added `evals/run_real_world_eval.py`.
- The eval uses replayed observation payloads and asserts no live Playwright fallback is needed.

M14 privacy/security:

- Expanded the action classifier coverage in `scripts/inward_eyes/safety.py`.
- Added privacy scanning in `scripts/inward_eyes/privacy.py`, `scripts/privacy_report_runner.py`, and `evals/run_privacy_eval.py`.
- The scanner blocks forbidden evidence keys and routes private text findings to manual review.

M15 site profiles:

- Added advisory profile catalog `profiles/site_profiles.json`.
- Added `schemas/site_profiles.schema.json`, `scripts/inward_eyes/site_profiles.py`, `scripts/site_profile_runner.py`, and `evals/run_site_profile_eval.py`.
- Profiles are extraction guidance only and never grant browser permissions.

M16 review UI:

- Added a local text review surface in `scripts/inward_eyes/review.py` and `scripts/review_run.py`.
- Added `evals/run_review_ui_eval.py`.
- The review surface summarizes manifest status, validation reports, blockers, warnings, missing paths, and manual-review reasons.

M17 distribution:

- Added deterministic package dry-run support in `scripts/inward_eyes/distribution.py` and `scripts/plugin_package.py`.
- Added `evals/run_distribution_eval.py`.
- Added `dist/` to `.gitignore`.
- This is local archive packaging, not marketplace publication.

M18-M19 batch, retry, and run database:

- Added sequential batch execution in `scripts/batch_runner.py`.
- Added rebuildable JSONL run indexing and retry-plan generation in `scripts/inward_eyes/run_index.py` and `scripts/run_database.py`.
- Added `evals/run_batch_retry_eval.py`.
- Manifests remain source of truth; the run index is rebuildable.

M20 exporters and extensions:

- Added view-only exporters in `scripts/inward_eyes/exporters.py` and `scripts/export_run.py`.
- Added `evals/run_export_eval.py`.
- Exporters read canonical run artifacts and write JSON, CSV, and Markdown summaries.

## Frozen Behavior

- No new Codex skills were added.
- No new browser backend was added.
- No broad crawling, marketplace monitoring, stealth, proxy, CAPTCHA, anti-bot bypass, purchasing, cart, checkout, coupon claiming, account mutation, or unrestricted logged-in browsing was added.
- Runtime outputs still belong under user-selected output roots such as `browser-operator-runs/` or ignored eval output roots.
- Generated indexes, packages, reviews, and exports are derived views unless explicitly recorded in a run manifest.

## Contracts Created or Updated

- `docs/contracts/site-profile-contract.md`
- `docs/contracts/runtime-operations-contract.md`
- `docs/contracts/artifact-contracts.md`
- `docs/contracts/safety-contract.md`
- `docs/contracts/schemas-and-validation-contract.md`

## Acceptance Gates

Run from `E:\Inward Eyes`.

- Compile gate including new scripts and evals.
- Existing eval suite from M0-M11.
- New phase evals:
  - `python evals\run_adapter_matrix_eval.py`
  - `python evals\run_real_world_eval.py`
  - `python evals\run_privacy_eval.py`
  - `python evals\run_site_profile_eval.py`
  - `python evals\run_review_ui_eval.py`
  - `python evals\run_distribution_eval.py`
  - `python evals\run_batch_retry_eval.py`
  - `python evals\run_export_eval.py`
- Site profile schema smoke check:
  - `python scripts\validation\validate_json_schema.py --schema schemas\site_profiles.schema.json --json profiles\site_profiles.json`
- Local plugin validation.
- `git diff --check`.

## Known Limitations

- Real-world evals are deterministic replay checks, not live network or browser smoke tests.
- Privacy detection is conservative pattern/key scanning and cannot prove complete redaction.
- Review UI is a CLI/text surface, not a graphical application.
- The distribution package is a local dry-run archive, not marketplace publication.
- Batch execution is sequential. Parallelism, locks, and remote schedulers remain out of scope.
- Run indexing is JSONL and rebuildable; no SQLite or service database was introduced.
- Exporters are JSON/CSV/Markdown only to preserve the standard-library dependency policy.
