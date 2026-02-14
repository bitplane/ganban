"""Comments editor widget."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Static

from ganban.ui.confirm import ConfirmButton
from ganban.ui.edit.blocks import extract_bullet_list, reconstruct_body
from ganban.ui.edit.editable import EditableText
from ganban.ui.edit.editors import TextEditor
from ganban.ui.edit.section import EditorSelectButton, SectionEditor
from ganban.ui.edit.viewers import MarkdownViewer

if TYPE_CHECKING:
    from ganban.ui.edit.document import EditorType

_MAILTO_RE = re.compile(r"\[([^\]]*)\]\(mailto:([^)]+)\)")
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


class CommentRow(Horizontal):
    """A single comment in the comments list."""

    def __init__(self, item: str, index: int, editable: bool, parser_factory=None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._item = item
        self._index = index
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


class CommentsEditor(SectionEditor):
    """Editor for comment sections using bullet-list extraction."""

    def __init__(
        self,
        heading: str | None,
        body: str = "",
        parser_factory=None,
        editor_types: list[EditorType] | None = None,
        user_email: str = "",
        user_name: str = "",
        board=None,
        **kwargs,
    ) -> None:
        super().__init__(heading, body, parser_factory=parser_factory, editor_types=editor_types, **kwargs)
        self._user_email = user_email
        self._user_name = user_name
        self._board = board
        self._extracted = extract_bullet_list(body)

    def compose(self) -> ComposeResult:
        if self._heading is not None:
            with Horizontal(classes="section-heading-row"):
                yield EditableText(
                    self._heading,
                    Static(self._heading),
                    TextEditor(),
                    classes="section-heading",
                )
                current = self._match_editor_type()
                if current and self._editor_types:
                    yield EditorSelectButton(self._editor_types, current, classes="section-editor-select")
                yield ConfirmButton(classes="section-delete")

        if self._extracted.before.strip():
            yield MarkdownViewer(self._extracted.before, parser_factory=self._parser_factory, classes="comments-before")

        with VerticalScroll(classes="comments-list"):
            for i, item in enumerate(self._extracted.items):
                email, _, _ = _parse_comment(item)
                editable = bool(self._user_email and email == self._user_email)
                yield CommentRow(item, i, editable, parser_factory=self._parser_factory, classes="comment-row")

        if self._extracted.after.strip():
            yield MarkdownViewer(self._extracted.after, parser_factory=self._parser_factory, classes="comments-after")

        yield EditableText(
            "",
            Static("+ comment"),
            TextEditor(),
            placeholder="+ comment",
            classes="add-comment",
        )

    def focus_body(self) -> None:
        """Focus the add-comment input."""
        self.query_one(".add-comment", EditableText).focus()

    def _rebuild_body(self) -> None:
        """Reconstruct body from extracted data and emit BodyChanged."""
        old = self._body
        self._body = reconstruct_body(self._extracted)
        self.post_message(self.BodyChanged(old, self._body))

    def on_editable_text_changed(self, event: EditableText.Changed) -> None:
        event.stop()
        event.prevent_default()
        if "section-heading" in event.control.classes:
            self._heading = event.new_value
            self.post_message(self.HeadingChanged(event.old_value, event.new_value))
            return

        if "add-comment" in event.control.classes:
            if event.new_value.strip():
                prefix = f"[{self._user_name}](mailto:{self._user_email}) " if self._user_email else ""
                self._extracted.items.append(f"- {prefix}{event.new_value.strip()}")
                self._rebuild_body()
                self.call_after_refresh(self.recompose)
            return

        if "comment-text" in event.control.classes:
            row = event.control.parent
            if isinstance(row, CommentRow):
                _, author_prefix, _ = _parse_comment(self._extracted.items[row._index])
                self._extracted.items[row._index] = author_prefix + event.new_value
                self._rebuild_body()
                self.call_after_refresh(self.recompose)
            return

    def on_confirm_button_confirmed(self, event: ConfirmButton.Confirmed) -> None:
        event.stop()
        event.prevent_default()
        row = event.control.parent
        if isinstance(row, CommentRow):
            del self._extracted.items[row._index]
            self._rebuild_body()
            self.call_after_refresh(self.recompose)
            return
        # Section delete (inherited behavior)
        self.post_message(self.DeleteRequested())
