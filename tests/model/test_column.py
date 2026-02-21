"""Tests for column mutation operations."""

from ganban.model.column import (
    archive_column,
    build_column_path,
    create_column,
    move_column,
    rename_column,
    slugify,
)
from ganban.parser import first_title

from .conftest import _make_board, _make_column


def test_create_column_basic(tmp_path):
    board = _make_board(tmp_path)
    col = create_column(board, "Backlog")
    assert col.order == "1"
    assert first_title(col.sections) == "Backlog"
    assert col.dir_path == "1.backlog"
    assert len(board.columns) == 1


def test_create_column_auto_order(tmp_path):
    board = _make_board(tmp_path, columns=[_make_column("1", "Backlog")])
    col = create_column(board, "Done")
    assert col.order == "2"
    assert len(board.columns) == 2


def test_create_column_hidden(tmp_path):
    board = _make_board(tmp_path)
    col = create_column(board, "Archive", hidden=True)
    assert col.hidden is True
    assert col.dir_path.startswith(".")


def test_move_column(tmp_path):
    board = _make_board(
        tmp_path,
        columns=[
            _make_column("1", "Backlog"),
            _make_column("2", "Doing"),
            _make_column("3", "Done"),
        ],
    )
    doing = board.columns["2"]
    move_column(board, doing, 0)
    names = [first_title(c.sections) for c in board.columns]
    assert names == ["Doing", "Backlog", "Done"]
    # Orders should be renumbered
    orders = board.columns.keys()
    assert orders == ["1", "2", "3"]


def test_move_column_to_end(tmp_path):
    board = _make_board(
        tmp_path,
        columns=[
            _make_column("1", "Backlog"),
            _make_column("2", "Doing"),
            _make_column("3", "Done"),
        ],
    )
    backlog = board.columns["1"]
    move_column(board, backlog, 2)
    names = [first_title(c.sections) for c in board.columns]
    assert names == ["Doing", "Done", "Backlog"]


def test_move_column_updates_dir_path(tmp_path):
    board = _make_board(
        tmp_path,
        columns=[
            _make_column("1", "Backlog"),
            _make_column("2", "Done"),
        ],
    )
    done = board.columns["2"]
    move_column(board, done, 0)
    assert done.dir_path == "1.done"
    backlog = board.columns["2"]
    assert backlog.dir_path == "2.backlog"


def test_archive_column(tmp_path):
    board = _make_board(
        tmp_path,
        columns=[
            _make_column("1", "Backlog"),
            _make_column("2", "Done"),
        ],
    )
    archive_column(board, "1")
    assert board.columns["1"] is None
    assert len(board.columns) == 1


def test_rename_column(tmp_path):
    board = _make_board(
        tmp_path,
        columns=[_make_column("1", "Backlog")],
    )
    col = board.columns["1"]
    rename_column(board, col, "Archive")
    assert first_title(col.sections) == "Archive"
    assert col.dir_path == "1.archive"


def test_slugify_basic():
    assert slugify("Hello World") == "hello-world"


def test_slugify_special_chars():
    assert slugify("What: is this?") == "what-is-this"
    assert slugify("Test!") == "test"
    assert slugify("{foo}") == "foo"
    assert slugify("a.b.c") == "a-b-c"


def test_slugify_multiple_spaces():
    assert slugify("hello    world") == "hello-world"
    assert slugify("a - b - c") == "a-b-c"


def test_slugify_leading_trailing():
    assert slugify("  hello  ") == "hello"
    assert slugify("---test---") == "test"
    assert slugify("!hello!") == "hello"


def test_slugify_empty():
    assert slugify("") == "untitled"
    assert slugify("   ") == "untitled"
    assert slugify("!!!") == "untitled"


def test_build_column_path_normal():
    assert build_column_path("1", "Backlog") == "1.backlog"


def test_build_column_path_hidden():
    assert build_column_path("1", "Archive", hidden=True) == ".1.archive"
