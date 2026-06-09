from __future__ import annotations

import re
from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin

BOILERPLATE_HINTS = (
    "nav",
    "footer",
    "header",
    "cookie",
    "banner",
    "advert",
    "ads",
    "recommend",
    "related",
    "sidebar",
    "subscribe",
    "newsletter",
    "share",
)

SKIP_TAGS = {
    "script",
    "style",
    "noscript",
    "svg",
    "nav",
    "footer",
    "header",
    "form",
    "button",
    "select",
    "input",
    "textarea",
}

BLOCK_TAGS = {"p", "li", "blockquote", "pre", "td", "th", "figcaption"}
HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", unescape(text)).strip()


def _attr_value(attrs: list[tuple[str, str | None]], name: str) -> str | None:
    for key, value in attrs:
        if key.lower() == name and value:
            return value
    return None


def _has_boilerplate_hint(attrs: list[tuple[str, str | None]]) -> bool:
    haystack = " ".join(value or "" for _, value in attrs).lower()
    return any(hint in haystack for hint in BOILERPLATE_HINTS)


class PageHTMLParser(HTMLParser):
    def __init__(self, base_url: str | None = None) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.title_text: str | None = None
        self.meta: dict[str, str] = {}
        self.links: dict[str, str] = {}
        self.blocks: list[dict[str, Any]] = []
        self.time_values: list[str] = []
        self._tag_stack: list[str] = []
        self._skip_depth = 0
        self._current_tag: str | None = None
        self._current_attrs: list[tuple[str, str | None]] = []
        self._buffer: list[str] = []
        self._title_buffer: list[str] = []
        self._table_rows: list[list[str]] = []
        self._current_row: list[str] = []
        self._in_table = False
        self._in_row = False
        self._in_cell = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        self._tag_stack.append(tag)

        if tag in SKIP_TAGS or _has_boilerplate_hint(attrs):
            self._skip_depth += 1
            return

        if tag == "meta":
            key = _attr_value(attrs, "property") or _attr_value(attrs, "name")
            value = _attr_value(attrs, "content")
            if key and value:
                self.meta[key.lower()] = _clean_text(value)
            return

        if tag == "link":
            rel = (_attr_value(attrs, "rel") or "").lower()
            href = _attr_value(attrs, "href")
            if rel and href:
                self.links[rel] = urljoin(self.base_url or "", href)
            return

        if tag == "img" and self._skip_depth == 0:
            src = _attr_value(attrs, "src")
            alt = _attr_value(attrs, "alt")
            if src:
                self.blocks.append(
                    {
                        "type": "image",
                        "src": urljoin(self.base_url or "", src),
                        "alt": _clean_text(alt or ""),
                    }
                )
            return

        if tag == "time":
            datetime_value = _attr_value(attrs, "datetime")
            if datetime_value:
                self.time_values.append(_clean_text(datetime_value))

        if tag == "table":
            self._flush_current()
            self._in_table = True
            self._table_rows = []
            return

        if tag == "tr" and self._in_table:
            self._in_row = True
            self._current_row = []
            return

        if tag in {"td", "th"} and self._in_table:
            self._in_cell = True
            self._start_capture(tag, attrs)
            return

        if tag in HEADING_TAGS or tag in BLOCK_TAGS:
            self._start_capture(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()

        if self._skip_depth > 0:
            self._skip_depth -= 1
            if self._tag_stack:
                self._tag_stack.pop()
            return

        if tag == "title":
            text = _clean_text("".join(self._title_buffer))
            if text:
                self.title_text = text
            self._title_buffer = []

        if tag in {"td", "th"} and self._in_table and self._in_cell:
            text = _clean_text("".join(self._buffer))
            self._buffer = []
            self._current_tag = None
            self._in_cell = False
            self._current_row.append(text)
        elif tag == "tr" and self._in_table and self._in_row:
            self._in_row = False
            if any(cell for cell in self._current_row):
                self._table_rows.append(self._current_row)
        elif tag == "table" and self._in_table:
            self._in_table = False
            if self._table_rows:
                self.blocks.append({"type": "table", "rows": self._table_rows})
            self._table_rows = []
        elif tag == self._current_tag:
            self._flush_current()

        if self._tag_stack:
            self._tag_stack.pop()

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        if self._tag_stack and self._tag_stack[-1] == "title":
            self._title_buffer.append(data)
            return
        if self._current_tag:
            self._buffer.append(data)

    def _start_capture(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._flush_current()
        self._current_tag = tag
        self._current_attrs = attrs
        self._buffer = []

    def _flush_current(self) -> None:
        if not self._current_tag:
            return
        text = _clean_text("".join(self._buffer))
        tag = self._current_tag
        self._current_tag = None
        self._buffer = []
        if not text:
            return
        if tag in HEADING_TAGS:
            self.blocks.append({"type": "heading", "level": int(tag[1]), "text": text})
        elif tag == "blockquote":
            self.blocks.append({"type": "quote", "text": text})
        elif tag == "pre":
            self.blocks.append({"type": "code", "text": text})
        elif tag == "li":
            self.blocks.append({"type": "list_item", "text": text})
        elif tag == "figcaption":
            self.blocks.append({"type": "paragraph", "text": text})
        elif not self._in_table:
            self.blocks.append({"type": "paragraph", "text": text})


def extract_html(html: str, source_url: str | None = None) -> dict[str, Any]:
    parser = PageHTMLParser(base_url=source_url)
    parser.feed(html)

    page_title = (
        parser.meta.get("og:title")
        or parser.meta.get("twitter:title")
        or parser.title_text
    )
    canonical_url = parser.links.get("canonical") or parser.meta.get("og:url")
    author = parser.meta.get("author") or parser.meta.get("article:author")
    published_at = (
        parser.meta.get("article:published_time")
        or parser.meta.get("published_time")
        or parser.meta.get("date")
        or parser.meta.get("pubdate")
        or (parser.time_values[0] if parser.time_values else None)
    )
    site_name = parser.meta.get("og:site_name")
    language = parser.meta.get("language")

    first_h1 = next(
        (block.get("text") for block in parser.blocks if block.get("type") == "heading" and block.get("level") == 1),
        None,
    )
    document_title = first_h1 or page_title

    warnings: list[str] = []
    if not document_title:
        warnings.append("title_not_found")
    if not author:
        warnings.append("author_not_found")
    if not published_at:
        warnings.append("published_at_not_found")
    if not canonical_url:
        warnings.append("canonical_url_not_found")
    if not parser.blocks:
        warnings.append("main_content_not_found")
    body_blocks = [block for block in parser.blocks if block.get("type") not in {"heading", "image"}]
    if not body_blocks and "main_content_not_found" not in warnings:
        warnings.append("main_content_not_found")
    if published_at and any(value != published_at for value in parser.time_values):
        warnings.append("conflicting_publish_times")

    document_ast = {
        "schema_version": "1.0",
        "title": document_title,
        "blocks": parser.blocks,
        "warnings": warnings.copy(),
    }

    document = {
        "title": {"value": document_title, "confidence": 0.95 if document_title else 0, "evidence": "h1_or_title"},
        "author": {"value": author, "confidence": 0.8 if author else 0, "evidence": "meta_author" if author else "not_found"},
        "published_at": {
            "value": published_at,
            "confidence": 0.8 if published_at else 0,
            "evidence": "meta_published_time" if published_at else "not_found",
        },
        "language": language,
    }

    return {
        "source": {
            "url": source_url or "",
            "canonical_url": canonical_url,
            "page_title": page_title,
            "site_name": site_name,
        },
        "document": document,
        "document_ast": document_ast,
        "warnings": warnings,
    }
