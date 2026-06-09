# Browser Operation Contract

## Purpose

Define when Inward Eyes may use browser tools and how it should choose among them.

## Core Rule

Browser tools are observation and operation layers. They are not the product core. Structured records, evidence, validation, and rendered artifacts are the product core.

## Routing Matrix

| Scenario | Preferred | Secondary | Fallback | Reason |
| --- | --- | --- | --- | --- |
| Logged-in account-state page | Codex Chrome extension/current Chrome | Chrome DevTools MCP with explicit scope | Computer Use | Preserve login state and avoid re-authentication |
| Public article/docs page | Playwright MCP or Chrome DevTools MCP | Browser Use | Computer Use | Structured extraction is repeatable |
| SPA, lazy-load, infinite scroll | Playwright MCP or Chrome DevTools MCP | Browser Use | Computer Use | Requires waiting, scrolling, and snapshots |
| X-like thread/forum thread | Logged-in Chrome when required plus screenshots | Chrome DevTools MCP | Computer Use | Dynamic content and metadata are easy to misread |
| Ecommerce price comparison | Logged-in Chrome when account/region affects price plus structured snapshot and screenshot | Playwright MCP | Computer Use | Price depends on region, seller, coupon, and stock |
| Local development page | Codex in-app browser or Playwright MCP | Chrome DevTools MCP | Computer Use | No real account state needed |
| Legacy GUI or broken DOM | Computer Use | User-assisted manual review | Stop | Structured tools are unreliable |

## Principles

- Prefer structured extraction over visual extraction.
- Prefer least-privileged tool access.
- Scope browser access to the task domain and current page set.
- Use Computer Use only when structured browser access cannot satisfy the task.
- Keep browser history access off by default unless the user explicitly asks and the task requires it.
- Do not connect to all open tabs by default.

## Tool Notes

Chrome extension/current Chrome is suitable when logged-in browser state is required.

Playwright/Chrome DevTools style tools are suitable when DOM, accessibility snapshots, screenshots, and repeatable navigation are needed.

Browser Use is optional and should not be the first default dependency for this project because the initial scope is read-only, evidence-backed operation rather than stealth, CAPTCHA, proxy, or anti-bot workflows.

Computer Use is a GUI fallback. It can affect the user's desktop state and must be tightly scoped.

## Required Browser Task Setup

Before using a browser tool, the skill must know:

- Target URL or current page.
- Allowed domain(s).
- Whether login state is required.
- Whether screenshots are required.
- Output directory.
- Any user-approved Yellow actions.

## Stop Conditions

Stop and ask the user when:

- A page asks for credentials, payment, CAPTCHA, or identity verification.
- Required data is behind a forbidden Red action.
- Product/spec identity is ambiguous and affects conclusions.
- The browser shows unrelated private data.
- The task would require changing account, cart, coupon, shipping address, or payment state.
