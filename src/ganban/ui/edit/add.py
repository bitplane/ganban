"""Shared behavior for '+' add-widgets."""

from textual.app import ComposeResult
from textual.widgets import Static

from ganban.ui.edit.editable import EditableText
from ganban.ui.edit.editors import TextEditor


class AddValueMixin:
    """A '+' EditableText that emits entered values and resets.

    Mix into a widget class and implement value_entered(). Set
    editable_classes to style the inner EditableText. Focus bindings
    only take effect on widgets declared can_focus=True; set
    refocus_after_submit to take focus back after a submission (leave
    off when submission moves focus elsewhere, e.g. into a new section).
    """

    BINDINGS = [
        ("space", "start_editing"),
        ("enter", "start_editing"),
    ]

    editable_classes: str = ""
    refocus_after_submit: bool = False

    def action_start_editing(self) -> None:
        self.query_one(EditableText)._start_edit()

    def compose(self) -> ComposeResult:
        yield EditableText("", Static("+"), TextEditor(), placeholder="+", classes=self.editable_classes or None)

    def on_editable_text_changed(self, event: EditableText.Changed) -> None:
        event.stop()
        if event.new_value:
            self.value_entered(event.new_value)
        self.query_one(EditableText).value = ""
        if self.refocus_after_submit:
            self.focus()

    def value_entered(self, value: str) -> None:
        """Handle a newly entered value."""
        raise NotImplementedError
