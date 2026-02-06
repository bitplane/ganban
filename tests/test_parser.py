"""Tests for markdown parser."""

from ganban.parser import parse_sections, serialize_sections


def test_parse_sections_title_and_body():
    sections, meta = parse_sections("# Hello\n\nWorld")
    assert sections == [("Hello", "World")]
    assert meta == {}


def test_parse_sections_with_h2s():
    text = "# Title\n\nBody\n\n## Notes\n\nStuff\n\n## Links\n\nMore"
    sections, meta = parse_sections(text)
    assert sections == [("Title", "Body"), ("Notes", "Stuff"), ("Links", "More")]


def test_parse_sections_no_title():
    sections, meta = parse_sections("Just text\n\n## Section\n\nContent")
    assert sections[0] == ("", "Just text")
    assert sections[1] == ("Section", "Content")


def test_parse_sections_front_matter():
    text = "---\ncolor: red\n---\n# Fix bug\n\nDetails"
    sections, meta = parse_sections(text)
    assert meta == {"color": "red"}
    assert sections == [("Fix bug", "Details")]


def test_parse_sections_empty():
    sections, meta = parse_sections("")
    assert sections == [("", "")]
    assert meta == {}


def test_parse_sections_body_only():
    sections, meta = parse_sections("Some text with no headings at all.")
    assert sections == [("", "Some text with no headings at all.")]


def test_parse_sections_invalid_front_matter():
    text = "---\ninvalid: yaml: content: [\n---\n# Title\n"
    sections, meta = parse_sections(text)
    assert meta == {}
    assert sections[0][0] == "Title"


def test_parse_sections_unclosed_front_matter():
    """Front-matter that starts with --- but has no closing --- is ignored."""
    text = "---\nkey: value\n# Title\n"
    sections, meta = parse_sections(text)
    assert meta == {}
    # Unclosed front-matter becomes preamble, title is in second section
    assert sections[0] == ("", "---\nkey: value")
    assert sections[1][0] == "Title"


def test_serialize_sections_basic():
    text = serialize_sections([("Title", "Body"), ("Notes", "Stuff")])
    assert "# Title" in text
    assert "## Notes" in text
    assert "Body" in text
    assert "Stuff" in text


def test_serialize_sections_with_meta():
    text = serialize_sections([("Title", "Body")], {"color": "red"})
    assert text.startswith("---\n")
    assert "color: red" in text


def test_serialize_sections_first_is_h1():
    text = serialize_sections([("First", ""), ("Second", "")])
    lines = text.split("\n")
    h_lines = [line for line in lines if line.startswith("#")]
    assert h_lines[0] == "# First"
    assert h_lines[1] == "## Second"


def test_serialize_sections_empty_title():
    text = serialize_sections([("", "Just body")])
    assert "# " not in text
    assert "Just body" in text


def test_sections_roundtrip():
    original = "---\ntags:\n- a\n- b\n---\n# Board\n\nDesc\n\n## Notes\n\nStuff\n"
    sections, meta = parse_sections(original)
    text = serialize_sections(sections, meta)
    sections2, meta2 = parse_sections(text)
    assert sections == sections2
    assert meta == meta2
