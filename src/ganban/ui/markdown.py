"""Markdown-it plugins for ganban."""

from __future__ import annotations

import re

from markdown_it import MarkdownIt
from markdown_it.token import Token

from ganban.model.node import Node
from ganban.parser import first_title
from ganban.ui.emoji import emoji_for_email, resolve_email_display

_CARD_REF_RE = re.compile(r"#(\d+)")


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


def card_ref_plugin(md: MarkdownIt, board: Node) -> None:
    """Core rule replacing #NNN card references with links."""

    def replace_card_refs(state):
        for token in state.tokens:
            if token.type != "inline" or not token.children:
                continue
            new_children = []
            inside_link = 0
            for child in token.children:
                if child.type == "link_open":
                    inside_link += 1
                elif child.type == "link_close":
                    inside_link -= 1

                if child.type != "text" or inside_link > 0:
                    new_children.append(child)
                    continue

                parts = _split_card_refs(child.content, board, child.level)
                new_children.extend(parts)

            token.children = new_children

    md.core.ruler.push("card_ref", replace_card_refs)


def _split_card_refs(text: str, board: Node, level: int) -> list[Token]:
    """Split text containing #NNN refs into text and link tokens."""
    tokens = []
    last_end = 0

    for match in _CARD_REF_RE.finditer(text):
        card_id = str(int(match.group(1))).zfill(3)
        card = board.cards[card_id] if board.cards else None
        if card is None:
            continue

        title = first_title(card.sections)
        start, end = match.start(), match.end()

        if start > last_end:
            tokens.append(_text_token(text[last_end:start], level))

        link_open = Token("link_open", "a", 1)
        link_open.attrs = {"href": f"card:{card_id}"}
        link_open.level = level
        tokens.append(link_open)

        tokens.append(_text_token(f"#{card_id} {title}", level + 1))

        link_close = Token("link_close", "a", -1)
        link_close.level = level
        tokens.append(link_close)

        last_end = end

    if not tokens:
        return [_text_token(text, level)]

    if last_end < len(text):
        tokens.append(_text_token(text[last_end:], level))

    return tokens


def _text_token(content: str, level: int) -> Token:
    """Create a text token."""
    tok = Token("text", "", 0)
    tok.content = content
    tok.level = level
    return tok


def ganban_parser_factory(board: Node | None):
    """Return a parser_factory closure for Textual's Markdown widget."""

    def factory():
        md = MarkdownIt("gfm-like")
        if board:
            meta = board.meta
            committers = None
            if board.git:
                c = board.git.committers
                committers = c if isinstance(c, list) else None
            if meta:
                md.use(mailto_display_plugin, meta, committers)
            md.use(card_ref_plugin, board)
        return md

    return factory
