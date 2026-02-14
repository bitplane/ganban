"""Reusable block extraction from markdown body text."""

from __future__ import annotations

from dataclasses import dataclass, field

from markdown_it import MarkdownIt


@dataclass
class ExtractedList:
    """A bullet list extracted from markdown body text."""

    before: str = ""
    items: list[str] = field(default_factory=list)
    after: str = ""


def extract_bullet_list(body: str) -> ExtractedList:
    """Extract the first bullet list from markdown body using markdown-it.

    Uses Token.map line ranges to slice the source text. Skips code fences
    (handled by markdown-it's tokenizer). If no bullet list found, returns
    ExtractedList(before=body, items=[], after="").
    """
    md = MarkdownIt("gfm-like")
    tokens = md.parse(body)
    lines = body.split("\n")

    # Find the first bullet_list_open token
    list_start = None
    list_end = None
    for token in tokens:
        if token.type == "bullet_list_open" and token.map:
            list_start, list_end = token.map
            break

    if list_start is None:
        return ExtractedList(before=body)

    # Extract individual items from list_item tokens within this list
    items = []
    depth = 0
    in_target_list = False
    for token in tokens:
        if token.type == "bullet_list_open":
            if token.map and token.map[0] == list_start:
                in_target_list = True
                depth = 1
            elif in_target_list:
                depth += 1
        elif token.type == "bullet_list_close" and in_target_list:
            depth -= 1
            if depth == 0:
                break
        elif token.type == "list_item_open" and in_target_list and depth == 1 and token.map:
            item_start, item_end = token.map
            item_lines = lines[item_start:item_end]
            # Strip trailing blank lines (markdown-it may include them)
            while item_lines and not item_lines[-1].strip():
                item_lines.pop()
            items.append("\n".join(item_lines))

    # Find where actual item content ends (excluding trailing blank lines)
    content_end = list_end
    while content_end > list_start and not lines[content_end - 1].strip():
        content_end -= 1

    before = "\n".join(lines[:list_start])
    after = "\n".join(lines[content_end:])

    return ExtractedList(before=before, items=items, after=after)


def reconstruct_body(extracted: ExtractedList) -> str:
    """Reconstruct body from before + items + after."""
    parts = []
    if extracted.before:
        parts.append(extracted.before)
    if extracted.items:
        parts.append("\n".join(extracted.items))
    if extracted.after:
        parts.append(extracted.after)
    return "\n".join(parts)
