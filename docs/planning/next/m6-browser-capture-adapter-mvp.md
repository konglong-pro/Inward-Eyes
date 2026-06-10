---
doc_type: phase_plan
phase_id: m6_browser_capture_adapter_mvp
title: browser capture adapter MVP
status: next
canonical: true
related_contracts:
  - docs/contracts/capture-adapter-contract.md
  - docs/contracts/browser-operation-contract.md
  - docs/contracts/evidence-contract.md
  - docs/contracts/safety-contract.md
---

# M6 browser capture adapter MVP

## Goal

Implement one real browser capture adapter that produces `page_capture.json` for the existing local deterministic workflows.

## Scope

Start with exactly one backend and one workflow:

- Backend: one approved browser adapter, selected before implementation.
- Workflow: `page-to-md`.
- Output boundary: `page_capture.json`.
- Validation: existing page-to-md runner and eval gates.

Do not implement research discovery, price comparison capture, broad crawling, account mutation, marketplace distribution, or multiple adapters in this slice.

## Acceptance Criteria

- Adapter writes contract-shaped `page_capture.json`.
- Captures URL, title, access time, capture method, content payload, screenshot policy, privacy flags, and warnings.
- Does not save cookies, tokens, HAR files, browser profiles, passwords, payment details, or unrelated account data.
- Red actions are refused.
- Unapproved Yellow actions stop the run or produce `aborted_by_policy`.
- The captured output can be passed into `python scripts\page_to_md_runner.py --input <page_capture.json>`.

## Out of Scope

- Browser research source discovery.
- Ecommerce quote extraction.
- Multiple browser backends.
- Logged-in private data export.
- Stealth browsing, proxies, anti-bot bypass, CAPTCHA handling.
