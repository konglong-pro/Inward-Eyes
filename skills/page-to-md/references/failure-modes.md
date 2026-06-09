# page-to-md Failure Modes

## Validation Failure

Do not present a final complete artifact when validation fails. Report the failed checks and paths.

## Partial Extraction

Mark output partial when:

- Only screenshots are available.
- Main content cannot be confidently separated from boilerplate.
- Page requires login but no evidence screenshot exists.
- Dynamic content may not have fully loaded.
- Metadata conflicts.

## Manual Review Required

Require manual review when:

- Personal data appears in evidence.
- Multiple titles, authors, or publish dates conflict.
- X-like or forum thread author/time is ambiguous.
- Ecommerce product pages show account-specific price or region.
