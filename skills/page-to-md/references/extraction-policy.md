# page-to-md Extraction Policy

## Priority Order

1. Structured page capture or DOM/accessibility snapshot.
2. Local HTML file.
3. Browser-visible selected content plus URL.
4. Screenshot fallback, marked partial.

## Page Types

- `article`
- `blog`
- `docs`
- `x_thread`
- `forum_thread`
- `product_page`
- `unknown`

## Main Content Rules

Include:

- Main title.
- Author and publish time only when present.
- Headings.
- Paragraphs.
- Lists.
- Quotes.
- Code blocks.
- Tables.
- Images with alt text or captions.

Exclude:

- Navigation.
- Footer.
- Cookie banners.
- Advertisements.
- Recommendations.
- Unrelated comments.
- Account menus.
- Share buttons.

## Unknowns

Unknown metadata must stay explicit. Use warnings such as:

- `author_not_found`
- `published_at_not_found`
- `canonical_url_not_found`
- `page_type_unknown`
- `screenshot_required_but_missing`
