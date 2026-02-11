"""Section editor widget."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.message import Message
from textual.widgets import Static

from ganban.ui.confirm import ConfirmButton
from ganban.ui.edit.editable import EditableText
from ganban.ui.edit.editors import MarkdownEditor, TextEditor
from ganban.ui.edit.viewers import MarkdownViewer


class SectionEditor(Container):
    """Editor for a section with heading and markdown body."""

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

    class DeleteRequested(Message):
        """Emitted when the section delete is confirmed."""

        @property
        def control(self) -> SectionEditor:
            return self._sender

    def __init__(self, heading: str | None, body: str = "", parser_factory=None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._heading = heading
        self._body = body
        self._parser_factory = parser_factory

    @property
    def heading(self) -> str | None:
        return self._heading

    @property
    def body(self) -> str:
        return self._body

    def compose(self) -> ComposeResult:
        if self._heading is not None:
            with Horizontal(classes="section-heading-row"):
                yield EditableText(
                    self._heading,
                    Static(self._heading),
                    TextEditor(),
                    classes="section-heading",
                )
                yield ConfirmButton(classes="section-delete")
        yield EditableText(
            self._body,
            MarkdownViewer(self._body, parser_factory=self._parser_factory),
            MarkdownEditor(),
            classes="section-body",
            clean=False,
        )

    def on_confirm_button_confirmed(self, event: ConfirmButton.Confirmed) -> None:
        event.stop()
        self.post_message(self.DeleteRequested())

    def on_editable_text_changed(self, event: EditableText.Changed) -> None:
        event.stop()
        if "section-heading" in event.control.classes:
            self._heading = event.new_value
            self.post_message(self.HeadingChanged(event.old_value, event.new_value))
        else:
            self._body = event.new_value
            self.post_message(self.BodyChanged(event.old_value, event.new_value))
