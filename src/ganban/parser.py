"""Parse markdown documents with front-matter."""

import re

import yaml

_H1_OR_H2 = re.compile(r"^(#{1,2}) ", re.MULTILINE)


def _demote_headings(text: str) -> str:
    """Convert # and ## at start of lines to ### to prevent structural conflicts.

    Skips lines inside fenced code blocks.
    """
    result = []
    in_fence = False
    for line in text.split("\n"):
        if line.startswith("```"):
            in_fence = not in_fence
        if not in_fence:
            line = _H1_OR_H2.sub("### ", line)
        result.append(line)
    return "\n".join(result)


def parse_sections(text: str) -> tuple[list[tuple[str, str]], dict]:
    """Parse markdown into an ordered list of (title, body) sections plus meta.

    Returns (sections, meta) where:
    - sections is a list of (title, body) tuples
    - First section is the h1 (title may be "" if no h1)
    - Subsequent sections are h2s
    - meta is the front-matter dict (or {})
    """
    text, meta = _extract_front_matter(text)
    lines = text.split("\n")

    sections: list[tuple[str, str]] = []
    current_title: str | None = None
    current_lines: list[str] = []
    preamble_lines: list[str] = []
    in_heading = False
    in_code_fence = False

    for line in lines:
        if line.startswith("```"):
            in_code_fence = not in_code_fence
        if not in_code_fence and (line.startswith("# ") or line.startswith("## ")):
            if in_heading:
                sections.append((current_title or "", "\n".join(current_lines).strip()))
            is_h1 = line.startswith("# ") and not line.startswith("## ")
            current_title = line[2:].strip() if is_h1 else line[3:].strip()
            current_lines = []
            in_heading = True
            continue
        if in_heading:
            current_lines.append(line)
        else:
            preamble_lines.append(line)

    if in_heading:
        # Prepend preamble as ("", body) if there was text before the first heading
        preamble = "\n".join(preamble_lines).strip()
        if preamble:
            sections.insert(0, ("", preamble))
        sections.append((current_title or "", "\n".join(current_lines).strip()))
    else:
        sections.append(("", "\n".join(preamble_lines).strip()))

    return sections, meta


def serialize_sections(sections: list[tuple[str, str]], meta: dict | None = None) -> str:
    """Serialize sections and meta back to markdown text.

    First section becomes # heading, rest become ## headings.
    Meta becomes YAML front-matter if non-empty.
    """
    parts: list[str] = []

    if meta:
        parts.append("---")
        parts.append(yaml.dump(meta, default_flow_style=False, sort_keys=False).rstrip())
        parts.append("---")
        parts.append("")

    for i, (title, body) in enumerate(sections):
        if title:
            prefix = "#" if i == 0 else "##"
            parts.append(f"{prefix} {title}")
            parts.append("")
        if body:
            parts.append(_demote_headings(body))
            parts.append("")

    return "\n".join(parts).rstrip() + "\n"


def first_title(sections) -> str:
    """Get the title (first key) of a sections ListNode, or empty string."""
    keys = sections.keys()
    return keys[0] if keys else ""


def first_body(sections) -> str:
    """Get the body (first value) of a sections ListNode, or empty string."""
    keys = sections.keys()
    if not keys:
        return ""
    value = sections[keys[0]]
    return value if isinstance(value, str) else ""


def _extract_front_matter(text: str) -> tuple[str, dict]:
    """Extract YAML front-matter from text. Returns (remaining_text, meta)."""
    if not text.startswith("---"):
        return text, {}

    # Find the closing ---
    match = re.match(r"^---\n(.*?)\n---\n?", text, re.DOTALL)
    if not match:
        return text, {}

    yaml_content = match.group(1)
    remaining = text[match.end() :]

    try:
        meta = yaml.safe_load(yaml_content) or {}
    except yaml.YAMLError:
        meta = {}

    return remaining, meta
