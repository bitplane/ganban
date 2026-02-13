"""Tests for card indicator pure functions."""

from datetime import date, timedelta

from ganban.model.node import ListNode, Node
from ganban.ui.card_indicators import build_footer_text, build_label_text
from ganban.ui.constants import ICON_BODY, ICON_CALENDAR
from ganban.ui.emoji import emoji_for_email


def _make_card(body="", due=None):
    """Create a card node with given body and optional due date."""
    sections = ListNode()
    sections["Title"] = body
    meta_dict = {}
    if due is not None:
        meta_dict["due"] = due.isoformat()
    return sections, Node(**meta_dict)


def _has_red(text):
    """Check if a Rich Text has red styling (on .style or in spans)."""
    if "red" in str(text.style):
        return True
    return any("red" in str(span.style) for span in text._spans)


def test_footer_empty_card():
    """Empty card produces empty footer text."""
    sections, meta = _make_card()
    result = build_footer_text(sections, meta)
    assert result.plain == ""


def test_footer_body_only():
    """Card with body content shows 📝 indicator."""
    sections, meta = _make_card(body="some content")
    result = build_footer_text(sections, meta)
    assert ICON_BODY in result.plain
    assert ICON_CALENDAR not in result.plain


def test_footer_body_whitespace_only():
    """Card with whitespace-only body shows no body indicator."""
    sections, meta = _make_card(body="   \n\t  ")
    result = build_footer_text(sections, meta)
    assert ICON_BODY not in result.plain


def test_footer_due_date():
    """Card with future due date shows 📅 indicator."""
    future = date.today() + timedelta(days=5)
    sections, meta = _make_card(due=future)
    result = build_footer_text(sections, meta)
    assert ICON_CALENDAR in result.plain
    assert "5d" in result.plain
    assert ICON_BODY not in result.plain


def test_footer_overdue_styling():
    """Overdue due date is styled red."""
    past = date.today() - timedelta(days=3)
    sections, meta = _make_card(due=past)
    result = build_footer_text(sections, meta)
    assert ICON_CALENDAR in result.plain
    assert _has_red(result)


def test_footer_due_today_is_overdue():
    """Due date of today is treated as overdue (red)."""
    sections, meta = _make_card(due=date.today())
    result = build_footer_text(sections, meta)
    assert f"{ICON_CALENDAR}0d" in result.plain
    assert _has_red(result)


def test_footer_combined():
    """Card with body and due date shows both indicators."""
    future = date.today() + timedelta(days=2)
    sections, meta = _make_card(body="has body", due=future)
    result = build_footer_text(sections, meta)
    assert ICON_BODY in result.plain
    assert f"{ICON_CALENDAR}2d" in result.plain


def test_footer_assigned_with_custom_emoji():
    """Assigned card shows custom emoji from board meta users."""
    sections, meta = _make_card()
    meta.assigned = "alice@example.com"
    board_meta = Node(users={"Alice": {"emoji": "🤖", "emails": ["alice@example.com"]}})
    result = build_footer_text(sections, meta, board_meta)
    assert "🤖" in result.plain


def test_footer_assigned_hash_fallback():
    """Assigned card shows hash-based emoji when no custom set."""
    sections, meta = _make_card()
    meta.assigned = "alice@example.com"
    board_meta = Node()
    result = build_footer_text(sections, meta, board_meta)
    assert emoji_for_email("alice@example.com") in result.plain


def test_footer_assigned_no_board_meta():
    """No assignee indicator when board_meta not provided."""
    sections, meta = _make_card()
    meta.assigned = "alice@example.com"
    result = build_footer_text(sections, meta)
    assert result.plain == ""


def _make_board_with_label_colors(**label_colors):
    """Create a board with label color overrides."""
    board = Node()
    board.meta = Node()
    board.meta.labels = Node(**{name: Node(color=color) for name, color in label_colors.items()})
    board.labels = Node(**{name: Node(cards=[]) for name in label_colors.keys()})
    return board


def test_label_text_shows_colored_blocks():
    """Cards with labels show colored block characters."""
    meta = Node(labels=["bug", "urgent"])
    board = _make_board_with_label_colors(bug="#800000", urgent="#ff6600")
    result = build_label_text(meta, board)
    assert result.plain == "■■"


def test_label_text_empty_without_card_labels():
    """No label text when card has no labels."""
    meta = Node()
    board = _make_board_with_label_colors(bug="#800000")
    result = build_label_text(meta, board)
    assert result.plain == ""


def test_label_text_uses_hash_color_without_override():
    """Labels without overrides use hash-computed color."""

    meta = Node(labels=["newlabel"])
    board = Node()
    board.meta = Node()
    board.meta.labels = None
    result = build_label_text(meta, board)
    # Should have one block character with hash-computed color
    assert result.plain == "■"
