"""Tests for card mutation operations."""

from ganban.model.card import archive_card, create_card, find_card_column, move_card

from .conftest import _make_board, _make_card, _make_column


def test_find_card_column(tmp_path):
    board = _make_board(
        tmp_path,
        cards={"001": _make_card("A"), "002": _make_card("B")},
        columns=[
            _make_column("1", "Backlog", links=["001"]),
            _make_column("2", "Done", links=["002"]),
        ],
    )
    assert find_card_column(board, "001") is board.columns["1"]
    assert find_card_column(board, "002") is board.columns["2"]
    assert find_card_column(board, "999") is None


def test_move_card_cross_column(tmp_path):
    board = _make_board(
        tmp_path,
        cards={"001": _make_card("A")},
        columns=[
            _make_column("1", "Backlog", links=["001"]),
            _make_column("2", "Done"),
        ],
    )
    move_card(board, "001", board.columns["2"])
    assert list(board.columns["1"].links) == []
    assert list(board.columns["2"].links) == ["001"]


def test_move_card_cross_column_with_position(tmp_path):
    board = _make_board(
        tmp_path,
        cards={"001": _make_card("A"), "002": _make_card("B"), "003": _make_card("C")},
        columns=[
            _make_column("1", "Backlog", links=["001"]),
            _make_column("2", "Done", links=["002", "003"]),
        ],
    )
    move_card(board, "001", board.columns["2"], position=1)
    assert list(board.columns["1"].links) == []
    assert list(board.columns["2"].links) == ["002", "001", "003"]


def test_move_card_same_column_reorder(tmp_path):
    """Same-column reorder should be atomic (single assignment)."""
    board = _make_board(
        tmp_path,
        cards={"001": _make_card("A"), "002": _make_card("B"), "003": _make_card("C")},
        columns=[_make_column("1", "Backlog", links=["001", "002", "003"])],
    )
    col = board.columns["1"]

    # Track watcher events - should fire exactly once for the single assignment
    events = []
    col.watch("links", lambda n, k, old, new: events.append(1))

    move_card(board, "001", col, position=2)
    assert list(col.links) == ["002", "003", "001"]
    assert len(events) == 1


def test_move_card_same_column_no_change(tmp_path):
    """Moving to same position should still set links (idempotent)."""
    board = _make_board(
        tmp_path,
        cards={"001": _make_card("A"), "002": _make_card("B")},
        columns=[_make_column("1", "Backlog", links=["001", "002"])],
    )
    move_card(board, "001", board.columns["1"], position=0)
    assert list(board.columns["1"].links) == ["001", "002"]


def test_archive_card(tmp_path):
    board = _make_board(
        tmp_path,
        cards={"001": _make_card("A"), "002": _make_card("B")},
        columns=[_make_column("1", "Backlog", links=["001", "002"])],
    )
    archive_card(board, "001")
    assert list(board.columns["1"].links) == ["002"]
    # Card still exists in cards collection
    assert board.cards["001"] is not None


def test_archive_card_not_in_column(tmp_path):
    """Archiving a card not in any column is a no-op."""
    board = _make_board(
        tmp_path,
        cards={"001": _make_card("A")},
        columns=[_make_column("1", "Backlog")],
    )
    archive_card(board, "001")  # should not raise


def test_create_card_basic(tmp_path):
    board = _make_board(
        tmp_path,
        columns=[_make_column("1", "Backlog")],
    )
    card_id, card = create_card(board, "New card", "Body")
    assert card_id == "1"
    assert board.cards["1"] is not None
    assert "New card" in card.sections.keys()
    assert list(board.columns["1"].links) == ["1"]


def test_create_card_at_position(tmp_path):
    board = _make_board(
        tmp_path,
        cards={"1": _make_card("A")},
        columns=[_make_column("1", "Backlog", links=["1"])],
    )
    card_id, _ = create_card(board, "B", column=board.columns["1"], position=0)
    assert list(board.columns["1"].links) == [card_id, "1"]
