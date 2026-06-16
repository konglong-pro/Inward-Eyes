# Pluginization

## Current Package Shape

Current release class: post-M12-M20 local operations hardening. The plugin can process local input JSON/HTML and existing Inward Eyes page capture JSON, and the repository includes optional adapter-boundary wrappers for approved public/current-page captures, bounded discovery, local review/index/export utilities, and a package dry-run. Marketplace publication is not implemented.

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
- M12-M20 did not add new skills or browser backends.
- Package dry-run is local archive validation only.
- Marketplace installation is not configured in this repository.
- Do not create marketplace entries unless explicitly requested.

## Validation

Run from `E:\Inward Eyes`:

```bash
python C:\Users\62406\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py "E:\Inward Eyes"
```

The local plugin is considered v1.0 release-candidate-ready only when page, research, price, discovery, capture adapter, schema, workflow validator, and plugin validation gates pass.

Local package dry-run:

```bash
python scripts\plugin_package.py --output-dir dist
```

The generated `dist/` output is ignored and should not be committed.
