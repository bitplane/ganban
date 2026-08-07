"""Tests for BoardScreen column reconciliation (external membership changes)."""

import pytest
from textual.app import App

from ganban.model.column import create_column
from ganban.model.node import ListNode, Node
from ganban.parser import first_title
from ganban.ui.board import BoardScreen
from ganban.ui.column import AddColumn, ColumnWidget

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
    board.git = Node(config=Node(ganban=Node(sync_local=False, sync_remote=False, sync_interval=30)))
    return board


class BoardApp(App):
    CSS_PATH = GANBAN_CSS_PATH

    def __init__(self, board):
        super().__init__()
        self.board = board

    def on_mount(self):
        self.push_screen(BoardScreen(self.board))


@pytest.mark.asyncio
async def test_externally_added_column_appears():
    """A column added to the model (e.g. by a sync merge) gets a widget."""
    board = _make_board()
    app = BoardApp(board)
    async with app.run_test() as pilot:
        assert len(app.screen.query(ColumnWidget)) == 2

        create_column(board, "Review", order="3")
        await pilot.pause()

        widgets = list(app.screen.query(ColumnWidget))
        assert len(widgets) == 3
        assert [first_title(w.column.sections) for w in widgets] == ["Backlog", "Done", "Review"]


@pytest.mark.asyncio
async def test_externally_removed_column_disappears():
    """A column removed from the model (e.g. archived remotely) unmounts."""
    board = _make_board()
    app = BoardApp(board)
    async with app.run_test() as pilot:
        assert len(app.screen.query(ColumnWidget)) == 2

        board.columns["2"] = None
        await pilot.pause()

        widgets = list(app.screen.query(ColumnWidget))
        assert [first_title(w.column.sections) for w in widgets] == ["Backlog"]


@pytest.mark.asyncio
async def test_add_column_widget_mounts_new_column():
    """Creating a column via AddColumn mounts a widget through the watcher."""
    board = _make_board()
    app = BoardApp(board)
    async with app.run_test() as pilot:
        app.screen.query_one(AddColumn).value_entered("Review")
        await pilot.pause()

        widgets = list(app.screen.query(ColumnWidget))
        assert [first_title(w.column.sections) for w in widgets] == ["Backlog", "Done", "Review"]


@pytest.mark.asyncio
async def test_archive_request_unmounts_column_widget():
    """The archive handler mutates the model; reconciliation unmounts."""
    board = _make_board()
    app = BoardApp(board)
    async with app.run_test() as pilot:
        widget = next(w for w in app.screen.query(ColumnWidget) if w.column.order == "2")
        app.screen.on_column_widget_archive_requested(ColumnWidget.ArchiveRequested(widget))
        await pilot.pause()

        widgets = list(app.screen.query(ColumnWidget))
        assert [first_title(w.column.sections) for w in widgets] == ["Backlog"]
