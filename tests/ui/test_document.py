"""Tests for the document editor widget."""

import pytest
from textual.app import App, ComposeResult

from ganban.model.loader import build_sections_list
from ganban.model.node import ListNode, Node
from ganban.ui.edit import EditableText, MarkdownDocEditor
from tests.ui.conftest import GANBAN_CSS_PATH


class DocEditorApp(App):
    """Minimal app for testing document editor."""

    CSS_PATH = GANBAN_CSS_PATH

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


@pytest.mark.asyncio
@pytest.mark.parametrize("section_id,key", [("main-section", "Title"), ("preamble-section", "")])
async def test_preamble_and_body_edit_independently(section_id, key):
    app = DocEditorApp()
    app.sections, _ = build_sections_list("Intro\n\n# Title\n\nBody\n\n## Notes\n\nNotes body\n")
    async with app.run_test() as pilot:
        value = app.query_one(f"#{section_id} .section-body", EditableText)
        assert value.value == ("Intro" if key == "" else "Body")
        value.focus()
        await pilot.pause()
        value.query_one("#edit").text = "Changed"
        app.set_focus(None)
        await pilot.pause()
        assert app.sections.items() == [
            ("", "Changed" if key == "" else "Intro"),
            ("Title", "Changed" if key == "Title" else "Body"),
            ("Notes", "Notes body"),
        ]


@pytest.mark.asyncio
@pytest.mark.parametrize("requested,stored", [("Renamed", "Renamed"), ("Notes", "Notes (1)")])
async def test_title_rename_keeps_preamble_and_reacts_to_body_changes(requested, stored):
    app = DocEditorApp()
    app.sections, _ = build_sections_list("Intro\n\n# Title\n\nBody\n\n## Notes\n\nNotes body\n")
    document = Node(sections=app.sections)
    async with app.run_test() as pilot:
        document.sections["Title"] = "External body"
        await pilot.pause()
        title = app.query_one("#doc-title", EditableText)
        assert title.value == "Title"
        title.focus()
        await pilot.pause()
        title.query_one("#edit").text = requested
        await pilot.press("enter")
        await pilot.pause()
        assert app.sections.items() == [("", "Intro"), (stored, "External body"), ("Notes", "Notes body")]
        assert app.query_one("#doc-title", EditableText).value == stored
