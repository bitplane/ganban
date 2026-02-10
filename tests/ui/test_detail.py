"""Tests for detail modals."""

from datetime import date

import pytest
from textual.app import App

from ganban.model.node import ListNode, Node
from ganban.ui.cal import Calendar, CalendarDay, NavButton
from ganban.ui.detail import BoardDetailModal, CardDetailModal, ColumnDetailModal, DetailModal
from ganban.ui.due import DueDateWidget
from ganban.ui.edit import EditableText, MarkdownDocEditor, SectionEditor
from tests.ui.conftest import GANBAN_CSS_PATH


class DetailTestApp(App):
    """Minimal app for testing detail modals."""

    CSS_PATH = GANBAN_CSS_PATH

    def __init__(self, modal):
        super().__init__()
        self._modal = modal

    def on_mount(self):
        self.push_screen(self._modal)


@pytest.fixture
def card():
    """A card with sections."""
    sections = ListNode()
    sections["Test Card"] = "Card body content"
    sections["Notes"] = "Some notes"
    sections["Tasks"] = "- [ ] Task 1"
    return Node(sections=sections, meta={}, file_path=".all/001.md")


@pytest.fixture
def card_with_due():
    """A card with a due date."""
    sections = ListNode()
    sections["Due Card"] = ""
    return Node(sections=sections, meta={"due": "2026-06-15"}, file_path=".all/002.md")


@pytest.fixture
def column():
    """A column with content."""
    sections = ListNode()
    sections["Column Title"] = "Column description"
    sections["Guidelines"] = "Some guidelines"
    return Node(order="01", sections=sections, meta={})


@pytest.fixture
def board():
    """A board with content."""
    sections = ListNode()
    sections["Test Board"] = "Board description"
    sections["About"] = "About this board"
    return Node(repo_path="/tmp/test", sections=sections, meta={})


@pytest.mark.asyncio
async def test_card_detail_modal_shows_content(card):
    """Card detail modal displays card content."""
    app = DetailTestApp(CardDetailModal(card))
    async with app.run_test():
        screen = app.screen
        assert isinstance(screen, CardDetailModal)

        editor = screen.query_one(MarkdownDocEditor)
        assert editor.sections is card.sections

        # Should have main section + subsections
        sections = screen.query(SectionEditor)
        assert len(sections) == 3  # main + 2 sections


@pytest.mark.asyncio
async def test_column_detail_modal_shows_content(column):
    """Column detail modal displays column content."""
    app = DetailTestApp(ColumnDetailModal(column))
    async with app.run_test():
        screen = app.screen
        assert isinstance(screen, ColumnDetailModal)

        editor = screen.query_one(MarkdownDocEditor)
        assert editor.sections is column.sections


@pytest.mark.asyncio
async def test_board_detail_modal_shows_content(board):
    """Board detail modal displays board content."""
    app = DetailTestApp(BoardDetailModal(board))
    async with app.run_test():
        screen = app.screen
        assert isinstance(screen, BoardDetailModal)

        editor = screen.query_one(MarkdownDocEditor)
        assert editor.sections is board.sections


@pytest.mark.asyncio
async def test_escape_closes_modal(card):
    """Escape key closes the modal when not editing."""
    app = DetailTestApp(CardDetailModal(card))
    async with app.run_test() as pilot:
        assert isinstance(app.screen, DetailModal)

        # Click somewhere that's not an EditableText to ensure we're not editing
        await pilot.click(app.screen, offset=(5, 5))
        await pilot.pause()

        # If an EditableText got focused, first escape cancels edit, second closes modal
        await pilot.press("escape")
        await pilot.pause()
        if isinstance(app.screen, DetailModal):
            await pilot.press("escape")
        assert not isinstance(app.screen, DetailModal)


@pytest.mark.asyncio
async def test_click_outside_closes_modal(card):
    """Clicking outside the detail container closes the modal."""
    app = DetailTestApp(CardDetailModal(card))
    async with app.run_test() as pilot:
        assert isinstance(app.screen, DetailModal)

        # Click in the corner (outside 80% centered container)
        await pilot.click(offset=(0, 0))
        assert not isinstance(app.screen, DetailModal)


@pytest.mark.asyncio
async def test_editing_title_updates_sections(card):
    """Editing the title updates the underlying sections ListNode."""
    app = DetailTestApp(CardDetailModal(card))
    async with app.run_test() as pilot:
        title = app.screen.query_one("#doc-title", EditableText)

        # Start editing by focusing
        title.focus()
        await pilot.pause()

        # Set new title
        text_area = title.query_one("#edit")
        text_area.text = "New Title"

        # Submit
        await pilot.press("enter")
        await pilot.pause()

        assert card.sections.keys()[0] == "New Title"


@pytest.mark.asyncio
async def test_editing_section_updates_sections(card):
    """Editing a section body updates the underlying sections ListNode."""
    app = DetailTestApp(CardDetailModal(card))
    async with app.run_test() as pilot:
        # Find the Notes section
        sections = app.screen.query(".subsection")
        notes_section = None
        for section in sections:
            if section.heading == "Notes":
                notes_section = section
                break

        assert notes_section is not None

        # Start editing body
        body = notes_section.query_one(".section-body", EditableText)
        body.focus()
        await pilot.pause()

        text_area = body.query_one("#edit")
        text_area.text = "Updated notes"

        # Blur to save (focus title to trigger blur-save on editor)
        title = app.screen.query_one("#doc-title", EditableText)
        title.focus()
        await pilot.pause()

        assert card.sections["Notes"] == "Updated notes"


@pytest.mark.asyncio
async def test_renaming_section_updates_sections(card):
    """Renaming a section heading updates the sections ListNode."""
    app = DetailTestApp(CardDetailModal(card))
    async with app.run_test() as pilot:
        # Find the Notes section
        sections = app.screen.query(".subsection")
        notes_section = None
        for section in sections:
            if section.heading == "Notes":
                notes_section = section
                break

        assert notes_section is not None

        # Start editing heading
        heading = notes_section.query_one(".section-heading", EditableText)
        heading.focus()
        await pilot.pause()

        text_area = heading.query_one("#edit")
        text_area.text = "Comments"

        await pilot.press("enter")
        await pilot.pause()

        # Old key should be gone, new key should have content
        assert "Notes" not in card.sections
        assert "Comments" in card.sections
        assert card.sections["Comments"] == "Some notes"


@pytest.mark.asyncio
async def test_editing_main_body_updates_sections(card):
    """Editing the main section body updates the underlying sections ListNode."""
    app = DetailTestApp(CardDetailModal(card))
    async with app.run_test() as pilot:
        editor = app.screen.query_one("#main-section", SectionEditor)
        body = editor.query_one(".section-body", EditableText)

        body.focus()
        await pilot.pause()

        text_area = body.query_one("#edit")
        text_area.text = "Updated body content"

        # Blur to save by focusing the title
        title = app.screen.query_one("#doc-title", EditableText)
        title.focus()
        await pilot.pause()

        # First key's value should be updated
        assert card.sections[card.sections.keys()[0]] == "Updated body content"


@pytest.mark.asyncio
async def test_action_close_via_escape(card):
    """Escape key triggers action_close to dismiss modal."""
    app = DetailTestApp(CardDetailModal(card))
    async with app.run_test() as pilot:
        assert isinstance(app.screen, DetailModal)

        # If an EditableText is focused (starts editing), first escape cancels edit
        await pilot.press("escape")
        await pilot.pause()
        if isinstance(app.screen, DetailModal):
            await pilot.press("escape")
            await pilot.pause()

        assert not isinstance(app.screen, DetailModal)


@pytest.mark.asyncio
async def test_action_quit_exits_app(card):
    """action_quit exits the app."""
    app = DetailTestApp(CardDetailModal(card))
    async with app.run_test() as pilot:
        assert isinstance(app.screen, DetailModal)

        await app.screen.action_quit()
        await pilot.pause()

        assert app.return_code is not None


@pytest.mark.asyncio
async def test_section_editor_body_property(card):
    """SectionEditor.body property returns the current body text."""
    app = DetailTestApp(CardDetailModal(card))
    async with app.run_test():
        editor = app.screen.query_one("#main-section", SectionEditor)
        assert editor.body == "Card body content"


@pytest.mark.asyncio
async def test_card_with_due_date_shows_due_widget(card_with_due):
    """Card with due date shows DueDateWidget with correct date."""
    app = DetailTestApp(CardDetailModal(card_with_due))
    async with app.run_test():
        widget = app.screen.query_one(DueDateWidget)
        assert widget.due == date(2026, 6, 15)


@pytest.mark.asyncio
async def test_setting_due_date_updates_card_meta(card):
    """Selecting a due date updates card.meta."""
    app = DetailTestApp(CardDetailModal(card))
    async with app.run_test() as pilot:
        widget = app.screen.query_one(DueDateWidget)
        picker = widget.query_one("#due-picker")

        await pilot.click(picker)

        cal = app.screen.query_one(Calendar)
        target_day = None
        for day in cal.query(CalendarDay):
            if day.date.month == date.today().month:
                target_day = day
                break

        await pilot.click(target_day)
        assert card.meta.due == target_day.date.isoformat()


@pytest.mark.asyncio
async def test_clearing_due_date_removes_meta(card_with_due):
    """Clearing due date via calendar clear button removes 'due' from card meta."""
    app = DetailTestApp(CardDetailModal(card_with_due))
    async with app.run_test() as pilot:
        widget = app.screen.query_one(DueDateWidget)
        picker = widget.query_one("#due-picker")

        await pilot.click(picker)
        cal = app.screen.query_one(Calendar)
        clear_btn = cal.query_one("#clear", NavButton)
        await pilot.click(clear_btn)
        await pilot.pause()

        assert card_with_due.meta.due is None
