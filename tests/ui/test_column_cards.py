"""Tests for ColumnWidget card reconciliation (external links changes)."""

import pytest
from textual.app import App

from ganban.model.card import archive_card, create_card, move_card
from ganban.model.column import create_column
from ganban.model.node import ListNode, Node
from ganban.ui.board import BoardScreen
from ganban.ui.card import CardWidget
from ganban.ui.column import ColumnWidget

from .conftest import GANBAN_CSS_PATH


def _make_board():
    board = Node(repo_path=".")
    board.sections = ListNode()
    board.sections["Test Board"] = ""
    board.meta = {}
    board.cards = ListNode()
    board.columns = ListNode()
    create_column(board, "Backlog", order="1")
    create_column(board, "Done", order="2")
    create_card(board, "First card", column=board.columns["1"])
    create_card(board, "Second card", column=board.columns["1"])
    board.git = Node(config=Node(ganban=Node(sync_local=False, sync_remote=False, sync_interval=30)))
    return board


class BoardApp(App):
    CSS_PATH = GANBAN_CSS_PATH

    def __init__(self, board):
        super().__init__()
        self.board = board

    def on_mount(self):
        self.push_screen(BoardScreen(self.board))


def _column_widget(app, order: str) -> ColumnWidget:
    return next(cw for cw in app.screen.query(ColumnWidget) if cw.column.order == order)


def _card_ids(column_widget: ColumnWidget) -> list[str]:
    return [c.card_id for c in column_widget.query(CardWidget)]


@pytest.mark.asyncio
async def test_externally_added_card_appears():
    """A card added to the model (e.g. by a sync merge) gets a widget."""
    board = _make_board()
    app = BoardApp(board)
    async with app.run_test() as pilot:
        backlog = _column_widget(app, "1")
        assert _card_ids(backlog) == ["1", "2"]

        create_card(board, "Remote card", column=board.columns["1"])
        await pilot.pause()

        assert _card_ids(backlog) == ["1", "2", "3"]


@pytest.mark.asyncio
async def test_externally_archived_card_disappears():
    """A card removed from links (e.g. archived remotely) unmounts."""
    board = _make_board()
    app = BoardApp(board)
    async with app.run_test() as pilot:
        backlog = _column_widget(app, "1")
        assert _card_ids(backlog) == ["1", "2"]

        archive_card(board, "1")
        await pilot.pause()

        assert _card_ids(backlog) == ["2"]


@pytest.mark.asyncio
async def test_externally_moved_card_switches_columns():
    """A card moved between columns in the model moves between widgets."""
    board = _make_board()
    app = BoardApp(board)
    async with app.run_test() as pilot:
        backlog = _column_widget(app, "1")
        done = _column_widget(app, "2")

        move_card(board, "1", board.columns["2"])
        await pilot.pause()

        assert _card_ids(backlog) == ["2"]
        assert _card_ids(done) == ["1"]


@pytest.mark.asyncio
async def test_externally_reordered_cards_reorder():
    """Reordered links (e.g. from a sync merge) reorder card widgets."""
    board = _make_board()
    app = BoardApp(board)
    async with app.run_test() as pilot:
        backlog = _column_widget(app, "1")
        assert _card_ids(backlog) == ["1", "2"]

        board.columns["1"].links = ("2", "1")
        await pilot.pause()

        assert _card_ids(backlog) == ["2", "1"]


@pytest.mark.asyncio
async def test_reload_style_update_reconciles_cards():
    """A board.update() from a freshly loaded tree reconciles card widgets."""
    board = _make_board()
    app = BoardApp(board)
    async with app.run_test() as pilot:
        backlog = _column_widget(app, "1")
        done = _column_widget(app, "2")

        # Simulate what apply_reload does after a sync merge: build the
        # post-merge state as a separate tree and update in place.
        new_board = board.clone()
        create_card(new_board, "Merged card", column=new_board.columns["2"])
        move_card(new_board, "1", new_board.columns["2"])
        board.update(new_board)
        await pilot.pause()

        assert _card_ids(backlog) == ["2"]
        assert _card_ids(done) == ["3", "1"]
