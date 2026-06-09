from __future__ import annotations

from typing import Any


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    text = str(value).replace('"', '\\"')
    return f'"{text}"'


def _escape_pipe(text: str) -> str:
    return text.replace("|", "\\|")


def render_page_markdown(metadata: dict[str, Any], ast: dict[str, Any]) -> str:
    source = metadata["source"]
    document = metadata["document"]
    extraction = metadata["extraction"]
    title = document["title"]["value"] or source.get("page_title") or "Untitled"
    author = document["author"]["value"]
    published_at = document["published_at"]["value"]
    warnings = extraction.get("warnings", [])

    lines: list[str] = ["---"]
    front_matter = {
        "title": title,
        "author": author,
        "published_at": published_at,
        "source_url": source["url"],
        "canonical_url": source.get("canonical_url"),
        "accessed_at": source["accessed_at"],
        "page_type": document.get("page_type"),
        "extraction_method": extraction["method"],
    }
    for key, value in front_matter.items():
        lines.append(f"{key}: {_yaml_scalar(value)}")
    lines.append("warnings:")
    if warnings:
        for warning in warnings:
            lines.append(f"  - {warning}")
    else:
        lines.append("  []")
    lines.append("---")
    lines.append("")
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"> Source: {source['url']}")
    lines.append(f"> Accessed: {source['accessed_at']}")
    lines.append(f"> Author: {author or 'Unknown'}")
    lines.append(f"> Published: {published_at or 'Unknown'}")
    lines.append("")

    h1_emitted = False
    ast_document = ast.get("document", {})
    for block in ast_document.get("blocks", []):
        block_type = block.get("type")
        text = (block.get("text") or "").strip()
        if block_type == "heading":
            level = int(block.get("level") or 2)
            if level == 1:
                if not h1_emitted and text == title:
                    h1_emitted = True
                    continue
                level = 2
            lines.append(f"{'#' * level} {text}")
            lines.append("")
        elif block_type == "paragraph" and text:
            lines.append(text)
            lines.append("")
        elif block_type == "list_item" and text:
            lines.append(f"- {text}")
        elif block_type == "quote" and text:
            for quote_line in text.splitlines():
                lines.append(f"> {quote_line}")
            lines.append("")
        elif block_type == "code" and text:
            lines.append("```")
            lines.append(text)
            lines.append("```")
            lines.append("")
        elif block_type == "image":
            alt = block.get("alt") or "no_caption"
            src = block.get("src") or ""
            lines.append(f"![{alt}]({src})")
            lines.append("")
        elif block_type == "table":
            rows = block.get("rows") or []
            if rows:
                header = rows[0]
                lines.append("| " + " | ".join(_escape_pipe(str(cell)) for cell in header) + " |")
                lines.append("| " + " | ".join("---" for _ in header) + " |")
                for row in rows[1:]:
                    lines.append("| " + " | ".join(_escape_pipe(str(cell)) for cell in row) + " |")
                lines.append("")
        elif block_type == "thread_post":
            author_name = block.get("author") or "Unknown"
            published = block.get("published_at") or "Unknown"
            lines.append(f"## Post by {author_name}")
            lines.append("")
            lines.append(f"> Published: {published}")
            if block.get("permalink"):
                lines.append(f"> Permalink: {block['permalink']}")
            lines.append("")
            for child in block.get("body_blocks") or []:
                child_text = (child.get("text") or "").strip()
                if child.get("type") == "paragraph" and child_text:
                    lines.append(child_text)
                    lines.append("")
                elif child.get("type") == "quote" and child_text:
                    lines.append(f"> {child_text}")
                    lines.append("")
            for warning in block.get("warnings") or []:
                if warning not in warnings:
                    warnings.append(warning)

    if warnings:
        lines.append("## Extraction Notes")
        lines.append("")
        for warning in warnings:
            lines.append(f"- {warning}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
