"""Label editor widget for card detail bar."""

from __future__ import annotations

from typing import Any

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Input, OptionList, Static

from ganban.model.node import Node
from ganban.ui.constants import ICON_COLOR_SWATCH
from ganban.ui.palette import get_label_color
from ganban.ui.tag import Tag
from ganban.ui.watcher import NodeWatcherMixin

ICON_LABEL = "\U0001f516"  # 🔖


def _label_display(name: str, board: Node) -> Text:
    """Build a colored block + name Text for a label."""
    color = get_label_color(name, board)
    result = Text()
    result.append(ICON_COLOR_SWATCH, style=color)
    result.append_text(Text(name))
    return result


def build_label_options(board: Node, current_labels: list[str]) -> list[tuple[str, str]]:
    """Build (label, value) options for the label search dropdown.

    Shows all known labels from board.labels, excluding those already on the card.
    """
    exclude = {raw.strip().lower() for raw in current_labels}
    options: list[tuple[str, str]] = []
    if board.labels:
        for name in board.labels.keys():
            if name not in exclude:
                options.append((name, name))
    return options


class LabelsWidget(NodeWatcherMixin, Container):
    """Inline label editor for card detail bar.

    Displays label tags next to a bookmark icon. Click the icon to add a label,
    click a tag to edit it, click × to delete. Uses Tag widgets with SearchInput
    for label selection with free-text fallback for new labels.
    """

    def __init__(self, meta: Node, board: Node, **kwargs) -> None:
        self._init_watcher()
        super().__init__(**kwargs)
        self.meta = meta
        self.board = board

    def compose(self) -> ComposeResult:
        with Horizontal(id="labels-bar"):
            yield Static(ICON_LABEL, id="labels-add")
            yield Horizontal(id="labels-tags")

    def on_mount(self) -> None:
        self.node_watch(self.meta, "labels", self._on_labels_changed)
        self._rebuild_tags()

    def _on_labels_changed(self, source_node: Any, key: str, old: Any, new: Any) -> None:
        self.call_later(self._rebuild_tags)

    def _rebuild_tags(self) -> None:
        """Clear and rebuild the label tag widgets."""
        container = self.query_one("#labels-tags", Horizontal)
        for child in list(container.children):
            child.remove()
        labels = self.meta.labels
        if labels and isinstance(labels, list):
            for name in labels:
                tag = Tag(value=name, display=_label_display(name, self.board))
                container.mount(tag)

    def _current_labels_except(self, exclude_tag: Tag | None = None) -> list[str]:
        """Get current labels, optionally excluding one tag's value."""
        labels = list(self.meta.labels or [])
        if exclude_tag is not None:
            tags = list(self.query_one("#labels-tags", Horizontal).query(Tag))
            idx = tags.index(exclude_tag) if exclude_tag in tags else None
            if idx is not None and idx < len(labels):
                return labels[:idx] + labels[idx + 1 :]
        return labels

    def on_click(self, event) -> None:
        event.stop()
        target = event.widget
        if target.id == "labels-add":
            self._add_new_tag()
        elif target.has_class("tag-label"):
            tag = target.parent.parent  # tag-label → tag-row → Tag
            if isinstance(tag, Tag) and not tag.has_class("-editing"):
                options = build_label_options(self.board, self._current_labels_except(tag))
                tag.start_editing(options)

    def _add_new_tag(self) -> None:
        """Mount a temporary blank tag for adding a new label."""
        container = self.query_one("#labels-tags", Horizontal)
        tag = Tag(value="", classes="-new")
        container.mount(tag)
        options = build_label_options(self.board, self._current_labels_except())
        tag.start_editing(options)

    def on_tag_changed(self, event: Tag.Changed) -> None:
        event.stop()
        tag = event.tag
        labels = list(self.meta.labels or [])
        tags = list(self.query_one("#labels-tags", Horizontal).query(Tag))
        idx = tags.index(tag) if tag in tags else None

        if tag.has_class("-new"):
            tag.remove_class("-new")
            labels.append(event.new_value)
        elif idx is not None and idx < len(labels):
            labels[idx] = event.new_value

        tag.update_display(_label_display(event.new_value, self.board))
        with self.suppressing():
            self.meta.labels = labels or None

    def on_tag_deleted(self, event: Tag.Deleted) -> None:
        event.stop()
        tag = event.tag
        labels = list(self.meta.labels or [])
        tags = list(self.query_one("#labels-tags", Horizontal).query(Tag))
        idx = tags.index(tag) if tag in tags else None

        if tag.has_class("-new"):
            tag.remove()
            return

        if idx is not None and idx < len(labels):
            del labels[idx]
        tag.remove()
        with self.suppressing():
            self.meta.labels = labels or None

    def _swatch_for(self, text: str) -> Text:
        """Build a swatch-only Text for the given label name."""
        name = text.strip().lower()
        if name:
            color = get_label_color(name, self.board)
            result = Text()
            result.append(ICON_COLOR_SWATCH, style=color)
            return result
        return Text()

    def _update_editing_swatch(self, text: str) -> None:
        """Update the tag-label on whichever tag is currently editing."""
        for tag in self.query_one("#labels-tags", Horizontal).query(Tag):
            if tag.has_class("-editing"):
                tag.query_one(".tag-label", Static).update(self._swatch_for(text))
                return

    def on_input_changed(self, event: Input.Changed) -> None:
        event.stop()
        self._update_editing_swatch(event.value)

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        event.stop()
        if event.option and event.option.id:
            self._update_editing_swatch(event.option.id)
