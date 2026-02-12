"""Tests for the LabelsWidget in the card detail bar."""

from ganban.model.node import Node
from ganban.ui.labels import build_label_options, _label_color
from ganban.palette import color_for_label


def _make_board_labels(**labels):
    """Build a minimal board with a labels index."""
    board = Node()
    board.labels = Node(**{name: Node(color=color, cards=[]) for name, color in labels.items()})
    return board


def test_build_label_options_excludes_current():
    """Options exclude labels already on the card."""
    board = _make_board_labels(bug="#cc0000", feature="#22aa44", urgent="#dd6600")
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
    board = _make_board_labels(bug="#cc0000", feature="#22aa44")
    options = build_label_options(board, ["bug", "feature"])
    assert options == []


def test_label_color_from_board_index():
    """Color comes from board.labels when available."""
    board = _make_board_labels(bug="#cc0000")
    assert _label_color("bug", board) == "#cc0000"


def test_label_color_falls_back_to_hash():
    """Color falls back to hash when label not in board index."""
    board = _make_board_labels()
    assert _label_color("newlabel", board) == color_for_label("newlabel")


def test_label_color_strips_and_lowercases():
    """Label name is normalised before lookup."""
    board = _make_board_labels(bug="#cc0000")
    assert _label_color(" Bug ", board) == "#cc0000"
