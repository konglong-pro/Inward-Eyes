# Site Profile Contract

## Purpose

Define advisory extraction profiles for known page shapes without expanding browser permissions.

## Applies To

- `profiles/site_profiles.json`
- `schemas/site_profiles.schema.json`
- `scripts/site_profile_runner.py`
- Future extraction logic that chooses page-specific parsing hints

## Rules

- Site profiles are extraction guidance, not authorization.
- Safety, browser-operation, evidence, artifact, and error-status contracts always override a profile.
- A profile must never request or imply crawler behavior, anti-bot bypass, stealth, proxy use, login automation, cart, checkout, coupon claiming, account mutation, or browser profile/session export.
- "Site profile" is not a browser profile. Browser profiles, cookies, tokens, HAR logs, local storage, session storage, passwords, payment data, and unrelated account data remain forbidden evidence.
- Unknown or unmatched sites must degrade to generic extraction or manual review. They must not cause invented fields.
- Profile use must be traceable through generated artifacts when a runner applies a profile.

## Required Shape

The default catalog is `profiles/site_profiles.json` and validates against `schemas/site_profiles.schema.json`.

Each profile records:

- `profile_id` and `profile_version`.
- Workflow and page-type applicability.
- Domain, URL, or site-name matching hints.
- Included and excluded content scope.
- Required evidence and screenshot policy.
- Allowed read-only actions and forbidden actions.
- Risk flags that should drive warnings or manual review.

## Validation

Release gates must run:

```powershell
python scripts\validation\validate_json_schema.py --schema schemas\site_profiles.schema.json --json profiles\site_profiles.json
python evals\run_site_profile_eval.py
```

Workflow validators remain authoritative for final artifacts.
