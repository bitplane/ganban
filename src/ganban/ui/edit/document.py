"""Markdown document editor widget."""

from __future__ import annotations

import re
from dataclasses import dataclass

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import Static

from ganban.model.node import ListNode, Node
from ganban.parser import first_title
from ganban.ui.edit.editable import EditableText
from ganban.ui.edit.editors import TextEditor
from ganban.ui.edit.section import SectionEditor
from ganban.ui.edit.viewers import MarkdownViewer
from ganban.ui.watcher import NodeWatcherMixin


@dataclass
class EditorType:
    """Describes an available editor for markdown sections."""

    icon: str
    name: str
    pattern: re.Pattern
    editor_class: type = SectionEditor


DEFAULT_EDITOR_TYPES = [EditorType("📝", "Markdown", re.compile(r".*"))]


class DocHeader(NodeWatcherMixin, Container):
    """Editable document title with rule underneath."""

    class TitleChanged(Message):
        """Emitted when the title changes."""

        def __init__(self, new_title: str) -> None:
            super().__init__()
            self.new_title = new_title

    def __init__(self, sections: ListNode) -> None:
        self._init_watcher()
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

    def on_mount(self) -> None:
        parent = self.sections._parent
        if parent is not None and self.sections._key is not None:
            self.node_watch(parent, self.sections._key, self._on_sections_changed)

    def _on_sections_changed(self, node, key, old, new) -> None:
        keys = self.sections.keys()
        if not keys:
            return
        new_title = keys[0]
        title_widget = self.query_one("#doc-title", EditableText)
        if title_widget.value != new_title:
            title_widget.value = new_title

    def on_editable_text_changed(self, event: EditableText.Changed) -> None:
        event.stop()
        if event.new_value == first_title(self.sections):
            return
        with self.suppressing():
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
        editor_types: list[EditorType] | None = None,
        **kwargs,
    ) -> None:
        self._init_watcher()
        super().__init__(**kwargs)
        self.sections = sections
        self._include_header = include_header
        self._meta = meta
        self._parser_factory = parser_factory
        self.editor_types = editor_types or DEFAULT_EDITOR_TYPES

    def compose(self) -> ComposeResult:
        if self._include_header:
            yield DocHeader(self.sections)
        items = self.sections.items()
        body = items[0][1]
        subsections = items[1:]
        pf = self._parser_factory
        et = self.editor_types
        with Horizontal(id="doc-editor-container"):
            with Vertical(id="doc-editor-left"):
                yield SectionEditor(None, body, parser_factory=pf, id="main-section")
            with VerticalScroll(id="doc-editor-right"):
                for heading, content in subsections:
                    yield SectionEditor(heading, content, parser_factory=pf, editor_types=et, classes="subsection")
                yield AddSection()

    def on_mount(self) -> None:
        if self._meta:
            self.node_watch(self._meta, "users", self._on_users_changed)
        parent = self.sections._parent
        if parent is not None and self.sections._key is not None:
            self.node_watch(parent, self.sections._key, self._on_sections_changed)

    def _on_sections_changed(self, node, key, old, new) -> None:
        self.call_later(self.recompose)

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
        with self.suppressing():
            self.sections[old_key] = None
            actual_key = self.sections.add(new_key, content)
        if actual_key != new_key:
            event.control._heading = actual_key
            heading_et = event.control.query_one(".section-heading", EditableText)
            heading_et._value = actual_key
            heading_et._update_viewer()
        self.post_message(self.Changed())

    def on_section_editor_body_changed(self, event: SectionEditor.BodyChanged) -> None:
        """Update sections when a body changes."""
        event.stop()
        editor = event.control
        with self.suppressing():
            if editor.id == "main-section":
                self.sections[first_title(self.sections)] = event.new_value
            else:
                self.sections[editor.heading] = event.new_value
        self.post_message(self.Changed())

    def on_section_editor_delete_requested(self, event: SectionEditor.DeleteRequested) -> None:
        """Remove a subsection."""
        event.stop()
        editor = event.control
        with self.suppressing():
            self.sections[editor.heading] = None
        editor.remove()
        self.post_message(self.Changed())

    def _focus_section_body(self, section: SectionEditor) -> None:
        """Focus the body editor of a section."""
        section.query_one(".section-body", EditableText).focus()

    def on_add_section_section_created(self, event: AddSection.SectionCreated) -> None:
        """Add a new subsection."""
        event.stop()
        with self.suppressing():
            actual_key = self.sections.add(event.heading, "")
        editor = SectionEditor(
            actual_key, "", parser_factory=self._parser_factory, editor_types=self.editor_types, classes="subsection"
        )
        self.query_one("#doc-editor-right").mount(editor, before=self.query_one(AddSection))
        self.call_after_refresh(self._focus_section_body, editor)
        self.post_message(self.Changed())
