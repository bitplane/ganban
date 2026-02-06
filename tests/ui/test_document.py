"""Tests for the document editor widget."""

import pytest
from textual.app import App, ComposeResult

from ganban.model.node import ListNode
from ganban.ui.edit import EditableText, MarkdownDocEditor


class DocEditorApp(App):
    """Minimal app for testing document editor."""

    def __init__(self):
        super().__init__()
        self.sections = ListNode()
        self.sections["Test Doc"] = "Body text"
        self.doc_changed = False

    def compose(self) -> ComposeResult:
        yield MarkdownDocEditor(self.sections)

    def on_markdown_doc_editor_changed(self, event: MarkdownDocEditor.Changed) -> None:
        self.doc_changed = True


@pytest.mark.asyncio
async def test_title_change_emits_changed():
    """Changing the title emits a Changed event from MarkdownDocEditor."""
    app = DocEditorApp()
    async with app.run_test() as pilot:
        title = app.query_one("#doc-title", EditableText)
        title.focus()
        await pilot.pause()

        text_area = title.query_one("#edit")
        text_area.text = "New Title"

        await pilot.press("enter")
        await pilot.pause()

        assert app.doc_changed is True
