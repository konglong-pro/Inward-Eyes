# Pluginization

## Current Package Shape

Current release class: local deterministic MVP. The plugin can process local input JSON/HTML and render validated artifacts; it does not yet operate a live browser.

The local plugin package is this repository root. It includes:

- `.codex-plugin/plugin.json`
- `skills/page-to-md/`
- `skills/browser-research/`
- `skills/price-compare/`
- `schemas/`
- deterministic Python scripts under `scripts/`
- synthetic evals under `evals/`
- examples under `examples/`
- contracts and operating docs under `docs/`

## Current Policy

- Capabilities remain read-only.
- Runtime outputs stay outside the plugin package.
- Browser/MCP dependencies are optional and not bundled yet.
- Marketplace installation is not configured in this slice.
- Do not create marketplace entries unless explicitly requested.

## Validation

Run from `E:\Inward Eyes`:

```bash
python C:\Users\62406\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py "E:\Inward Eyes"
```

The local plugin is considered package-ready for this MVP only when page, research, price, schema, and plugin validation gates pass.
