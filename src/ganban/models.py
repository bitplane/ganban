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
class Ticket:
    """A ticket file in .all/"""

    id: str
    path: str = ""
    content: MarkdownDoc = field(default_factory=MarkdownDoc)


@dataclass
class TicketLink:
    """A symlink in a column pointing to a ticket."""

    position: str
    slug: str
    ticket_id: str
    path: str = ""
    broken: bool = False


@dataclass
class Column:
    """A column directory on the board."""

    order: str
    name: str
    path: str = ""
    hidden: bool = False
    links: list[TicketLink] = field(default_factory=list)
    content: MarkdownDoc = field(default_factory=MarkdownDoc)


@dataclass
class Board:
    """The full board state."""

    repo_path: str = ""
    columns: list[Column] = field(default_factory=list)
    tickets: dict[str, Ticket] = field(default_factory=dict)
    content: MarkdownDoc = field(default_factory=MarkdownDoc)
