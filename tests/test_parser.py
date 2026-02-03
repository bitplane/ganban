"""Tests for markdown parser."""

from ganban.parser import parse_markdown


def test_parse_empty():
    doc = parse_markdown("")
    assert doc.title == ""
    assert doc.body == ""
    assert doc.sections == {}
    assert doc.meta == {}


def test_parse_title_only():
    doc = parse_markdown("# My Title")
    assert doc.title == "My Title"
    assert doc.body == ""


def test_parse_title_and_body():
    doc = parse_markdown("# My Title\n\nSome body text here.")
    assert doc.title == "My Title"
    assert doc.body == "Some body text here."


def test_parse_sections():
    text = """# Title

Body content.

## Notes

Some notes here.

## Comments

A comment.
"""
    doc = parse_markdown(text)
    assert doc.title == "Title"
    assert doc.body == "Body content."
    assert doc.sections["Notes"] == "Some notes here."
    assert doc.sections["Comments"] == "A comment."


def test_parse_front_matter():
    text = """---
tags:
 - one
 - two
color: red
---
# Title

Body.
"""
    doc = parse_markdown(text)
    assert doc.meta["tags"] == ["one", "two"]
    assert doc.meta["color"] == "red"
    assert doc.title == "Title"
    assert doc.body == "Body."


def test_parse_preserves_raw():
    text = "# Hello\n\nWorld"
    doc = parse_markdown(text)
    assert doc.raw == text


def test_parse_no_title():
    doc = parse_markdown("Just some text without a heading.")
    assert doc.title == ""
    assert doc.body == "Just some text without a heading."


def test_parse_invalid_front_matter():
    text = """---
invalid: yaml: content: [
---
# Title
"""
    doc = parse_markdown(text)
    assert doc.meta == {}
    assert doc.title == "Title"
