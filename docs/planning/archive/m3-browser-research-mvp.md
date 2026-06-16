---
doc_type: phase_plan
phase_id: m3_browser_research_mvp
title: browser-research minimum viable workflow
status: completed
canonical: true
related_contracts:
  - docs/contracts/evidence-contract.md
  - docs/contracts/browser-operation-contract.md
  - docs/contracts/schemas-and-validation-contract.md
  - docs/contracts/safety-contract.md
related_adrs:
  - docs/adr/0001-evidence-first-browser-workflows.md
---

# M3 browser-research MVP

## Status

Completed. The user approved starting M2-after work on 2026-06-09; the M3 MVP closeout is `docs/planning/archive/m3-browser-research-mvp-closeout.md`.

## Scope

Implement the smallest deterministic `browser-research` loop after M0-M2:

- Local research input JSON.
- One `SourceRecord` per source under `evidence/source-###/`.
- `claims.json` as the structured claim ledger.
- `report.md`, `sources.csv`, and `source_notes.md` rendered from structured data.
- `claim-coverage-report.json` and `missing-sources.md` validation outputs.
- Synthetic passing and failing eval fixtures.

Real browser capture, MCP adapters, broad discovery, price comparison, and plugin distribution remain out of scope for this slice.

## Success Criteria

- Every key fact or inference has source IDs and support entries.
- Claim type is one of `fact`, `inference`, or `unknown`.
- Direct and inferred support remain distinct.
- Single-source findings are marked.
- Unsupported key claims fail validation.
- `claims.json`, `sources.csv`, `report.md`, source records, and manifest paths agree.

## Current Gates

- `python -m py_compile scripts\browser_research_runner.py scripts\validation\validate_browser_research.py scripts\inward_eyes\research.py scripts\inward_eyes\validation.py evals\run_research_eval.py`
- `python evals\run_research_eval.py`
- `python scripts\validation\validate_json_schema.py --schema schemas\research_report.schema.json --json evals\.tmp\browser-research\eval-evidence-backed-research\artifacts\claims.json`
- `python scripts\validation\validate_json_schema.py --schema schemas\run_manifest.schema.json --json evals\.tmp\browser-research\eval-evidence-backed-research\manifest.json`
