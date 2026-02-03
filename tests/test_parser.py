"""Tests for markdown parser."""

from ganban.models import MarkdownDoc
from ganban.parser import parse_markdown, serialize_markdown


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


def test_serialize_empty():
    doc = MarkdownDoc()
    assert serialize_markdown(doc) == "\n"


def test_serialize_title_only():
    doc = MarkdownDoc(title="My Title")
    assert serialize_markdown(doc) == "# My Title\n"


def test_serialize_title_and_body():
    doc = MarkdownDoc(title="My Title", body="Some body text.")
    assert serialize_markdown(doc) == "# My Title\n\nSome body text.\n"


def test_serialize_sections():
    doc = MarkdownDoc(
        title="Title",
        body="Body.",
        sections={"Notes": "Some notes.", "Comments": "A comment."},
    )
    result = serialize_markdown(doc)
    assert "# Title" in result
    assert "Body." in result
    assert "## Notes" in result
    assert "Some notes." in result
    assert "## Comments" in result


def test_serialize_front_matter():
    doc = MarkdownDoc(
        title="Title",
        body="Body.",
        meta={"tags": ["one", "two"], "color": "red"},
    )
    result = serialize_markdown(doc)
    assert result.startswith("---\n")
    assert "tags:" in result
    assert "- one" in result
    assert "color: red" in result


def test_roundtrip():
    original = """---
tags:
- alpha
- beta
---
# Test Title

This is the body.

## Notes

Some notes here.

## Links

- link one
"""
    doc = parse_markdown(original)
    result = serialize_markdown(doc)
    doc2 = parse_markdown(result)

    assert doc2.title == doc.title
    assert doc2.body == doc.body
    assert doc2.sections == doc.sections
    assert doc2.meta == doc.meta
