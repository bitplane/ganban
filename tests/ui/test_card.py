"""Tests for CardWidget."""

from datetime import date, timedelta

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Rule

from ganban.model.node import ListNode, Node
from ganban.ui.card import CardWidget
from ganban.ui.static import PlainStatic


def _make_board(body="", due=None):
    """Create a minimal board with one card."""
    sections = ListNode()
    sections["Test Card"] = body
    meta_dict = {}
    if due is not None:
        meta_dict["due"] = due.isoformat()
    card = Node(sections=sections, meta=meta_dict)

    cards = ListNode()
    cards["1"] = card

    col_sections = ListNode()
    col_sections["Todo"] = ""
    col = Node(order="1", dir_path="1.todo", sections=col_sections, meta={}, links=["1"])

    columns = ListNode()
    columns["1"] = col

    return Node(cards=cards, columns=columns, sections=ListNode(), meta={})


class CardTestApp(App):
    """Minimal app for testing CardWidget."""

    def __init__(self, board):
        super().__init__()
        self.board = board

    def compose(self) -> ComposeResult:
        yield CardWidget("1", self.board)


@pytest.mark.asyncio
async def test_card_has_three_zones():
    """Card composes header rule, title, and footer."""
    board = _make_board()
    app = CardTestApp(board)
    async with app.run_test():
        assert app.query_one("#card-header", Rule) is not None
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
        assert "📝" in str(rendered)


@pytest.mark.asyncio
async def test_footer_shows_due_indicator():
    """Footer shows 📅 when card has due date."""
    future = date.today() + timedelta(days=5)
    board = _make_board(due=future)
    app = CardTestApp(board)
    async with app.run_test():
        footer = app.query_one("#card-footer", PlainStatic)
        rendered = footer.render()
        assert "📅" in str(rendered)


@pytest.mark.asyncio
async def test_reactive_meta_due_updates_footer():
    """Changing meta.due triggers footer update."""
    board = _make_board()
    app = CardTestApp(board)
    async with app.run_test() as pilot:
        footer = app.query_one("#card-footer", PlainStatic)
        assert "📅" not in str(footer.render())

        future = date.today() + timedelta(days=3)
        board.cards["1"].meta.due = future.isoformat()
        await pilot.pause()

        assert "📅" in str(footer.render())


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
