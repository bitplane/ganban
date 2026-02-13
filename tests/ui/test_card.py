"""Tests for CardWidget."""

from datetime import date, timedelta

import pytest
from textual.app import App, ComposeResult

from ganban.model.node import ListNode, Node
from ganban.ui.card import CardWidget
from ganban.ui.constants import ICON_BODY, ICON_CALENDAR, ICON_COLOR_SWATCH
from ganban.ui.static import PlainStatic


def _make_board(body="", due=None, labels=None):
    """Create a minimal board with one card."""
    sections = ListNode()
    sections["Test Card"] = body
    meta_dict = {}
    if due is not None:
        meta_dict["due"] = due.isoformat()
    if labels is not None:
        meta_dict["labels"] = labels
    card = Node(sections=sections, meta=meta_dict)

    cards = ListNode()
    cards["1"] = card

    col_sections = ListNode()
    col_sections["Todo"] = ""
    col = Node(order="1", dir_path="1.todo", sections=col_sections, meta={}, links=["1"])

    columns = ListNode()
    columns["1"] = col

    board_meta = {}
    board_labels = None
    if labels:
        board_labels = Node(**{name: Node(cards=["1"]) for name in labels})

    return Node(cards=cards, columns=columns, sections=ListNode(), meta=board_meta, labels=board_labels)


class CardTestApp(App):
    """Minimal app for testing CardWidget."""

    def __init__(self, board):
        super().__init__()
        self.board = board

    def compose(self) -> ComposeResult:
        yield CardWidget("1", self.board)


@pytest.mark.asyncio
async def test_card_has_four_zones():
    """Card composes header, labels, title, and footer."""
    board = _make_board()
    app = CardTestApp(board)
    async with app.run_test():
        assert app.query_one("#card-header", PlainStatic) is not None
        assert app.query_one("#card-labels", PlainStatic) is not None
        assert app.query_one("#card-title", PlainStatic) is not None
        assert app.query_one("#card-footer", PlainStatic) is not None


@pytest.mark.asyncio
async def test_footer_empty_no_indicators():
    """Footer is empty when card has no body or due date."""
    board = _make_board()
    app = CardTestApp(board)
    async with app.run_test():
        footer = app.query_one("#card-footer", PlainStatic)
        rendered = footer.render()
        assert str(rendered).strip() == ""


@pytest.mark.asyncio
async def test_footer_shows_body_indicator():
    """Footer shows 📝 when card has body content."""
    board = _make_board(body="some content")
    app = CardTestApp(board)
    async with app.run_test():
        footer = app.query_one("#card-footer", PlainStatic)
        rendered = footer.render()
        assert ICON_BODY in str(rendered)


@pytest.mark.asyncio
async def test_footer_shows_due_indicator():
    """Footer shows 📅 when card has due date."""
    future = date.today() + timedelta(days=5)
    board = _make_board(due=future)
    app = CardTestApp(board)
    async with app.run_test():
        footer = app.query_one("#card-footer", PlainStatic)
        rendered = footer.render()
        assert ICON_CALENDAR in str(rendered)


@pytest.mark.asyncio
async def test_reactive_meta_due_updates_footer():
    """Changing meta.due triggers footer update."""
    board = _make_board()
    app = CardTestApp(board)
    async with app.run_test() as pilot:
        footer = app.query_one("#card-footer", PlainStatic)
        assert ICON_CALENDAR not in str(footer.render())

        future = date.today() + timedelta(days=3)
        board.cards["1"].meta.due = future.isoformat()
        await pilot.pause()

        assert ICON_CALENDAR in str(footer.render())


@pytest.mark.asyncio
async def test_reactive_section_updates_title():
    """Changing sections updates the title display."""
    board = _make_board()
    app = CardTestApp(board)
    async with app.run_test() as pilot:
        card = board.cards["1"]
        old_body = card.sections["Test Card"]
        new_sections = ListNode()
        new_sections["New Title"] = old_body
        card.sections = new_sections
        await pilot.pause()

        title = app.query_one("#card-title", PlainStatic)
        assert "New Title" in str(title.render())


@pytest.mark.asyncio
async def test_watcher_cleanup():
    """Watchers are removed after card widget is removed."""
    board = _make_board()
    app = CardTestApp(board)
    async with app.run_test() as pilot:
        card_node = board.cards["1"]
        sections_watchers_before = len(card_node._watchers.get("sections", []))
        meta_watchers_before = len(card_node._watchers.get("meta", []))

        card_widget = app.query_one(CardWidget)
        await card_widget.remove()
        await pilot.pause()

        sections_watchers_after = len(card_node._watchers.get("sections", []))
        meta_watchers_after = len(card_node._watchers.get("meta", []))

        assert sections_watchers_after == sections_watchers_before - 1
        assert meta_watchers_after == meta_watchers_before - 1


@pytest.mark.asyncio
async def test_labels_in_labels_widget_not_title():
    """Label swatches appear in #card-labels, not in #card-title."""
    board = _make_board(labels=["bug", "urgent"])
    app = CardTestApp(board)
    async with app.run_test():
        labels_widget = app.query_one("#card-labels", PlainStatic)
        title_widget = app.query_one("#card-title", PlainStatic)
        labels_text = str(labels_widget.render())
        title_text = str(title_widget.render())
        assert ICON_COLOR_SWATCH in labels_text
        assert ICON_COLOR_SWATCH not in title_text
        assert "Test Card" in title_text
