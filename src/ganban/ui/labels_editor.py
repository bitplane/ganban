"""Board-level labels editor for the board detail modal."""

from __future__ import annotations

from typing import Any

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.message import Message
from textual.widgets import Static

from ganban.model.card import delete_label, rename_label
from ganban.model.node import Node
from ganban.palette import color_for_label
from ganban.ui.color import ColorButton
from ganban.ui.confirm import ConfirmButton
from ganban.ui.edit.editable import EditableText
from ganban.ui.edit.editors import TextEditor
from ganban.ui.edit.viewers import TextViewer
from ganban.ui.watcher import NodeWatcherMixin


def _swatch_text(color: str) -> Text:
    """Build a colored block swatch."""
    result = Text()
    result.append("\u2588\u2588", style=color)
    return result


class LabelRow(Vertical):
    """A single label row with colour swatch, editable name, card count, and delete."""

    class ColorChanged(Message):
        def __init__(self, name: str, color: str | None) -> None:
            super().__init__()
            self.name = name
            self.color = color

    class NameRenamed(Message):
        def __init__(self, old: str, new: str) -> None:
            super().__init__()
            self.old = old
            self.new = new

    class DeleteRequested(Message):
        def __init__(self, name: str) -> None:
            super().__init__()
            self.name = name

    def __init__(self, name: str, label_node: Node, **kwargs) -> None:
        super().__init__(**kwargs)
        self.label_name = name
        self.label_node = label_node

    def compose(self) -> ComposeResult:
        color = self.label_node.color or color_for_label(self.label_name)
        cards = self.label_node.cards
        count = len(cards) if isinstance(cards, list) else 0
        with Horizontal(classes="label-title-bar"):
            yield ColorButton(color=color, classes="label-color")
            yield Static(classes="label-swatch")
            yield EditableText(
                self.label_name,
                TextViewer(self.label_name),
                TextEditor(),
                classes="label-name",
            )
            yield Static(f"({count})", classes="label-count")
            yield ConfirmButton(classes="label-delete")

    def on_mount(self) -> None:
        color = self.label_node.color or color_for_label(self.label_name)
        self.query_one(".label-swatch", Static).update(_swatch_text(color))

    def on_color_button_color_selected(self, event: ColorButton.ColorSelected) -> None:
        event.stop()
        self.post_message(self.ColorChanged(self.label_name, event.color))

    def on_editable_text_changed(self, event: EditableText.Changed) -> None:
        event.stop()
        sender = event.control
        if "label-name" in sender.classes:
            old = self.label_name
            self.label_name = event.new_value
            self.post_message(self.NameRenamed(old, event.new_value))

    def on_confirm_button_confirmed(self, event: ConfirmButton.Confirmed) -> None:
        event.stop()
        self.post_message(self.DeleteRequested(self.label_name))


class AddLabelRow(Static, can_focus=True):
    """EditableText with '+' to add a new label."""

    BINDINGS = [
        ("space", "start_editing"),
        ("enter", "start_editing"),
    ]

    class LabelCreated(Message):
        def __init__(self, name: str) -> None:
            super().__init__()
            self.name = name

    def action_start_editing(self) -> None:
        self.query_one(EditableText)._start_edit()

    def compose(self) -> ComposeResult:
        yield EditableText("", Static("+"), TextEditor(), placeholder="+")

    def on_editable_text_changed(self, event: EditableText.Changed) -> None:
        event.stop()
        if event.new_value:
            self.post_message(self.LabelCreated(event.new_value))
        self.query_one(EditableText).value = ""
        self.focus()


class LabelsEditor(NodeWatcherMixin, Container):
    """Editor for board-level labels — shown as a tab in BoardDetailModal."""

    def __init__(self, board: Node, **kwargs) -> None:
        self._init_watcher()
        super().__init__(**kwargs)
        self.board = board
        self.meta = board.meta

    def _ensure_labels(self) -> Node:
        """Create meta.labels = {} if missing, return the labels node."""
        if self.meta.labels is None:
            self.meta.labels = {}
        return self.meta.labels

    def compose(self) -> ComposeResult:
        labels = self.board.labels
        if labels is not None:
            for name in labels.keys():
                label_node = getattr(labels, name)
                if label_node is not None:
                    yield LabelRow(name, label_node)
        yield AddLabelRow()

    def on_mount(self) -> None:
        if self.meta:
            self.node_watch(self.meta, "labels", self._on_labels_changed)

    def _on_labels_changed(self, source_node: Any, key: str, old: Any, new: Any) -> None:
        self.call_later(self.recompose)

    def on_label_row_color_changed(self, event: LabelRow.ColorChanged) -> None:
        event.stop()
        meta_labels = self._ensure_labels()
        with self.suppressing():
            entry = getattr(meta_labels, event.name)
            if entry is None:
                setattr(meta_labels, event.name, {"color": event.color})
            else:
                entry.color = event.color

    def on_label_row_name_renamed(self, event: LabelRow.NameRenamed) -> None:
        event.stop()
        with self.suppressing():
            rename_label(self.board, event.old, event.new)

    def on_label_row_delete_requested(self, event: LabelRow.DeleteRequested) -> None:
        event.stop()
        with self.suppressing():
            delete_label(self.board, event.name)
        for row in self.query(LabelRow):
            if row.label_name == event.name:
                row.remove()
                break

    def on_add_label_row_label_created(self, event: AddLabelRow.LabelCreated) -> None:
        event.stop()
        name = event.name.strip().lower()
        if not name:
            return
        meta_labels = self._ensure_labels()
        with self.suppressing():
            color = color_for_label(name)
            setattr(meta_labels, name, {"color": color})
        label_node = getattr(self.board.labels, name)
        if label_node is None:
            label_node = Node(color=color_for_label(name), cards=[])
        row = LabelRow(name, label_node)
        self.mount(row, before=self.query_one(AddLabelRow))
