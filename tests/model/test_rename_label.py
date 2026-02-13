"""Tests for rename_label and delete_label helpers."""

from ganban.model.card import delete_label, rename_label
from ganban.model.loader import _setup_labels

from tests.model.conftest import _make_board, _make_card, _make_column


def _board_with_labels(card_labels=None, board_label_overrides=None):
    """Build a board with cards that have labels and optional board-level overrides."""
    cards = {}
    for card_id, labels in (card_labels or {}).items():
        card = _make_card(f"Card {card_id}", meta={"labels": labels})
        cards[card_id] = card

    meta = {}
    if board_label_overrides:
        meta["labels"] = board_label_overrides

    board = _make_board(
        "/tmp/fake",
        columns=[_make_column("1", "Backlog", links=list(cards.keys()))],
        cards=cards,
        meta=meta,
    )
    _setup_labels(board)
    return board


def test_rename_label_updates_cards():
    """Card labels list changes when a label is renamed."""
    board = _board_with_labels(
        card_labels={
            "001": ["bug", "feature"],
            "002": ["bug"],
        }
    )
    rename_label(board, "bug", "defect")
    assert "defect" in board.cards["001"].meta.labels
    assert "bug" not in board.cards["001"].meta.labels
    assert "feature" in board.cards["001"].meta.labels
    assert board.cards["002"].meta.labels == ["defect"]


def test_rename_label_updates_board_meta():
    """Board.meta.labels key is renamed."""
    board = _board_with_labels(
        card_labels={"001": ["bug"]},
        board_label_overrides={"bug": {"color": "#ff0000"}},
    )
    rename_label(board, "bug", "defect")
    assert "defect" in board.meta.labels
    assert "bug" not in board.meta.labels.keys()
    assert board.meta.labels.defect.color == "#ff0000"


def test_rename_label_noop_same_name():
    """No change when old and new names match."""
    board = _board_with_labels(card_labels={"001": ["bug"]})
    rename_label(board, "bug", "bug")
    assert board.cards["001"].meta.labels == ["bug"]


def test_rename_label_normalises():
    """'Bug' -> 'feature' works with case differences."""
    board = _board_with_labels(
        card_labels={
            "001": ["Bug"],
            "002": ["BUG"],
        }
    )
    rename_label(board, "Bug", "defect")
    assert board.cards["001"].meta.labels == ["defect"]
    assert board.cards["002"].meta.labels == ["defect"]


def test_rename_label_no_meta_labels():
    """Rename works when board.meta.labels doesn't exist."""
    board = _board_with_labels(card_labels={"001": ["bug"]})
    rename_label(board, "bug", "defect")
    assert board.cards["001"].meta.labels == ["defect"]


def test_rename_label_card_without_labels():
    """Cards without labels are unaffected."""
    board = _board_with_labels(
        card_labels={
            "001": ["bug"],
            "002": [],
        }
    )
    card_no_labels = _make_card("No labels")
    board.cards["003"] = card_no_labels
    rename_label(board, "bug", "defect")
    assert board.cards["001"].meta.labels == ["defect"]


def test_delete_label_removes_from_cards():
    """delete_label removes the label from all cards."""
    board = _board_with_labels(
        card_labels={
            "001": ["bug", "feature"],
            "002": ["bug"],
        }
    )
    delete_label(board, "bug")
    assert board.cards["001"].meta.labels == ["feature"]
    assert board.cards["002"].meta.labels is None


def test_delete_label_removes_from_board_meta():
    """delete_label removes the label from board.meta.labels."""
    board = _board_with_labels(
        card_labels={"001": ["bug"]},
        board_label_overrides={"bug": {"color": "#ff0000"}},
    )
    delete_label(board, "bug")
    assert "bug" not in board.meta.labels.keys()


def test_delete_label_no_meta_labels():
    """delete_label works when board.meta.labels doesn't exist."""
    board = _board_with_labels(card_labels={"001": ["bug"]})
    delete_label(board, "bug")
    assert board.cards["001"].meta.labels is None
