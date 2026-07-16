---
doc_type: phase_plan
phase_id: m11_v1_hardening_release_candidate
title: v1.0 hardening and release candidate
status: completed
canonical: true
related_contracts:
  - docs/contracts/artifact-contracts.md
  - docs/contracts/error-status-contract.md
  - docs/contracts/evidence-contract.md
  - docs/contracts/browser-operation-contract.md
  - docs/contracts/capture-adapter-contract.md
  - docs/contracts/schemas-and-validation-contract.md
  - docs/contracts/safety-contract.md
related_adrs:
  - docs/adr/0001-evidence-first-browser-workflows.md
release_gate: docs/planning/archive/m11-v1-hardening-release-candidate.md#v10-acceptance-gates
---

# M11 v1.0 Hardening and Release Candidate

Status: completed on 2026-06-16. See `docs/planning/archive/m11-v1-release-risk-report.md` for gate evidence and residual risks.

## Goal

Freeze the public contracts for Inward Eyes v1.0 and make the existing M7-M10 workflows release-ready.

M11 is a hardening phase. It must not add new skills, browser backends, or product scope.

## Scope

In scope:

- Audit README, AGENTS, project status, phase manifest, architecture, testing docs, and all root skill files for status drift.
- Freeze v1.0 artifact and schema compatibility policy.
- Define public artifact contracts for RunManifest, SourceRecord, PageCapture, DocumentAST, ClaimLedger, PriceRecord, and discovery artifacts.
- Define error code taxonomy and unified `run_status` / `manual_review` semantics.
- Explicitly scope the minimal JSON schema validator.
- Add release checklist, acceptance gates, and release-risk reporting.
- Run all repository-contained evals, validators, and plugin validation.

Out of scope:

- New skills.
- New browser backends.
- Broad crawling, monitoring, marketplace crawling, unrestricted logged-in browsing, or crawler replacement behavior.
- Purchasing, cart, checkout, coupon claiming, account/payment/address mutation, stealth, proxies, CAPTCHA handling, or anti-bot bypass.
- Marketplace distribution implementation.
- Runtime database, batch/retry system, review UI, exporters, or site profiles.

## Interfaces Touched

- Documentation lifecycle files: `README.md`, `AGENTS.md`, `docs/active/current.md`, `docs/project-status.md`, `docs/phase-manifest.yaml`.
- Durable contracts under `docs/contracts/`.
- Skill entry docs under `skills/*/SKILL.md`.
- Testing and release documentation under `docs/testing.md` and this phase plan.

M11 may update schemas or validators only to resolve contract contradictions discovered during hardening. Any such change must be narrow, backward-compatible, and covered by evals or validator checks.

## Contract Freeze

The v1.0 public surface is the existing M7-M10 workflow set:

- `page-to-md`: local HTML/page capture, M6 public URL adapter capture, and M7 one approved current Chrome page capture.
- `browser-research`: local/provided-source claim-ledger workflow, M8 provided-URL capture, and M10A bounded public source discovery.
- `price-compare`: local/provided-product URL quote workflow, M9 product URL capture, and M10B approved candidate discovery.

Contract ownership:

- `docs/contracts/artifact-contracts.md`: public artifact shapes and traceability requirements.
- `docs/contracts/error-status-contract.md`: error taxonomy, run status, validation status, and manual review semantics.
- `docs/contracts/schemas-and-validation-contract.md`: schema versioning, backward compatibility, and validator scope.
- Existing evidence, browser, capture-adapter, and safety contracts remain binding.

## Release Checklist

- Current phase resolves to M11 in `docs/phase-manifest.yaml`.
- M0-M10 are documented as completed/frozen baselines, not active instructions.
- No completed phase plans remain under `docs/planning/active/`.
- README and AGENTS describe M11 as active hardening and do not claim v1.0 is shipped.
- `docs/testing.md` contains the complete M11 release gate.
- All `skills/*/SKILL.md` files align with M7-M10 scope and v1 contracts.
- Minimal schema validator is explicitly scoped as structural smoke validation, not a full JSON Schema engine.
- All evals and generated-artifact validators run from a clean repository state.
- Plugin validation runs locally.
- `git diff --check` passes.
- Release-risk report exists and lists remaining blockers, skipped checks, and residual risks.

## v1.0 Acceptance Gates

Run from `E:\Inward Eyes`.

1. Full compile gate:

   ```powershell
   python -m py_compile scripts\page_to_md_runner.py scripts\capture\playwright_mcp_capture.py scripts\capture\page_to_md_browser_runner.py scripts\capture\current_chrome_capture.py scripts\capture\current_chrome_page_to_md_runner.py scripts\research_discovery_runner.py scripts\research_capture_runner.py scripts\price_candidate_discovery_runner.py scripts\price_capture_runner.py scripts\markdown\render_page_md.py scripts\validation\validate_page_to_md.py scripts\validation\validate_page_capture.py scripts\validation\validate_json_schema.py scripts\validation\classify_browser_action.py scripts\validation\validate_research_discovery.py scripts\validation\validate_browser_research.py scripts\validation\validate_price_candidate_discovery.py scripts\validation\validate_price_compare.py scripts\inward_eyes\__init__.py scripts\inward_eyes\capture.py scripts\inward_eyes\discovery.py scripts\inward_eyes\price_discovery.py scripts\inward_eyes\html_extract.py scripts\inward_eyes\io.py scripts\inward_eyes\markdown.py scripts\inward_eyes\safety.py scripts\inward_eyes\validation.py scripts\inward_eyes\research.py scripts\inward_eyes\price.py scripts\browser_research_runner.py scripts\price_compare_runner.py evals\run_eval.py evals\run_safety_eval.py evals\run_research_eval.py evals\run_research_discovery_eval.py evals\run_research_capture_eval.py evals\run_price_eval.py evals\run_price_candidate_discovery_eval.py evals\run_price_capture_eval.py evals\run_capture_adapter_eval.py evals\run_cross_skill_schema_eval.py
   ```

2. Eval suite:

   ```powershell
   python evals\run_eval.py
   python evals\run_safety_eval.py
   python evals\run_research_eval.py
   python evals\run_research_discovery_eval.py
   python evals\run_research_capture_eval.py
   python evals\run_price_eval.py
   python evals\run_price_candidate_discovery_eval.py
   python evals\run_price_capture_eval.py
   python evals\run_capture_adapter_eval.py
   python evals\run_cross_skill_schema_eval.py
   ```

3. Generated-artifact schema and run validators:

   Use the generated-artifact validation block in `docs/testing.md` after the eval suite creates `evals/.tmp/`.

4. Local plugin validation:

   ```powershell
   python C:\Users\62406\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py "E:\Inward Eyes"
   ```

5. Diff hygiene:

   ```powershell
   git diff --check
   ```

## Future Queue at M11 Close

The following phases were planned-only context at M11 close and were later completed in `docs/planning/archive/m12-m20-post-rc-expansion-closeout.md`:

- M12: adapter matrix.
- M13: real-world evals.
- M14: privacy/security.
- M15: site profiles.
- M16: review UI.
- M17: distribution.
- M18-M19: batch, retry, and run database.
- M20: exporters and extensions.

## Closeout Requirements

Do not mark M11 complete until:

- All stale currentness docs and active/archive lifecycle inconsistencies are resolved.
- All v1.0 contract docs exist and agree with schemas, validators, and skills.
- All gates in this plan have been run or explicitly recorded as blocked/skipped with reasons.
- `docs/planning/archive/m11-v1-release-risk-report.md` has been updated with actual results.
