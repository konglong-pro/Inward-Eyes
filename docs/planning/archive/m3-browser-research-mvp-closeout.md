# M3 browser-research MVP Closeout

## What Shipped

- `browser-research` skill.
- Local `browser_research_runner.py`.
- Research claim and report schemas.
- Claim ledger, source CSV, source notes, report rendering, and missing source report.
- Claim coverage validator.
- Synthetic pass and unsupported-claim fail evals.

## Frozen Behavior

- The first M3 slice consumes local research input JSON.
- Real browser/MCP capture remains future work.
- Unsupported key claims fail validation.
- Inferred support requires manual review.

## Tests / Gates

Passed before moving to M4/M5:

- Python compile check for M3 scripts.
- `python evals\run_research_eval.py`
- Research report and manifest schema checks.
- Plugin validator.

## Known Limitations

- No real browser source discovery or capture adapter is implemented for research.
- No broad search workflow is implemented.
- The minimal JSON schema validator is not a full JSON Schema engine.
