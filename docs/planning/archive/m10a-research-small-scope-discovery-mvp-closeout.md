# M10A browser-research Small-Scope Discovery MVP Closeout

## What Shipped

- M10A discovery orchestration for `browser-research`.
- `scripts/research_discovery_runner.py` to:
  - accept scoped discovery input;
  - enforce research question, max source count, allowed domains/source types, excluded domains/source types, recency, search query context, and selection-rationale scope;
  - write discovery logs;
  - select only in-scope public sources;
  - generate `capture/discovery-selected-sources.json`;
  - run the existing M8 `research_capture_runner.py`;
  - preserve M3/M8 claim ledger and source validation as the research source of truth.
- `scripts/inward_eyes/discovery.py` for discovery log creation, Markdown rendering, public URL checks, prompt-injection candidate rejection, hard-cap checks, and discovery validation.
- `scripts/validation/validate_research_discovery.py` for standalone discovery run validation.
- Browser-research validation now includes discovery checks when `artifacts/discovery-log.json` exists.
- Schemas:
  - `schemas/research_discovery_input.schema.json`
  - `schemas/discovery_log.schema.json`
- Synthetic M10A eval coverage:
  - bounded 3-source discovery;
  - hard max-source cap failure;
  - rejected source with reason;
  - unsupported claim failure after discovery;
  - syndicated duplicate marked not independent;
  - prompt-injection search result rejected as source instruction.
- CI, testing docs, contracts, phase docs, and `browser-research` skill docs updated.

## Frozen Behavior

- M10A is for `browser-research` only.
- Discovery requires explicit task scope.
- Default maximum selected sources is 5.
- Hard maximum selected sources is 20.
- Allowed domains or allowed source types are required.
- Search queries or equivalent candidate-query context are required.
- Public HTTP(S) sources only.
- Selected sources require selection rationale.
- Rejected candidates remain in the discovery log with reasons.
- Selected sources are captured through the M8 provided-URL pipeline.
- Existing claim ledger validation remains enforced.
- If no claim ledger is provided, the M8 fallback creates an explicit unknown/no-synthesis claim instead of inventing findings.

## Contracts Updated

- `docs/contracts/browser-operation-contract.md`: M10A small-scope discovery boundary.
- `docs/contracts/evidence-contract.md`: discovery log and selected-source evidence requirements.
- `docs/contracts/schemas-and-validation-contract.md`: discovery schemas and validation rules.
- `docs/contracts/safety-contract.md`: M10A approval boundary.

## Tests / Gates

Passed during closeout:

- `python -m py_compile scripts\page_to_md_runner.py scripts\capture\playwright_mcp_capture.py scripts\capture\page_to_md_browser_runner.py scripts\capture\current_chrome_capture.py scripts\capture\current_chrome_page_to_md_runner.py scripts\research_discovery_runner.py scripts\research_capture_runner.py scripts\price_capture_runner.py scripts\markdown\render_page_md.py scripts\validation\validate_page_to_md.py scripts\validation\validate_page_capture.py scripts\validation\validate_json_schema.py scripts\validation\classify_browser_action.py scripts\validation\validate_research_discovery.py scripts\validation\validate_browser_research.py scripts\validation\validate_price_compare.py scripts\inward_eyes\__init__.py scripts\inward_eyes\capture.py scripts\inward_eyes\discovery.py scripts\inward_eyes\html_extract.py scripts\inward_eyes\io.py scripts\inward_eyes\markdown.py scripts\inward_eyes\safety.py scripts\inward_eyes\validation.py scripts\inward_eyes\research.py scripts\inward_eyes\price.py scripts\browser_research_runner.py scripts\price_compare_runner.py evals\run_eval.py evals\run_safety_eval.py evals\run_research_eval.py evals\run_research_discovery_eval.py evals\run_research_capture_eval.py evals\run_price_eval.py evals\run_price_capture_eval.py evals\run_capture_adapter_eval.py evals\run_cross_skill_schema_eval.py`
- `python evals\run_eval.py`
- `python evals\run_safety_eval.py`
- `python evals\run_research_eval.py`
- `python evals\run_research_discovery_eval.py`
- `python evals\run_price_eval.py`
- `python evals\run_research_capture_eval.py`
- `python evals\run_price_capture_eval.py`
- `python evals\run_capture_adapter_eval.py`
- `python evals\run_cross_skill_schema_eval.py`
- `python scripts\validation\validate_json_schema.py --schema schemas\research_discovery_input.schema.json --json evals\.tmp\research-discovery\eval-bounded-three-sources\input.json`
- `python scripts\validation\validate_json_schema.py --schema schemas\discovery_log.schema.json --json evals\.tmp\research-discovery\eval-bounded-three-sources\artifacts\discovery-log.json`
- `python scripts\validation\validate_json_schema.py --schema schemas\research_report.schema.json --json evals\.tmp\research-discovery\eval-bounded-three-sources\artifacts\claims.json`
- `python scripts\validation\validate_json_schema.py --schema schemas\run_manifest.schema.json --json evals\.tmp\research-discovery\eval-bounded-three-sources\manifest.json`
- `python scripts\validation\validate_json_schema.py --schema schemas\validation_report.schema.json --json evals\.tmp\research-discovery\eval-bounded-three-sources\validation\discovery-validation-report.json`
- `python scripts\validation\validate_json_schema.py --schema schemas\validation_report.schema.json --json evals\.tmp\research-discovery\eval-bounded-three-sources\validation\claim-coverage-report.json`
- `python scripts\validation\validate_research_discovery.py evals\.tmp\research-discovery\eval-bounded-three-sources`
- `python scripts\validation\validate_browser_research.py evals\.tmp\research-discovery\eval-bounded-three-sources`
- `python C:\Users\62406\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py "E:\Inward Eyes"`
- `git diff --check`

`git diff --check` exited 0 and reported only Git line-ending normalization warnings on touched Markdown files.

## Known Limitations

- Discovery ranking is deterministic and fixture/input-driven in this MVP; it does not implement a live search API client.
- Real public-search quality, ranking, and snippet fidelity remain unproven beyond synthetic fixtures.
- M10A does not synthesize claims from source text.
- M10A does not perform recursive crawling, monitoring, scheduled runs, login-required discovery, ecommerce candidate discovery, or anti-bot/CAPTCHA bypass.
- Live browser capture remains environment-dependent through the existing M8/M6 adapter path.

## Deferred Work

- Live search-provider integration behind the same bounded discovery contract.
- Assisted claim drafting with explicit review gates.
- Broader source quality ranking and duplicate clustering.
- Product/ecommerce discovery remains out of scope for M10A.
