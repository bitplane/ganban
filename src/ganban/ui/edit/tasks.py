"""Task list editor widget."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.events import Click
from textual.message import Message
from textual.widgets import Static

from ganban.ui.confirm import ConfirmButton
from ganban.ui.constants import ICON_CHECKED, ICON_UNCHECKED
from ganban.ui.edit.blocks import extract_bullet_list, reconstruct_body
from ganban.ui.edit.editable import EditableText
from ganban.ui.edit.editors import TextEditor
from ganban.ui.edit.section import SectionEditor
from ganban.ui.edit.viewers import MarkdownViewer

if TYPE_CHECKING:
    from ganban.ui.edit.document import EditorType

# Matches: "- [ ] task text" or "- [x] task text" (also *, +)
# Groups: (1) bullet prefix "- ", (2) checkbox char " " or "x"/"X", (3) task text
_TASK_RE = re.compile(r"^([\-\*\+]\s+)\[([ xX])\]\s*(.*)", re.DOTALL)


def _parse_task(item: str) -> tuple[bool, str, str]:
    """Parse a task item into (checked, bullet_prefix, task_text).

    Returns (False, "", full_item) if no checkbox found.
    """
    match = _TASK_RE.match(item)
    if match:
        return match.group(2) in "xX", match.group(1), match.group(3)
    return False, "", item


class TaskCheckbox(Static):
    """Clickable checkbox indicator for a task."""

    class Toggled(Message):
        """Emitted when the checkbox is clicked."""

        @property
        def control(self) -> TaskCheckbox:
            return self._sender

    def __init__(self, checked: bool, **kwargs) -> None:
        super().__init__(ICON_CHECKED if checked else ICON_UNCHECKED, **kwargs)
        self.checked = checked

    def on_click(self, event: Click) -> None:
        event.stop()
        self.checked = not self.checked
        self.update(ICON_CHECKED if self.checked else ICON_UNCHECKED)
        self.post_message(self.Toggled())


class TaskRow(Horizontal):
    """A single task in the task list."""

    def __init__(self, item: str, index: int, parser_factory=None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._item = item
        self._index = index
        self._parser_factory = parser_factory

    def compose(self) -> ComposeResult:
        checked, _, task_text = _parse_task(self._item)
        yield TaskCheckbox(checked, classes="task-checkbox")
        yield EditableText(
            task_text,
            MarkdownViewer(task_text, parser_factory=self._parser_factory),
            TextEditor(),
            classes="task-text",
            clean=False,
        )
        yield ConfirmButton(classes="task-delete")


class TasksEditor(SectionEditor):
    """Editor for task list sections using bullet-list extraction."""

    def __init__(
        self,
        heading: str | None,
        body: str = "",
        parser_factory=None,
        editor_types: list[EditorType] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(heading, body, parser_factory=parser_factory, editor_types=editor_types, **kwargs)
        self._extracted = extract_bullet_list(body)

    def compose(self) -> ComposeResult:
        if self._heading is not None:
            yield from self._compose_heading()

        if self._extracted.before.strip():
            yield MarkdownViewer(self._extracted.before, parser_factory=self._parser_factory, classes="tasks-before")

        with VerticalScroll(classes="tasks-list"):
            for i, item in enumerate(self._extracted.items):
                yield TaskRow(item, i, parser_factory=self._parser_factory, classes="task-row")

        if self._extracted.after.strip():
            yield MarkdownViewer(self._extracted.after, parser_factory=self._parser_factory, classes="tasks-after")

        yield EditableText(
            "",
            Static("+ task"),
            TextEditor(),
            placeholder="+ task",
            classes="add-task",
        )

    def focus_body(self) -> None:
        """Focus the add-task input."""
        self.query_one(".add-task", EditableText).focus()

    def _rebuild_body(self) -> None:
        """Reconstruct body from extracted data and emit BodyChanged."""
        old = self._body
        self._body = reconstruct_body(self._extracted)
        self.post_message(self.BodyChanged(old, self._body))

    def on_editable_text_changed(self, event: EditableText.Changed) -> None:
        event.stop()
        event.prevent_default()
        if "section-heading" in event.control.classes:
            self._heading = event.new_value
            self.post_message(self.HeadingChanged(event.old_value, event.new_value))
            return

        if "add-task" in event.control.classes:
            if event.new_value.strip():
                self._extracted.items.append(f"- [ ] {event.new_value.strip()}")
                self._rebuild_body()
                self.call_after_refresh(self.recompose)
            return

        if "task-text" in event.control.classes:
            row = event.control.parent
            if isinstance(row, TaskRow):
                checked, bullet_prefix, _ = _parse_task(self._extracted.items[row._index])
                checkbox = "[x]" if checked else "[ ]"
                self._extracted.items[row._index] = f"{bullet_prefix}{checkbox} {event.new_value}"
                self._rebuild_body()
                self.call_after_refresh(self.recompose)
            return

    def on_task_checkbox_toggled(self, event: TaskCheckbox.Toggled) -> None:
        event.stop()
        row = event.control.parent
        if isinstance(row, TaskRow):
            _, bullet_prefix, task_text = _parse_task(self._extracted.items[row._index])
            checkbox = "[x]" if event.control.checked else "[ ]"
            self._extracted.items[row._index] = f"{bullet_prefix}{checkbox} {task_text}"
            self._rebuild_body()

    def on_confirm_button_confirmed(self, event: ConfirmButton.Confirmed) -> None:
        event.stop()
        event.prevent_default()
        row = event.control.parent
        if isinstance(row, TaskRow):
            del self._extracted.items[row._index]
            self._rebuild_body()
            self.call_after_refresh(self.recompose)
            return
        # Section delete (inherited behavior)
        self.post_message(self.DeleteRequested())
