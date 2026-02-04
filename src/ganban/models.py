"""Data models for ganban boards."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MarkdownDoc:
    """Parsed markdown document with optional front-matter."""

    title: str = ""
    body: str = ""
    sections: dict[str, str] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)
    raw: str = ""


@dataclass
class Card:
    """A card file in .all/"""

    id: str
    path: str = ""
    content: MarkdownDoc = field(default_factory=MarkdownDoc)


@dataclass
class CardLink:
    """A symlink in a column pointing to a card."""

    position: str
    slug: str
    card_id: str
    path: str = ""
    broken: bool = False


@dataclass
class Column:
    """A column directory on the board."""

    order: str
    name: str
    path: str = ""
    hidden: bool = False
    links: list[CardLink] = field(default_factory=list)
    content: MarkdownDoc = field(default_factory=MarkdownDoc)


@dataclass
class Board:
    """The full board state."""

    repo_path: str = ""
    commit: str = ""
    columns: list[Column] = field(default_factory=list)
    cards: dict[str, Card] = field(default_factory=dict)
    content: MarkdownDoc = field(default_factory=MarkdownDoc)
