# Markdown Output Rules

## Required Front Matter

`page.md` must include YAML-style front matter with:

- `title`
- `author`
- `published_at`
- `source_url`
- `canonical_url`
- `accessed_at`
- `page_type`
- `extraction_method`
- `warnings`

## Body

- Use exactly one primary H1.
- Preserve source heading hierarchy where possible.
- Use blockquotes for quoted source content.
- Use fenced code blocks for code.
- Use Markdown tables only when table structure is reliable.
- Use image Markdown with alt text where available.

## Source Note

Immediately after H1, include:

```md
> Source: <url>
> Accessed: <timestamp>
> Author: <author-or-Unknown>
> Published: <timestamp-or-Unknown>
```

## Extraction Notes

Include extraction notes only when warnings or partial extraction occurred.
