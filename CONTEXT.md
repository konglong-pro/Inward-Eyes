# CONTEXT.md

## Project One-Liner

Inward Eyes is an evidence-first Codex plugin for browser-based page conversion, research, and price comparison.

## Core Terms

**Browser operation**: The act of using Chrome, Browser Use, Playwright, Chrome DevTools, or Computer Use to observe or interact with a page.

**Evidence-backed output**: An artifact whose claims or fields can be traced to a URL, timestamp, screenshot, source record, and run manifest.

**Run manifest**: The top-level record for one execution, including inputs, artifacts, evidence, warnings, validation status, and manual review requirements.

**SourceRecord**: Shared source object used by page conversion, research, and price comparison.

**Claim ledger**: Structured list of research claims with source support, confidence, fact/inference/unknown type, and notes.

**PriceRecord**: Structured record for one product quote, including product identity, specs, seller, region, price components, availability, source, and validation.

**Read-only mode**: Default operation mode that allows observation, extraction, screenshots, and local file generation but forbids account-mutating actions.

**Structured extraction**: DOM, accessibility snapshot, schema, or page text extraction that can be validated more reliably than pure visual reading.

**Visual fallback**: Screenshot or GUI-based reading used only when structured extraction is unavailable or unreliable.

**Site profile**: Future documented knowledge about a specific platform's page patterns, price semantics, metadata conventions, or failure modes.

## Avoid Ambiguous Terms

- Avoid saying "replace crawler"; say "small-scale evidence-backed browser operation".
- Avoid saying "scrape everything"; say "extract task-scoped fields with permission and evidence".
- Avoid saying "price"; specify list price, sale price, coupon price, shipping fee, estimated total, and availability.

See `docs/glossary/core.md` for expanded relationships.
