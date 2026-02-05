"""Viewer widgets that display content and support update(value)."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Markdown, Static


class TextViewer(Static):
    """Simple text viewer."""

    def update(self, value: str) -> None:
        """Update the displayed text."""
        super().update(value)


class MarkdownViewer(Container):
    """Markdown viewer container."""

    DEFAULT_CSS = """
    MarkdownViewer {
        height: auto;
    }
    """

    def __init__(self, value: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self._value = value

    def compose(self) -> ComposeResult:
        yield Markdown(self._value)

    def update(self, value: str) -> None:
        """Update the displayed markdown."""
        self._value = value
        self.query_one(Markdown).update(value)
