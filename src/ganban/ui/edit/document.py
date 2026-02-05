"""Markdown document editor widget."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.message import Message
from textual.widgets import Static

from ganban.ui.edit.editable import EditableText
from ganban.ui.edit.editors import TextEditor
from ganban.ui.edit.section import SectionEditor

if TYPE_CHECKING:
    from ganban.models import MarkdownDoc


class MarkdownDocEditor(Container):
    """Two-panel editor for MarkdownDoc content."""

    DEFAULT_CSS = """
    MarkdownDocEditor {
        width: 100%;
        height: 100%;
        layout: vertical;
    }
    #doc-title {
        width: 100%;
        height: auto;
        text-style: bold;
        border-bottom: solid $primary;
    }
    #doc-title > ContentSwitcher > Static {
        text-style: bold;
    }
    #doc-editor-container {
        width: 100%;
        height: 1fr;
    }
    #doc-editor-left {
        width: 2fr;
        height: 100%;
        padding-right: 1;
    }
    #doc-editor-right {
        width: 1fr;
        height: 100%;
        border-left: tall $surface-lighten-1;
        padding-left: 1;
    }
    #main-section {
        height: auto;
    }
    """

    class Changed(Message):
        """Emitted when the document content changes."""

    def __init__(self, doc: MarkdownDoc) -> None:
        super().__init__()
        self.doc = doc

    def compose(self) -> ComposeResult:
        yield EditableText(
            self.doc.title,
            Static(self.doc.title),
            TextEditor(),
            id="doc-title",
        )
        with Horizontal(id="doc-editor-container"):
            with VerticalScroll(id="doc-editor-left"):
                yield SectionEditor(None, self.doc.body, id="main-section")
            with VerticalScroll(id="doc-editor-right"):
                for heading, content in self.doc.sections.items():
                    yield SectionEditor(heading, content, classes="subsection")

    def on_editable_text_changed(self, event: EditableText.Changed) -> None:
        """Update doc when title changes."""
        if event.control.id == "doc-title":
            event.stop()
            self.doc.title = event.new_value
            self.post_message(self.Changed())

    def on_section_editor_heading_changed(self, event: SectionEditor.HeadingChanged) -> None:
        """Update doc when a section heading changes."""
        event.stop()
        content = self.doc.sections.pop(event.old_value, "")
        self.doc.sections[event.new_value] = content
        self.post_message(self.Changed())

    def on_section_editor_body_changed(self, event: SectionEditor.BodyChanged) -> None:
        """Update doc when a body changes."""
        event.stop()
        editor = event.control
        if editor.id == "main-section":
            self.doc.body = event.new_value
        else:
            self.doc.sections[editor.heading] = event.new_value
        self.post_message(self.Changed())
