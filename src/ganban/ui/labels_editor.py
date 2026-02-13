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
from ganban.ui.constants import ICON_COLOR_SWATCH
from ganban.ui.palette import color_for_label, get_label_color
from ganban.ui.color import ColorButton
from ganban.ui.confirm import ConfirmButton
from ganban.ui.edit.editable import EditableText
from ganban.ui.edit.editors import TextEditor
from ganban.ui.edit.viewers import TextViewer
from ganban.ui.watcher import NodeWatcherMixin


def _swatch_text(color: str) -> Text:
    """Build a colored block swatch."""
    result = Text()
    result.append(ICON_COLOR_SWATCH, style=color)
    return result


class SavedLabelRow(Vertical):
    """A saved label row (from board.meta.labels) with colour picker.

    Delete removes the override only - label stays on cards with computed color.
    """

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
        """Delete override only - label stays on cards."""

        def __init__(self, name: str) -> None:
            super().__init__()
            self.name = name

    def __init__(self, name: str, board: Node, **kwargs) -> None:
        super().__init__(**kwargs)
        self.label_name = name
        self.board = board

    def compose(self) -> ComposeResult:
        color = get_label_color(self.label_name, self.board)
        # Count cards with this label
        label_node = getattr(self.board.labels, self.label_name) if self.board.labels else None
        cards = label_node.cards if label_node else []
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
        color = get_label_color(self.label_name, self.board)
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


class UsedLabelRow(Vertical):
    """A used label row (on cards, no override) with read-only color swatch.

    Delete removes from all cards. Save creates an override.
    """

    class NameRenamed(Message):
        def __init__(self, old: str, new: str) -> None:
            super().__init__()
            self.old = old
            self.new = new

    class DeleteRequested(Message):
        """Delete from all cards."""

        def __init__(self, name: str) -> None:
            super().__init__()
            self.name = name

    class SaveRequested(Message):
        """Create override from computed color."""

        def __init__(self, name: str) -> None:
            super().__init__()
            self.name = name

    def __init__(self, name: str, board: Node, **kwargs) -> None:
        super().__init__(**kwargs)
        self.label_name = name
        self.board = board

    def compose(self) -> ComposeResult:
        color = get_label_color(self.label_name, self.board)
        label_node = getattr(self.board.labels, self.label_name) if self.board.labels else None
        cards = label_node.cards if label_node else []
        count = len(cards) if isinstance(cards, list) else 0
        with Horizontal(classes="label-title-bar"):
            yield Static(_swatch_text(color), classes="label-swatch-static")
            yield EditableText(
                self.label_name,
                TextViewer(self.label_name),
                TextEditor(),
                classes="label-name",
            )
            yield Static(f"({count})", classes="label-count")
            yield Static("💾", classes="label-save")
            yield ConfirmButton(classes="label-delete")

    def on_click(self, event) -> None:
        target = event.widget
        if target.has_class("label-save"):
            event.stop()
            self.post_message(self.SaveRequested(self.label_name))

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
    """Editor for board-level labels — shown as a tab in BoardDetailModal.

    Two sections:
    - Saved Labels: from board.meta.labels (color overrides)
    - Used Labels: on cards but no override (computed colors)
    """

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
        # Saved labels (from board.meta.labels)
        saved_names = set()
        meta_labels = self.meta.labels if self.meta else None
        if meta_labels and isinstance(meta_labels, Node):
            saved_names = set(meta_labels.keys())
            if saved_names:
                yield Static("Saved Labels", classes="section-header")
                for name in meta_labels.keys():
                    yield SavedLabelRow(name, self.board)

        # Used labels (on cards but not in meta)
        used_names = []
        if self.board.labels:
            for name in self.board.labels.keys():
                if name not in saved_names:
                    used_names.append(name)
        if used_names:
            yield Static("Used Labels", classes="section-header")
            for name in used_names:
                yield UsedLabelRow(name, self.board)

        yield AddLabelRow()

    def on_mount(self) -> None:
        if self.meta:
            self.node_watch(self.meta, "labels", self._on_labels_changed)
        if self.board.labels:
            self.node_watch(self.board, "labels", self._on_labels_changed)

    def _on_labels_changed(self, source_node: Any, key: str, old: Any, new: Any) -> None:
        self.call_later(self.recompose)

    # --- Saved label handlers ---

    def on_saved_label_row_color_changed(self, event: SavedLabelRow.ColorChanged) -> None:
        event.stop()
        meta_labels = self._ensure_labels()
        with self.suppressing():
            entry = getattr(meta_labels, event.name)
            if entry is None:
                setattr(meta_labels, event.name, {"color": event.color})
            else:
                entry.color = event.color
        # Update swatch immediately
        for row in self.query(SavedLabelRow):
            if row.label_name == event.name:
                row.query_one(".label-swatch", Static).update(_swatch_text(event.color))
                break

    def on_saved_label_row_name_renamed(self, event: SavedLabelRow.NameRenamed) -> None:
        event.stop()
        with self.suppressing():
            rename_label(self.board, event.old, event.new)

    def on_saved_label_row_delete_requested(self, event: SavedLabelRow.DeleteRequested) -> None:
        """Delete override only - label stays on cards."""
        event.stop()
        meta_labels = self.meta.labels
        if meta_labels:
            with self.suppressing():
                setattr(meta_labels, event.name, None)
        for row in self.query(SavedLabelRow):
            if row.label_name == event.name:
                row.remove()
                break
        # Recompose to potentially show as used label
        self.call_later(self.recompose)

    # --- Used label handlers ---

    def on_used_label_row_name_renamed(self, event: UsedLabelRow.NameRenamed) -> None:
        event.stop()
        with self.suppressing():
            rename_label(self.board, event.old, event.new)

    def on_used_label_row_delete_requested(self, event: UsedLabelRow.DeleteRequested) -> None:
        """Delete from all cards."""
        event.stop()
        with self.suppressing():
            delete_label(self.board, event.name)
        for row in self.query(UsedLabelRow):
            if row.label_name == event.name:
                row.remove()
                break

    def on_used_label_row_save_requested(self, event: UsedLabelRow.SaveRequested) -> None:
        """Promote used label to saved with current computed color."""
        event.stop()
        name = event.name
        color = color_for_label(name)
        meta_labels = self._ensure_labels()
        with self.suppressing():
            setattr(meta_labels, name, {"color": color})
        self.call_later(self.recompose)

    # --- Add label handler ---

    def on_add_label_row_label_created(self, event: AddLabelRow.LabelCreated) -> None:
        event.stop()
        name = event.name.strip().lower()
        if not name:
            return
        meta_labels = self._ensure_labels()
        with self.suppressing():
            color = color_for_label(name)
            setattr(meta_labels, name, {"color": color})
        self.call_later(self.recompose)
