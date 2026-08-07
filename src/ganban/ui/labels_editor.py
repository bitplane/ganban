"""Board-level labels editor for the board detail modal."""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.message import Message
from textual.widgets import Static

from ganban.model.card import delete_label, rename_label
from ganban.model.loader import normalise_label
from ganban.model.node import Node
from ganban.ui.palette import color_for_label, get_label_color
from ganban.ui.color import ColorButton
from ganban.ui.edit.add import AddValueMixin
from ganban.ui.tag import Tag
from ganban.ui.labels import _label_display
from ganban.ui.watcher import NodeWatcherMixin


class _LabelRow(Horizontal):
    """Shared skeleton for label rows: a renamable tag with a card count.

    Subclasses declare their own NameRenamed/DeleteRequested message
    classes (handler names derive from the concrete class) and add their
    extra controls around the shared tag + count.
    """

    def __init__(self, name: str, board: Node, **kwargs) -> None:
        super().__init__(**kwargs)
        self.label_name = name
        self.board = board

    def _label_count(self) -> int:
        label_node = getattr(self.board.labels, self.label_name) if self.board.labels else None
        cards = label_node.cards if label_node else []
        return len(cards) if isinstance(cards, list) else 0

    def _compose_tag_and_count(self) -> ComposeResult:
        yield Tag(value=self.label_name, display=_label_display(self.label_name, self.board))
        yield Static(f"({self._label_count()})", classes="label-count")

    def on_click(self, event) -> None:
        if event.widget.has_class("tag-label"):
            tag = self.query_one(Tag)
            if not tag.has_class("-editing"):
                tag.start_editing([])

    def on_tag_changed(self, event: Tag.Changed) -> None:
        event.stop()
        old = event.old_value
        self.label_name = event.new_value
        event.tag.update_display(_label_display(event.new_value, self.board))
        self.post_message(self.NameRenamed(old, event.new_value))

    def on_tag_deleted(self, event: Tag.Deleted) -> None:
        event.stop()
        self.post_message(self.DeleteRequested(self.label_name))


class SavedLabelRow(_LabelRow):
    """A saved label (from board.meta.labels) shown as a tag with count.

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

    def compose(self) -> ComposeResult:
        yield ColorButton(color=get_label_color(self.label_name, self.board), classes="label-color")
        yield from self._compose_tag_and_count()

    def on_color_button_color_selected(self, event: ColorButton.ColorSelected) -> None:
        event.stop()
        self.post_message(self.ColorChanged(self.label_name, event.color))


class UsedLabelRow(_LabelRow):
    """A used label (on cards, no override) shown as a tag with count and save.

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

    def compose(self) -> ComposeResult:
        yield from self._compose_tag_and_count()
        yield Static("💾", classes="label-save")

    def on_click(self, event) -> None:
        if event.widget.has_class("label-save"):
            event.stop()
            self.post_message(self.SaveRequested(self.label_name))
        else:
            super().on_click(event)


class AddLabelRow(AddValueMixin, Static, can_focus=True):
    """EditableText with '+' to add a new label."""

    class LabelCreated(Message):
        def __init__(self, name: str) -> None:
            super().__init__()
            self.name = name

    def value_entered(self, value: str) -> None:
        self.post_message(self.LabelCreated(value))
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

        yield AddLabelRow()

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
        # Update tag display with new color
        for row in self.query(SavedLabelRow):
            if row.label_name == event.name:
                row.query_one(Tag).update_display(_label_display(event.name, self.board))
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
        name = normalise_label(event.name)
        if not name:
            return
        meta_labels = self._ensure_labels()
        with self.suppressing():
            color = color_for_label(name)
            setattr(meta_labels, name, {"color": color})
        self.call_later(self.recompose)
