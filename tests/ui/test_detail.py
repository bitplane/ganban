"""Tests for detail modals."""

import pytest
from textual.app import App

from ganban.models import Board, Card, Column, MarkdownDoc
from ganban.ui.detail import BoardDetailModal, CardDetailModal, ColumnDetailModal, DetailModal
from ganban.ui.edit import MarkdownDocEditor, SectionEditor


class DetailTestApp(App):
    """Minimal app for testing detail modals."""

    def __init__(self, modal):
        super().__init__()
        self._modal = modal

    def on_mount(self):
        self.push_screen(self._modal)


@pytest.fixture
def card():
    """A card with sections."""
    return Card(
        id="test-card",
        content=MarkdownDoc(
            title="Test Card",
            body="Card body content",
            sections={"Notes": "Some notes", "Tasks": "- [ ] Task 1"},
        ),
    )


@pytest.fixture
def column():
    """A column with content."""
    return Column(
        order="01",
        name="Test Column",
        content=MarkdownDoc(
            title="Column Title",
            body="Column description",
            sections={"Guidelines": "Some guidelines"},
        ),
    )


@pytest.fixture
def board():
    """A board with content."""
    return Board(
        repo_path="/tmp/test",
        content=MarkdownDoc(
            title="Test Board",
            body="Board description",
            sections={"About": "About this board"},
        ),
    )


@pytest.mark.asyncio
async def test_card_detail_modal_shows_content(card):
    """Card detail modal displays card content."""
    app = DetailTestApp(CardDetailModal(card))
    async with app.run_test():
        screen = app.screen
        assert isinstance(screen, CardDetailModal)

        editor = screen.query_one(MarkdownDocEditor)
        assert editor.doc is card.content

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
        assert editor.doc is column.content


@pytest.mark.asyncio
async def test_board_detail_modal_shows_content(board):
    """Board detail modal displays board content."""
    app = DetailTestApp(BoardDetailModal(board))
    async with app.run_test():
        screen = app.screen
        assert isinstance(screen, BoardDetailModal)

        editor = screen.query_one(MarkdownDocEditor)
        assert editor.doc is board.content


@pytest.mark.asyncio
async def test_escape_closes_modal(card):
    """Escape key closes the modal."""
    app = DetailTestApp(CardDetailModal(card))
    async with app.run_test() as pilot:
        assert isinstance(app.screen, DetailModal)

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
async def test_editing_title_updates_doc(card):
    """Editing the title updates the underlying document."""
    app = DetailTestApp(CardDetailModal(card))
    async with app.run_test() as pilot:
        editor = app.screen.query_one("#main-section", SectionEditor)
        label = editor.query_one(".section-heading")

        # Start editing
        label.start_editing()
        await pilot.pause()

        # Clear and type new title
        text_area = label.query_one("#edit")
        text_area.text = "New Title"

        # Submit
        await pilot.press("enter")
        await pilot.pause()

        assert card.content.title == "New Title"


@pytest.mark.asyncio
async def test_editing_section_updates_doc(card):
    """Editing a section body updates the underlying document."""
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
        markdown = notes_section.query_one("EditableMarkdown")
        markdown.start_editing()
        await pilot.pause()

        text_area = markdown.query_one("#edit")
        text_area.text = "Updated notes"

        # Blur to save (click elsewhere)
        main_section = app.screen.query_one("#main-section")
        await pilot.click(main_section)
        await pilot.pause()

        assert card.content.sections["Notes"] == "Updated notes"


@pytest.mark.asyncio
async def test_renaming_section_updates_doc(card):
    """Renaming a section heading updates the document's sections dict."""
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
        label = notes_section.query_one(".section-heading")
        label.start_editing()
        await pilot.pause()

        text_area = label.query_one("#edit")
        text_area.text = "Comments"

        await pilot.press("enter")
        await pilot.pause()

        # Old key should be gone, new key should have content
        assert "Notes" not in card.content.sections
        assert "Comments" in card.content.sections
        assert card.content.sections["Comments"] == "Some notes"
