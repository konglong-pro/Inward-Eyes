# ADR 0001: Evidence-First Browser Workflows

## Status

Accepted for planning.

## Context

Codex can operate browsers through multiple surfaces, including logged-in Chrome, structured browser tooling, in-app browser workflows, and GUI control. A naive design would expose these tools directly and ask Codex to produce Markdown, reports, or price tables.

That design is not stable enough. It can produce outputs that look plausible but are hard to audit:

- Markdown without source fidelity.
- Research reports with broken fact chains.
- Price tables with mixed product specifications.
- Screenshots without machine-readable validation.

## Decision

Inward Eyes will be an evidence-first Codex plugin, not a general browser agent.

Codex remains the agent. Inward Eyes provides:

- Focused skills.
- Shared schemas.
- Deterministic scripts.
- Browser tool routing policy.
- Safety rules.
- Evidence manifests.
- Validation and evals.

All human-readable artifacts should be rendered from validated structured data wherever practical.

## Consequences

Positive:

- Outputs are auditable.
- Skills can share source and evidence models.
- Testing can target schemas and consistency, not only prose quality.
- Browser tools can be swapped without changing output contracts.

Tradeoffs:

- More upfront schema and validation work.
- Slower MVP than a prompt-only browser automation workflow.
- Some pages will be marked as partial or manual-review instead of being forced into a clean artifact.

## Non-Goals

- High-throughput crawling.
- Anti-bot bypass.
- Fully autonomous account mutation.
- Universal browser agent behavior.
