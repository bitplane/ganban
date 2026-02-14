"""Comments editor widget."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from textual.app import ComposeResult

from ganban.ui.confirm import ConfirmButton
from ganban.ui.edit.editable import EditableText
from ganban.ui.edit.editors import TextEditor
from ganban.ui.edit.section import BulletListEditor, ItemRow
from ganban.ui.edit.viewers import MarkdownViewer

if TYPE_CHECKING:
    from ganban.ui.edit.document import EditorType

# Matches: "- [Name](mailto:email) comment text"
# Groups: (1) bullet+author prefix including trailing space, (2) email, (3) comment text
_COMMENT_RE = re.compile(r"^([\-\*\+]\s+\[[^\]]*\]\(mailto:([^)]+)\)\s*)(.*)", re.DOTALL)


def _parse_comment(item: str) -> tuple[str | None, str, str]:
    """Parse a comment item into (email, author_prefix, comment_text).

    Returns (None, "", full_item) if no mailto link found.
    """
    match = _COMMENT_RE.match(item)
    if match:
        return match.group(2), match.group(1), match.group(3)
    return None, "", item


class CommentRow(ItemRow):
    """A single comment in the comments list."""

    def __init__(self, item: str, index: int, editable: bool, parser_factory=None, **kwargs) -> None:
        super().__init__(index, **kwargs)
        self._item = item
        self._editable = editable
        self._parser_factory = parser_factory

    def compose(self) -> ComposeResult:
        _, _, comment_text = _parse_comment(self._item)
        # Strip the bullet prefix for full display (author + comment)
        display_text = re.sub(r"^[\-\*\+]\s+", "", self._item)
        if self._editable:
            # Viewer shows full text (author + comment), editor edits comment only
            yield EditableText(
                comment_text,
                MarkdownViewer(display_text, parser_factory=self._parser_factory),
                TextEditor(),
                classes="comment-text",
                clean=False,
            )
            yield ConfirmButton(classes="comment-delete")
        else:
            yield MarkdownViewer(display_text, parser_factory=self._parser_factory, classes="comment-text")


class CommentsEditor(BulletListEditor):
    """Editor for comment sections using bullet-list extraction."""

    _list_class = "comments-list"
    _add_class = "add-comment"
    _add_placeholder = "+ comment"
    _before_class = "comments-before"
    _after_class = "comments-after"

    def __init__(
        self,
        heading: str | None,
        body: str = "",
        parser_factory=None,
        editor_types: list[EditorType] | None = None,
        user_email: str = "",
        user_name: str = "",
        **kwargs,
    ) -> None:
        super().__init__(heading, body, parser_factory=parser_factory, editor_types=editor_types, **kwargs)
        self._user_email = user_email
        self._user_name = user_name

    def _make_row(self, item: str, index: int) -> CommentRow:
        email, _, _ = _parse_comment(item)
        editable = bool(self._user_email and email == self._user_email)
        return CommentRow(item, index, editable, parser_factory=self._parser_factory, classes="comment-row")

    def _format_new_item(self, text: str) -> str:
        prefix = f"[{self._user_name}](mailto:{self._user_email}) " if self._user_email else ""
        return f"- {prefix}{text}"

    def _format_edited_item(self, index: int, new_text: str) -> str:
        _, author_prefix, _ = _parse_comment(self._extracted.items[index])
        return author_prefix + new_text
