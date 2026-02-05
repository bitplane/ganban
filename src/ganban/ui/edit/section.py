"""Section editor widget."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container
from textual.message import Message
from textual.widgets import Static

from ganban.ui.edit.editable import EditableText
from ganban.ui.edit.editors import MarkdownEditor, TextEditor
from ganban.ui.edit.viewers import MarkdownViewer


class SectionEditor(Container):
    """Editor for a section with heading and markdown body."""

    DEFAULT_CSS = """
    SectionEditor {
        width: 100%;
        height: 1fr;
    }
    SectionEditor > .section-heading {
        width: 100%;
        height: auto;
        text-style: bold;
        border-bottom: solid $primary-darken-2;
    }
    SectionEditor > .section-heading > ContentSwitcher > Static {
        text-style: bold;
    }
    SectionEditor > .section-body {
        height: 1fr;
    }
    SectionEditor > .section-body > ContentSwitcher {
        height: 100%;
    }
    SectionEditor > .section-body #view {
        height: 100%;
        padding: 0;
    }
    SectionEditor > .section-body #view MarkdownViewer {
        padding: 0;
        margin: 0;
    }
    SectionEditor > .section-body #view Markdown {
        padding: 0;
        margin: 0;
    }
    SectionEditor > .section-body #edit {
        height: 100%;
    }
    """

    class HeadingChanged(Message):
        """Emitted when the section heading changes."""

        def __init__(self, old_value: str, new_value: str) -> None:
            super().__init__()
            self.old_value = old_value
            self.new_value = new_value

        @property
        def control(self) -> SectionEditor:
            return self._sender

    class BodyChanged(Message):
        """Emitted when the section body changes."""

        def __init__(self, old_value: str, new_value: str) -> None:
            super().__init__()
            self.old_value = old_value
            self.new_value = new_value

        @property
        def control(self) -> SectionEditor:
            return self._sender

    def __init__(self, heading: str, body: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self._heading = heading
        self._body = body

    @property
    def heading(self) -> str:
        return self._heading

    @property
    def body(self) -> str:
        return self._body

    def compose(self) -> ComposeResult:
        yield EditableText(
            self._heading,
            Static(self._heading),
            TextEditor(),
            classes="section-heading",
        )
        yield EditableText(
            self._body,
            MarkdownViewer(self._body),
            MarkdownEditor(),
            classes="section-body",
            clean=False,
        )

    def on_editable_text_changed(self, event: EditableText.Changed) -> None:
        event.stop()
        if "section-heading" in event.control.classes:
            self._heading = event.new_value
            self.post_message(self.HeadingChanged(event.old_value, event.new_value))
        else:
            self._body = event.new_value
            self.post_message(self.BodyChanged(event.old_value, event.new_value))
