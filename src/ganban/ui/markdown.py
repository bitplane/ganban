"""Markdown-it plugins for ganban."""

from __future__ import annotations

from markdown_it import MarkdownIt

from ganban.model.node import Node
from ganban.ui.emoji import emoji_for_email, resolve_email_display


def mailto_display_plugin(md: MarkdownIt, meta: Node, committers: list[str] | None) -> None:
    """Core rule replacing mailto link text with emoji + name."""

    def replace_mailto_text(state):
        for token in state.tokens:
            if token.type != "inline" or not token.children:
                continue
            children = token.children
            for i, child in enumerate(children):
                if child.type != "link_open":
                    continue
                href = child.attrGet("href") or ""
                if not href.startswith("mailto:"):
                    continue
                email = href[7:]
                if i + 1 < len(children) and children[i + 1].type == "text":
                    result = resolve_email_display(email, meta, committers)
                    if result:
                        emoji, name = result
                    else:
                        emoji = emoji_for_email(email)
                        name = children[i + 1].content
                    children[i + 1].content = f"{emoji} {name}"

    md.core.ruler.push("mailto_display", replace_mailto_text)


def ganban_parser_factory(meta: Node | None, committers: list[str] | None = None):
    """Return a parser_factory closure for Textual's Markdown widget."""

    def factory():
        md = MarkdownIt("gfm-like")
        if meta:
            md.use(mailto_display_plugin, meta, committers)
        return md

    return factory
