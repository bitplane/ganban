"""Section editor widget."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container

from ganban.ui.edit.label import EditableLabel
from ganban.ui.edit.markdown import EditableMarkdown
from ganban.ui.events import ValueChanged


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
    SectionEditor > .section-heading > Static {
        text-style: bold;
    }
    SectionEditor > EditableMarkdown {
        height: 1fr;
    }
    """

    class HeadingChanged(ValueChanged):
        """Emitted when the section heading changes."""

        @property
        def control(self) -> SectionEditor:
            return self._sender

    class BodyChanged(ValueChanged):
        """Emitted when the section body changes."""

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
        yield EditableLabel(self._heading, click_to_edit=True, classes="section-heading")
        yield EditableMarkdown(self._body)

    def on_editable_label_changed(self, event: EditableLabel.Changed) -> None:
        event.stop()
        self._heading = event.new_value
        self.post_message(self.HeadingChanged(event.old_value, event.new_value))

    def on_editable_markdown_changed(self, event: EditableMarkdown.Changed) -> None:
        event.stop()
        self._body = event.new_value
        self.post_message(self.BodyChanged(event.old_value, event.new_value))
