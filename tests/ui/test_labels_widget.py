"""Tests for the LabelsWidget in the card detail bar."""

from ganban.model.node import Node
from ganban.ui.labels import build_label_options
from ganban.ui.palette import color_for_label, get_label_color


def _make_board_with_labels(**label_colors):
    """Build a minimal board with labels.

    Labels are set up in board.meta.labels (color overrides) and
    board.labels (card index, no colors).
    """
    board = Node()
    board.meta = Node()
    board.meta.labels = Node(**{name: Node(color=color) for name, color in label_colors.items()})
    # board.labels only has cards list, no color
    board.labels = Node(**{name: Node(cards=[]) for name in label_colors.keys()})
    return board


def test_build_label_options_excludes_current():
    """Options exclude labels already on the card."""
    board = _make_board_with_labels(bug="#cc0000", feature="#22aa44", urgent="#dd6600")
    options = build_label_options(board, ["bug"])
    values = [v for _, v in options]
    assert "bug" not in values
    assert "feature" in values
    assert "urgent" in values


def test_build_label_options_empty_board():
    """No options when board has no labels."""
    board = Node()
    board.labels = None
    options = build_label_options(board, [])
    assert options == []


def test_build_label_options_all_excluded():
    """Empty options when all labels are already on the card."""
    board = _make_board_with_labels(bug="#cc0000", feature="#22aa44")
    options = build_label_options(board, ["bug", "feature"])
    assert options == []


def test_get_label_color_from_meta_override():
    """Color comes from board.meta.labels when available."""
    board = _make_board_with_labels(bug="#cc0000")
    assert get_label_color("bug", board) == "#cc0000"


def test_get_label_color_falls_back_to_hash():
    """Color falls back to hash when label has no override."""
    board = Node()
    board.meta = Node()
    board.meta.labels = None
    assert get_label_color("newlabel", board) == color_for_label("newlabel")


def test_get_label_color_strips_and_lowercases():
    """Label name is normalised before lookup."""
    board = _make_board_with_labels(bug="#cc0000")
    assert get_label_color(" Bug ", board) == "#cc0000"
