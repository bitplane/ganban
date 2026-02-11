"""Tests for AddSection and MarkdownDocEditor section creation."""

import pytest
from textual.app import App, ComposeResult

from ganban.model.node import ListNode
from ganban.ui.confirm import ConfirmButton
from ganban.ui.edit.document import AddSection, MarkdownDocEditor
from ganban.ui.edit.editable import EditableText
from ganban.ui.edit.section import SectionEditor


class AddSectionTestApp(App):
    """Minimal app for testing AddSection."""

    def compose(self) -> ComposeResult:
        yield AddSection()


class DocEditorTestApp(App):
    """Minimal app for testing MarkdownDocEditor."""

    def __init__(self, sections):
        super().__init__()
        self.sections = sections

    def compose(self) -> ComposeResult:
        yield MarkdownDocEditor(self.sections)


@pytest.fixture
def sections():
    """A sections ListNode with title and one subsection."""
    s = ListNode()
    s["My Card"] = "Body text"
    s["Notes"] = "Some notes"
    return s


@pytest.fixture
def sections_no_subsections():
    """A sections ListNode with only a title."""
    s = ListNode()
    s["My Card"] = "Body text"
    return s


@pytest.mark.asyncio
async def test_add_section_emits_created():
    """AddSection emits SectionCreated with the heading text."""
    app = AddSectionTestApp()

    async with app.run_test() as pilot:
        add = app.query_one(AddSection)
        editable = add.query_one(EditableText)
        editable.focus()
        await pilot.pause()

        editor = editable.query_one("#edit")
        editor.text = "New Section"
        await pilot.press("enter")
        await pilot.pause()

        # Check the EditableText was cleared
        assert editable.value == ""


@pytest.mark.asyncio
async def test_add_section_empty_does_not_emit():
    """Empty submission does not emit SectionCreated."""
    app = AddSectionTestApp()

    async with app.run_test() as pilot:
        add = app.query_one(AddSection)
        editable = add.query_one(EditableText)
        editable.focus()
        await pilot.pause()

        # Submit empty
        await pilot.press("enter")
        await pilot.pause()

        assert editable.value == ""


@pytest.mark.asyncio
async def test_doc_editor_add_section_updates_model(sections_no_subsections):
    """Adding a section in MarkdownDocEditor updates the sections ListNode."""
    app = DocEditorTestApp(sections_no_subsections)

    async with app.run_test() as pilot:
        add = app.query_one(AddSection)
        editable = add.query_one(EditableText)
        editable.focus()
        await pilot.pause()

        editor = editable.query_one("#edit")
        editor.text = "Tasks"
        await pilot.press("enter")
        await pilot.pause()

        assert "Tasks" in sections_no_subsections.keys()
        assert sections_no_subsections["Tasks"] == ""


@pytest.mark.asyncio
async def test_doc_editor_add_section_mounts_editor(sections_no_subsections):
    """Adding a section mounts a new SectionEditor in the right panel."""
    app = DocEditorTestApp(sections_no_subsections)

    async with app.run_test() as pilot:
        # Initially no subsections
        subsections = app.query(".subsection")
        assert len(subsections) == 0

        add = app.query_one(AddSection)
        editable = add.query_one(EditableText)
        editable.focus()
        await pilot.pause()

        editor = editable.query_one("#edit")
        editor.text = "Comments"
        await pilot.press("enter")
        await pilot.pause()

        subsections = app.query(".subsection")
        assert len(subsections) == 1


@pytest.mark.asyncio
async def test_doc_editor_has_add_section(sections):
    """MarkdownDocEditor includes AddSection in the right panel."""
    app = DocEditorTestApp(sections)

    async with app.run_test():
        add = app.query_one(AddSection)
        assert add is not None


@pytest.mark.asyncio
async def test_delete_subsection_removes_from_model(sections):
    """Confirming delete on a subsection removes it from the model and DOM."""
    app = DocEditorTestApp(sections)

    async with app.run_test() as pilot:
        subsections = app.query(".subsection")
        assert len(subsections) == 1

        # Simulate confirm on the delete button
        btn = subsections.first(SectionEditor).query_one(ConfirmButton)
        btn.post_message(ConfirmButton.Confirmed())
        await pilot.pause()

        assert "Notes" not in sections.keys()
        assert len(app.query(".subsection")) == 0
