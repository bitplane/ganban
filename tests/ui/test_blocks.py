"""Tests for reusable block extraction from markdown."""

from ganban.ui.edit.blocks import ExtractedList, extract_bullet_list, reconstruct_body


def test_no_bullet_list():
    body = "Just some text\nwith no bullets."
    result = extract_bullet_list(body)
    assert result.before == body
    assert result.items == []
    assert result.after == ""


def test_simple_bullet_list():
    body = "- first\n- second\n- third"
    result = extract_bullet_list(body)
    assert result.before == ""
    assert result.items == ["- first", "- second", "- third"]
    assert result.after == ""


def test_bullet_list_with_before_and_after():
    body = "Intro text\n\n- alpha\n- beta\n\nOutro text"
    result = extract_bullet_list(body)
    assert result.before == "Intro text\n"
    assert result.items == ["- alpha", "- beta"]
    assert result.after == "\nOutro text"


def test_code_fence_skipped():
    body = "```\n- not a list\n```\n\n- real item"
    result = extract_bullet_list(body)
    assert result.items == ["- real item"]
    assert "```" in result.before


def test_multiple_lists_only_first():
    body = "- first list\n\nSome text\n\n- second list"
    result = extract_bullet_list(body)
    assert result.items == ["- first list"]
    assert "- second list" in result.after


def test_continuation_lines():
    body = "- item one\n  continued\n- item two"
    result = extract_bullet_list(body)
    assert len(result.items) == 2
    assert result.items[0] == "- item one\n  continued"
    assert result.items[1] == "- item two"


def test_round_trip():
    body = "Before\n\n- one\n- two\n- three\n\nAfter"
    result = extract_bullet_list(body)
    reconstructed = reconstruct_body(result)
    assert reconstructed == body


def test_reconstruct_empty():
    result = ExtractedList()
    assert reconstruct_body(result) == ""


def test_reconstruct_items_only():
    result = ExtractedList(items=["- a", "- b"])
    assert reconstruct_body(result) == "- a\n- b"


def test_empty_body():
    result = extract_bullet_list("")
    assert result.before == ""
    assert result.items == []
    assert result.after == ""


def test_asterisk_bullets():
    body = "* first\n* second"
    result = extract_bullet_list(body)
    assert len(result.items) == 2
    assert result.items[0] == "* first"
