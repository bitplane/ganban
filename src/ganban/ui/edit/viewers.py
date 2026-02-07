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

    def __init__(self, value: str = "", parser_factory=None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._value = value
        self._parser_factory = parser_factory

    def compose(self) -> ComposeResult:
        if self._parser_factory:
            yield Markdown(self._value, parser_factory=self._parser_factory)
        else:
            yield Markdown(self._value)

    def update(self, value: str) -> None:
        """Update the displayed markdown."""
        self._value = value
        self.query_one(Markdown).update(value)

    def refresh_content(self) -> None:
        """Re-render current value (e.g. after external data changes)."""
        self.query_one(Markdown).update(self._value)
