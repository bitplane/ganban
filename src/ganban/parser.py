"""Parse markdown documents with front-matter."""

import re

import yaml

from ganban.models import MarkdownDoc


def parse_markdown(text: str) -> MarkdownDoc:
    """Parse a markdown document into a MarkdownDoc."""
    raw = text
    meta: dict = {}
    title = ""
    body = ""
    sections: dict[str, str] = {}

    # Extract front-matter
    text, meta = _extract_front_matter(text)

    # Split into lines for processing
    lines = text.split("\n")

    current_section: str | None = None
    current_content: list[str] = []
    found_title = False

    for line in lines:
        # Check for h1 heading (title)
        if not found_title and line.startswith("# "):
            title = line[2:].strip()
            found_title = True
            continue

        # Check for h2 heading (section)
        if line.startswith("## "):
            # Save previous section/body
            if current_section is None and found_title:
                body = "\n".join(current_content).strip()
            elif current_section is not None:
                sections[current_section] = "\n".join(current_content).strip()

            current_section = line[3:].strip()
            current_content = []
            continue

        current_content.append(line)

    # Save final section/body
    if current_section is None:
        body = "\n".join(current_content).strip()
    else:
        sections[current_section] = "\n".join(current_content).strip()

    return MarkdownDoc(
        title=title,
        body=body,
        sections=sections,
        meta=meta,
        raw=raw,
    )


def serialize_markdown(doc: MarkdownDoc) -> str:
    """Serialize a MarkdownDoc back to markdown text."""
    parts: list[str] = []

    # Front-matter
    if doc.meta:
        parts.append("---")
        parts.append(yaml.dump(doc.meta, default_flow_style=False, sort_keys=False).rstrip())
        parts.append("---")
        parts.append("")

    # Title
    if doc.title:
        parts.append(f"# {doc.title}")
        parts.append("")

    # Body
    if doc.body:
        parts.append(doc.body)
        parts.append("")

    # Sections
    for heading, content in doc.sections.items():
        parts.append(f"## {heading}")
        parts.append("")
        if content:
            parts.append(content)
            parts.append("")

    return "\n".join(parts).rstrip() + "\n"


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
