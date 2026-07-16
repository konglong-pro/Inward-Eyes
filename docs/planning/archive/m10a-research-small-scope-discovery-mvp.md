---
doc_type: phase_plan
phase_id: m10a_research_small_scope_discovery_mvp
title: browser-research small-scope public source discovery MVP
status: completed
canonical: true
related_contracts:
  - docs/contracts/browser-operation-contract.md
  - docs/contracts/evidence-contract.md
  - docs/contracts/schemas-and-validation-contract.md
  - docs/contracts/safety-contract.md
related_adrs:
  - docs/adr/0001-evidence-first-browser-workflows.md
closeout: docs/planning/archive/m10a-research-small-scope-discovery-mvp-closeout.md
---

# M10A browser-research Small-Scope Discovery MVP

## Goal

Add a small, bounded, user-approved source discovery workflow for `browser-research`.

M10A may identify a limited number of public source candidates, select only in-scope sources with rationale, capture selected sources, and then run the existing M8 browser-backed research pipeline. The existing browser-research runner, claim ledger, source records, and validation remain the source of truth for research outputs.

## Scope

- Public web sources only.
- Small-scope discovery only.
- Default maximum source count: 5.
- Hard maximum source count: 20.
- User-approved task scope must include:
  - research question;
  - maximum source count;
  - allowed domains or allowed source types;
  - excluded domains or source types when relevant;
  - recency requirement when relevant;
  - search queries or equivalent candidate-query context.
- Capture selected sources only, not every search result.
- Save `artifacts/discovery-log.json` and `artifacts/discovery-log.md`.
- Every selected source must have selection rationale.
- Every selected source must become a `SourceRecord`.
- Every key claim still requires claim ledger support.

## Interfaces Touched

- `scripts/research_discovery_runner.py`: bounded discovery orchestration and M8 handoff.
- `scripts/inward_eyes/discovery.py`: discovery log creation, Markdown rendering, scope checks, and discovery validation.
- `scripts/validation/validate_research_discovery.py`: standalone discovery run validation.
- `scripts/inward_eyes/validation.py`: browser-research validation includes discovery checks when a discovery log is present.
- `schemas/research_discovery_input.schema.json`: scoped discovery input shape.
- `schemas/discovery_log.schema.json`: discovery log artifact shape.
- `evals/run_research_discovery_eval.py`: synthetic M10A coverage.

## Output Shape

```text
<run_dir>/
  input.json
  manifest.json
  artifacts/
    discovery-log.json
    discovery-log.md
    report.md
    claims.json
    sources.csv
    source_notes.md
  capture/
    discovery-selected-sources.json
    source-001/page_capture.json
  evidence/
    source-001/source_record.json
    source-001/screenshots/
  validation/
    discovery-validation-report.json
    claim-coverage-report.json
    missing-sources.md
    warnings.md
```

## Discovery Log Requirements

Each discovery candidate record must include:

- query used;
- candidate URL;
- title or snippet when available;
- accepted or rejected status;
- reason for selection or rejection;
- timestamp.

Selected sources additionally require:

- assigned `source_id`;
- selection rationale;
- source type;
- domain;
- matching `SourceRecord` after capture.

## Out of Scope

- Broad crawling.
- Recursive link following beyond approved selected sources.
- Login-required source discovery.
- Private data capture.
- Price comparison.
- Ecommerce candidate discovery.
- Stealth, proxy, CAPTCHA, or anti-bot bypass.
- Mass scraping.
- Monitoring or scheduled runs.
- Browser-backed claim synthesis without explicit claim ledger review.

## Validation

M10A validation must fail when:

- `max_sources` is greater than 20;
- selected source count exceeds `max_sources`;
- a selected source has no selection rationale;
- a selected source has no `SourceRecord`;
- a selected source is non-public, login-required, excluded, or outside allowed source scope;
- discovery records recursive link following;
- a prompt-injection search result is accepted as an instruction or selected source;
- an unsupported key claim would otherwise pass.

M10A validation may pass with manual review when:

- source independence is unknown;
- sources are non-independent or syndicated and claims are marked `single_source=true`;
- source capture failures are auditable and no key claim relies on failed source evidence.

## Tests / Gates

- `python -m py_compile scripts\research_discovery_runner.py scripts\validation\validate_research_discovery.py scripts\inward_eyes\discovery.py scripts\inward_eyes\validation.py evals\run_research_discovery_eval.py`
- `python evals\run_eval.py`
- `python evals\run_safety_eval.py`
- `python evals\run_research_eval.py`
- `python evals\run_research_discovery_eval.py`
- `python evals\run_price_eval.py`
- Discovery schema checks:
  - `python scripts\validation\validate_json_schema.py --schema schemas\research_discovery_input.schema.json --json evals\.tmp\research-discovery\eval-bounded-three-sources\input.json`
  - `python scripts\validation\validate_json_schema.py --schema schemas\discovery_log.schema.json --json evals\.tmp\research-discovery\eval-bounded-three-sources\artifacts\discovery-log.json`
- Existing research report, run manifest, and validation report schema checks.
- `python scripts\validation\validate_research_discovery.py evals\.tmp\research-discovery\eval-bounded-three-sources`
- `python scripts\validation\validate_browser_research.py evals\.tmp\research-discovery\eval-bounded-three-sources`
- `python C:\Users\62406\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py "E:\Inward Eyes"`
- `git diff --check`

## Closeout Requirements

- Create `docs/planning/archive/m10a-research-small-scope-discovery-mvp-closeout.md`.
- Record shipped behavior, frozen boundaries, eval coverage, gates run, and known limitations.
