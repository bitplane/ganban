"""Markdown document editor widget."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.message import Message
from textual.widgets import Static

from ganban.model.node import ListNode
from ganban.parser import first_title
from ganban.ui.edit.editable import EditableText
from ganban.ui.edit.editors import TextEditor
from ganban.ui.edit.section import SectionEditor


def _rename_first_key(sections: ListNode, new_title: str) -> None:
    """Rename the first key in a sections ListNode by rebuilding it."""
    items = sections.items()
    for key, _ in items:
        sections[key] = None
    if items:
        items[0] = (new_title, items[0][1])
    for key, val in items:
        sections[key] = val


class DocHeader(Container):
    """Editable document title with rule underneath."""

    DEFAULT_CSS = """
    DocHeader {
        width: 100%;
        height: auto;
    }
    DocHeader #doc-title {
        width: 100%;
        height: auto;
        text-style: bold;
        border-bottom: solid $primary;
    }
    DocHeader #doc-title > ContentSwitcher > Static {
        text-style: bold;
    }
    """

    class TitleChanged(Message):
        """Emitted when the title changes."""

        def __init__(self, new_title: str) -> None:
            super().__init__()
            self.new_title = new_title

    def __init__(self, sections: ListNode) -> None:
        super().__init__()
        self.sections = sections

    def compose(self) -> ComposeResult:
        title = first_title(self.sections)
        yield EditableText(
            title,
            Static(title),
            TextEditor(),
            id="doc-title",
        )

    def on_editable_text_changed(self, event: EditableText.Changed) -> None:
        event.stop()
        _rename_first_key(self.sections, event.new_value)
        self.post_message(self.TitleChanged(event.new_value))


class AddSection(Static):
    """Widget to add a new subsection."""

    class SectionCreated(Message):
        """Posted when a new section is created."""

        def __init__(self, heading: str) -> None:
            super().__init__()
            self.heading = heading

    DEFAULT_CSS = """
    AddSection {
        width: 100%;
        height: auto;
        border: dashed $surface-lighten-2;
    }
    AddSection > EditableText > ContentSwitcher > Static {
        text-align: center;
        color: $text-muted;
    }
    """

    def compose(self) -> ComposeResult:
        yield EditableText("", Static("+"), TextEditor(), placeholder="+")

    def on_editable_text_changed(self, event: EditableText.Changed) -> None:
        event.stop()
        if event.new_value:
            self.post_message(self.SectionCreated(event.new_value))
        self.query_one(EditableText).value = ""


class MarkdownDocEditor(Container):
    """Two-panel editor for markdown sections content."""

    DEFAULT_CSS = """
    MarkdownDocEditor {
        width: 100%;
        height: 100%;
        layout: vertical;
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

    def __init__(self, sections: ListNode, include_header: bool = True, **kwargs) -> None:
        super().__init__(**kwargs)
        self.sections = sections
        self._include_header = include_header

    def compose(self) -> ComposeResult:
        if self._include_header:
            yield DocHeader(self.sections)
        items = self.sections.items()
        body = items[0][1]
        subsections = items[1:]
        with Horizontal(id="doc-editor-container"):
            with VerticalScroll(id="doc-editor-left"):
                yield SectionEditor(None, body, id="main-section")
            with VerticalScroll(id="doc-editor-right"):
                for heading, content in subsections:
                    yield SectionEditor(heading, content, classes="subsection")
                yield AddSection()

    def on_doc_header_title_changed(self, event: DocHeader.TitleChanged) -> None:
        event.stop()
        self.post_message(self.Changed())

    def on_section_editor_heading_changed(self, event: SectionEditor.HeadingChanged) -> None:
        """Update sections when a section heading changes."""
        event.stop()
        old_key = event.old_value
        new_key = event.new_value
        content = self.sections[old_key] or ""
        self.sections[old_key] = None
        self.sections[new_key] = content
        self.post_message(self.Changed())

    def on_section_editor_body_changed(self, event: SectionEditor.BodyChanged) -> None:
        """Update sections when a body changes."""
        event.stop()
        editor = event.control
        if editor.id == "main-section":
            self.sections[first_title(self.sections)] = event.new_value
        else:
            self.sections[editor.heading] = event.new_value
        self.post_message(self.Changed())

    def on_add_section_section_created(self, event: AddSection.SectionCreated) -> None:
        """Add a new subsection."""
        event.stop()
        self.sections[event.heading] = ""
        editor = SectionEditor(event.heading, "", classes="subsection")
        self.query_one("#doc-editor-right").mount(editor, before=self.query_one(AddSection))
        self.post_message(self.Changed())
