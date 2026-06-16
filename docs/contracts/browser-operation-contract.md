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

## Current Chrome Boundary

Current Chrome capture is allowed only for one user-approved visible page. The task scope is the current page itself, not the browser profile.

Allowed observations:

- Copy the visible URL.
- Read visible title and page text.
- Capture a DOM, accessibility, or structured snapshot of the approved page.
- Save a screenshot only after privacy review/redaction policy is applied.

Forbidden observations and actions:

- Listing or scanning tabs.
- Opening account menus, inboxes, orders, dashboards, settings, payment, security, messages, comments, follows, carts, checkout, or coupon claim flows.
- Exporting browser profiles, cookies, tokens, HAR, local storage, session storage, passwords, payment data, network logs, or browser history.
- Mutating account, cart, checkout, coupon, posting, messaging, follow, comment, security, or payment state.

## Provided-URL Research Boundary

For M8 `browser-research`, browser operation is limited to source URLs explicitly provided by the user or already approved current-browser captures in task scope.

Allowed:

- Open/capture each provided URL once for source evidence.
- Read task-relevant page text or structured snapshots.
- Save per-source `page_capture.json`, `SourceRecord`, and required screenshot evidence.

Forbidden:

- Search queries.
- Source discovery.
- Following related links or pagination.
- Multi-hop browsing.
- Capturing search result pages at scale.
- Capturing comments, ads, recommendations, or marketing copy as factual sources by default.

## Small-Scope Research Discovery Boundary

For M10A `browser-research`, discovery may identify public source candidates only inside explicit user-approved task scope.

Required scope:

- Research question.
- Maximum source count.
- Allowed domains or allowed source types.
- Excluded domains or source types when relevant.
- Recency requirement when relevant.
- Search queries or equivalent candidate-query context.

Limits:

- Default maximum is 5 selected sources.
- Hard maximum is 20 selected sources.
- Public HTTP(S) sources only.
- Capture selected sources only.
- Save a discovery log before treating selected URLs as research sources.
- Every selected source must have selection rationale.

Allowed:

- Search public pages within the approved task scope.
- Record candidate title/snippet when available.
- Accept or reject candidates with reasons.
- Capture accepted source URLs once through the M8 provided-URL capture pipeline.

Forbidden:

- Broad crawling.
- Recursive link following beyond approved selected sources.
- Login-required source discovery.
- Private data capture.
- Search or discovery for ecommerce candidates.
- Capturing every search result by default.
- Stealth browsing, proxies, CAPTCHA handling, anti-bot bypass, or access-control bypass.

## Product-URL Price Boundary

For M9 `price-compare`, browser operation is limited to ecommerce product URLs explicitly provided by the user.

Allowed:

- Open/capture each approved product URL once for quote evidence.
- Read task-relevant product identity, selected specs, seller, stock, region, currency, and visible price components.
- Save per-source `page_capture.json`, `SourceRecord`, and required product-page screenshot evidence.
- Expand read-only product/spec/detail sections when that does not mutate account, cart, coupon, checkout, address, or payment state.

Forbidden:

- Platform search or keyword search.
- Product discovery.
- Following recommendation links.
- Claiming coupons.
- Adding to cart.
- Proceeding to checkout.
- Changing delivery address, region, account, payment, or security state without explicit future approval.
- Stealth browsing, proxies, anti-bot bypass, CAPTCHA submission, or access-control bypass.

## Approved Product Candidate Discovery Boundary

For M10B `price-compare`, browser operation is limited to explicitly approved ecommerce platforms/domains and a user-provided product target with required specs.

Required scope:

- Target product.
- Required product specs.
- Approved platforms.
- Approved domains.
- Maximum candidates per platform.
- Region.
- Currency.
- Excluded sellers or seller preferences when relevant.

Limits:

- Default maximum is 3 candidates per platform.
- Hard maximum is 20 total candidates.
- Candidate discovery records only product-page candidates.
- Quote extraction is delegated to the M9 product-URL price capture pipeline.
- Product identity and required specs remain separate throughout candidate assessment and quote capture.
- Candidate records must include match confidence and selection/rejection/review rationale.

Allowed:

- Search or inspect approved ecommerce platforms/domains within the task scope.
- Record visible product name, visible specs, seller, condition, provisional visible price, URL, and match confidence.
- Deduplicate product URLs.
- Route low-confidence, incomplete, seller-mismatched, or condition-mismatched candidates to manual review.
- Pass high-confidence candidates to M9 quote capture only when policy allows automatic approval, or when explicitly approved.

Forbidden:

- Broad web product search.
- Unlimited platform crawling.
- Recursive link following beyond approved candidate pages.
- Following recommendation carousels or related-product links.
- Login-required discovery.
- Coupon claiming.
- Add-to-cart.
- Checkout.
- Address, region, payment, security, or account mutation.
- Marketplace-wide monitoring.
- Stealth browsing, proxies, CAPTCHA handling, anti-bot bypass, or access-control bypass.

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
