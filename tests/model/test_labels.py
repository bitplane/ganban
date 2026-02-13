"""Tests for the computed board.labels index."""

from ganban.model.loader import _setup_labels, normalise_label
from ganban.ui.palette import color_for_label, get_label_color

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


def test_board_labels_populated():
    """Cards with labels produce board.labels entries."""
    board = _board_with_labels(card_labels={"001": ["bug", "urgent"]})
    assert board.labels.bug is not None
    assert board.labels.urgent is not None


def test_board_labels_has_cards_only():
    """board.labels only contains card lists, no color (that's a UI concern)."""
    board = _board_with_labels(card_labels={"001": ["bug"]})
    assert board.labels.bug.cards == ["001"]
    # Color is NOT in the index - it's computed by UI
    assert board.labels.bug.color is None


def test_board_labels_cards_list():
    """Cards list contains the correct card IDs."""
    board = _board_with_labels(
        card_labels={
            "001": ["bug"],
            "002": ["bug", "feature"],
        }
    )
    assert sorted(board.labels.bug.cards) == ["001", "002"]
    assert board.labels.feature.cards == ["002"]


def test_board_labels_normalised():
    """'Bug' and 'bug' merge into one entry."""
    board = _board_with_labels(
        card_labels={
            "001": ["Bug"],
            "002": ["bug"],
        }
    )
    assert board.labels.bug is not None
    assert sorted(board.labels.bug.cards) == ["001", "002"]
    # No separate "Bug" entry
    assert getattr(board.labels, "Bug") is None or getattr(board.labels, "Bug") is board.labels.bug


def test_board_labels_meta_only_not_in_index():
    """Board meta labels without cards do NOT appear in board.labels.

    board.labels only contains labels that are actually on cards.
    Meta-only labels are just color overrides, not data.
    """
    board = _board_with_labels(
        card_labels={},
        board_label_overrides={"wontfix": {"color": "#999999"}},
    )
    # wontfix has no cards, so it's not in board.labels
    assert board.labels.wontfix is None
    # But it IS in board.meta.labels
    assert board.meta.labels.wontfix.color == "#999999"


def test_board_labels_updates_on_card_change():
    """Mutating card.meta.labels triggers recompute."""
    board = _board_with_labels(card_labels={"001": ["bug"]})
    assert board.labels.bug is not None
    assert board.labels.feature is None

    # Add a label to the card
    card = board.cards["001"]
    card.meta.labels = ["bug", "feature"]

    assert board.labels.feature is not None
    assert "001" in board.labels.feature.cards


def test_get_label_color_uses_override():
    """get_label_color returns override if present, else computed hash."""
    board = _board_with_labels(
        card_labels={"001": ["bug"]},
        board_label_overrides={"bug": {"color": "#ff0000"}},
    )
    # Override takes precedence
    assert get_label_color("bug", board) == "#ff0000"
    # No override uses hash
    assert get_label_color("feature", board) == color_for_label("feature")


def test_get_label_color_no_override():
    """get_label_color returns computed hash when no override."""
    board = _board_with_labels(card_labels={"001": ["bug"]})
    assert get_label_color("bug", board) == color_for_label("bug")


def test_normalise_label():
    """normalise_label strips and lowercases."""
    assert normalise_label("  Bug ") == "bug"
    assert normalise_label("URGENT") == "urgent"
    assert normalise_label("feature") == "feature"
