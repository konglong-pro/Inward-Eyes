---
doc_type: closeout
phase_id: m21_contract_integrity_hardening
title: M21 contract-integrity hardening
status: completed
canonical: true
related_contracts:
  - docs/contracts/browser-operation-contract.md
  - docs/contracts/capture-adapter-contract.md
  - docs/contracts/error-status-contract.md
  - docs/contracts/evidence-contract.md
  - docs/contracts/runtime-operations-contract.md
  - docs/contracts/schemas-and-validation-contract.md
related_adrs:
  - docs/adr/0001-evidence-first-browser-workflows.md
---

# M21 Contract-Integrity Hardening Closeout

## What Shipped

Run and evidence integrity:

- Added strict run/source identifiers and canonical run-relative path resolution.
- Rejected run reuse, traversal, external symlinks, cross-run derived-output writes, and unsafe overwrite targets.
- Made JSON, text, binary, manifest, report, and package writes use temporary-file replacement.
- Final workflow manifests now converge in memory and are written once with final status semantics.

Capture and continuation integrity:

- Enforced request-time public-network checks, approved-host boundaries, IP pinning, redirect checks, and browser transport restrictions.
- Required real supported image bytes and SHA-256 for screenshot evidence.
- Added strict PageCapture, capture-report, adapter-stage manifest, path, digest, run, task, and process admission checks.
- Added invocation ownership markers so failed wrappers cannot finalize another run.
- Added one-time continuation handoffs authenticated with HMAC and bound to the run, stages, input path, and admission artifact digests.
- Failed authentication restores a valid handoff; successful consumption remains one-time and replay is rejected.
- Parent/child stages enforce deferred manifests so intermediate runners cannot overwrite the outer canonical manifest.

Privacy and failure behavior:

- Admission failures no longer retain rejected raw captures, adapter reports, screenshots, or sensitive observation payloads in canonical runs.
- Adapter observation inputs are staged under temporary adapter directories and removed after admission.
- Input/model/source/backend validation runs before claiming a run directory, so deterministic input failures do not leave orphan runs.
- Capture, renderer, discovery, price, batch, review, index, export, and package failure paths fail closed with auditable final status where a run was legitimately claimed.

Schema, operations, distribution, and CI:

- Added stricter shared manifest/report/status/path validation across review, batch, index, export, and workflow validators.
- Expanded the standard-library JSON Schema subset validator and added contract-drift validation.
- Added an MIT license, exact `package-files.txt` inventory, portable plugin/release validators, sensitive-path rejection, Windows path checks, and reproducible atomic ZIP output.
- Expanded CI to compile all shipped scripts/evals, run every eval family, validate generated artifacts and representative runs, validate release inputs, and build the exact package dry-run.

## Frozen Behavior

- No new Codex skill or browser backend was added.
- No crawler replacement, broad crawling, marketplace monitoring, purchasing, account mutation, unrestricted logged-in browsing, stealth, proxy, CAPTCHA, or anti-bot behavior was added.
- Browser operation remains a bounded execution layer; deterministic schemas, evidence, validation, and rendering remain the product core.
- Marketplace publication and release tagging remain separate work.

## Acceptance Gates

Executed from the repository root on 2026-07-16:

- Full Python compile of every `scripts/**/*.py` and `evals/**/*.py`: passed.
- All 18 eval runners listed in `docs/testing.md`: passed.
- All generated-artifact schema checks listed in `docs/testing.md`: passed.
- Representative page, capture, research, discovery, price-candidate, and price run validators: passed.
- `python scripts\validation\validate_contract_drift.py`: passed.
- `python scripts\validation\validate_plugin.py .`: passed.
- `python scripts\validation\validate_release.py .`: passed.
- Official local plugin validator: passed.
- `python scripts\plugin_package.py --output-dir evals\.tmp\final-package`: passed.
- `git diff --check`: passed; Git reported line-ending conversion warnings only.

## Not Executed

- Live browser/network smoke tests were not run.
- Remote GitHub Actions status was not run in this local session.
- Marketplace publication, release tagging, and installation testing were not run.

## Remaining Limits

- The standard-library schema validator intentionally implements a documented subset of JSON Schema; workflow validators remain authoritative.
- Privacy scanning is conservative and cannot prove complete semantic redaction.
- Browser/network quality outside deterministic and synthetic replay fixtures remains unverified.
- The package is a local deterministic archive, not a marketplace release.
