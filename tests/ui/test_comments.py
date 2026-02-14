"""Tests for the comments editor widget."""

import pytest
from textual.app import App, ComposeResult

from ganban.ui.edit.comments import CommentsEditor, CommentRow
from ganban.ui.edit.editable import EditableText
from ganban.ui.edit.section import SectionEditor
from ganban.ui.edit.viewers import MarkdownViewer

from tests.ui.conftest import GANBAN_CSS_PATH


BODY_WITH_COMMENTS = (
    "- [Alice](mailto:alice@example.com) first comment\n"
    "- [Bob](mailto:bob@example.com) second comment\n"
    "- [Alice](mailto:alice@example.com) third comment"
)


class CommentsApp(App):
    """Minimal app for testing CommentsEditor."""

    CSS_PATH = GANBAN_CSS_PATH

    def __init__(self, body=BODY_WITH_COMMENTS, user_email="alice@example.com", user_name="Alice"):
        super().__init__()
        self._body = body
        self._user_email = user_email
        self._user_name = user_name
        self.body_changes = []

    def compose(self) -> ComposeResult:
        yield CommentsEditor(
            "Comments",
            self._body,
            user_email=self._user_email,
            user_name=self._user_name,
        )

    def on_section_editor_body_changed(self, event: SectionEditor.BodyChanged) -> None:
        self.body_changes.append(event.new_value)


@pytest.mark.asyncio
async def test_comments_render_as_rows():
    """Comments render as individual CommentRow widgets."""
    app = CommentsApp()
    async with app.run_test():
        rows = app.query(CommentRow)
        assert len(rows) == 3


@pytest.mark.asyncio
async def test_own_comment_is_editable():
    """Current user's comments have an EditableText widget."""
    app = CommentsApp()
    async with app.run_test():
        rows = list(app.query(CommentRow))
        # Alice's comments (index 0, 2) should have EditableText
        alice_row = rows[0]
        editable = alice_row.query(EditableText)
        assert len(editable) == 1


@pytest.mark.asyncio
async def test_other_comment_is_static():
    """Other user's comments render as static MarkdownViewer."""
    app = CommentsApp()
    async with app.run_test():
        rows = list(app.query(CommentRow))
        # Bob's comment (index 1) should have MarkdownViewer but no EditableText
        bob_row = rows[1]
        assert len(bob_row.query(EditableText)) == 0
        assert len(bob_row.query(MarkdownViewer)) == 1


@pytest.mark.asyncio
async def test_add_comment_emits_body_changed():
    """Adding a comment emits BodyChanged with the new body."""
    app = CommentsApp()
    async with app.run_test() as pilot:
        add_input = app.query_one(".add-comment", EditableText)
        add_input.focus()
        await pilot.pause()

        text_area = add_input.query_one("#edit")
        text_area.text = "new comment"
        await pilot.press("enter")
        await pilot.pause()

        assert len(app.body_changes) == 1
        assert "[Alice](mailto:alice@example.com) new comment" in app.body_changes[0]


@pytest.mark.asyncio
async def test_delete_own_comment_emits_body_changed():
    """Deleting own comment emits BodyChanged without that comment."""
    app = CommentsApp(body="- [Alice](mailto:alice@example.com) only comment")
    async with app.run_test() as pilot:
        editor = app.query_one(CommentsEditor)
        # Directly modify the extracted data and trigger rebuild
        editor._extracted.items.clear()
        editor._rebuild_body()
        await pilot.pause()

        assert len(app.body_changes) == 1
        assert "only comment" not in app.body_changes[0]


@pytest.mark.asyncio
async def test_no_comments_shows_empty_list():
    """A body with no bullet list shows no comment rows."""
    app = CommentsApp(body="Just some text, no bullets")
    async with app.run_test():
        rows = app.query(CommentRow)
        assert len(rows) == 0
