"""Markdown document editor widget."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.message import Message
from textual.widgets import Static

from ganban.model.node import ListNode, Node
from ganban.parser import first_title
from ganban.ui.edit.editable import EditableText
from ganban.ui.edit.editors import TextEditor
from ganban.ui.edit.section import SectionEditor
from ganban.ui.edit.viewers import MarkdownViewer
from ganban.ui.watcher import NodeWatcherMixin


class DocHeader(Container):
    """Editable document title with rule underneath."""

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
        self.sections.rename_first_key(event.new_value)
        self.post_message(self.TitleChanged(event.new_value))


class AddSection(Static):
    """Widget to add a new subsection."""

    class SectionCreated(Message):
        """Posted when a new section is created."""

        def __init__(self, heading: str) -> None:
            super().__init__()
            self.heading = heading

    def compose(self) -> ComposeResult:
        yield EditableText("", Static("+"), TextEditor(), placeholder="+")

    def on_editable_text_changed(self, event: EditableText.Changed) -> None:
        event.stop()
        if event.new_value:
            self.post_message(self.SectionCreated(event.new_value))
        self.query_one(EditableText).value = ""


class MarkdownDocEditor(NodeWatcherMixin, Container):
    """Two-panel editor for markdown sections content."""

    class Changed(Message):
        """Emitted when the document content changes."""

    def __init__(
        self,
        sections: ListNode,
        include_header: bool = True,
        meta: Node | None = None,
        parser_factory=None,
        **kwargs,
    ) -> None:
        self._init_watcher()
        super().__init__(**kwargs)
        self.sections = sections
        self._include_header = include_header
        self._meta = meta
        self._parser_factory = parser_factory

    def compose(self) -> ComposeResult:
        if self._include_header:
            yield DocHeader(self.sections)
        items = self.sections.items()
        body = items[0][1]
        subsections = items[1:]
        pf = self._parser_factory
        with Horizontal(id="doc-editor-container"):
            with VerticalScroll(id="doc-editor-left"):
                yield SectionEditor(None, body, parser_factory=pf, id="main-section")
            with VerticalScroll(id="doc-editor-right"):
                for heading, content in subsections:
                    yield SectionEditor(heading, content, parser_factory=pf, classes="subsection")
                yield AddSection()

    def on_mount(self) -> None:
        if self._meta:
            self.node_watch(self._meta, "users", self._on_users_changed)

    def _on_users_changed(self, source_node, key, old, new) -> None:
        for viewer in self.query(MarkdownViewer):
            viewer.refresh_content()

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
        editor = SectionEditor(event.heading, "", parser_factory=self._parser_factory, classes="subsection")
        self.query_one("#doc-editor-right").mount(editor, before=self.query_one(AddSection))
        self.post_message(self.Changed())
