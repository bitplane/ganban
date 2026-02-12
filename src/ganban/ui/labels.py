"""Label editor widget for card detail bar."""

from __future__ import annotations

from typing import Any

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.events import DescendantBlur
from textual.widgets import Input, OptionList, Static

from ganban.model.node import Node
from ganban.palette import color_for_label
from ganban.ui.search import SearchInput
from ganban.ui.watcher import NodeWatcherMixin

ICON_LABEL = "\U0001f516"  # 🔖


def _label_color(name: str, board: Node) -> str:
    """Resolve a label's display color from the board index or hash."""
    label_node = getattr(board.labels, name.strip().lower()) if board.labels else None
    if label_node and label_node.color:
        return label_node.color
    return color_for_label(name.strip().lower())


def _label_display(name: str, board: Node) -> Text:
    """Build a colored block + name Text for a label."""
    color = _label_color(name, board)
    result = Text()
    result.append("\u2588\u2588", style=color)
    result.append_text(Text(f" {name}"))
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
    click a tag to replace it. Uses SearchInput for label selection with
    free-text fallback for new labels.
    """

    def __init__(self, meta: Node, board: Node, **kwargs) -> None:
        self._init_watcher()
        super().__init__(**kwargs)
        self.meta = meta
        self.board = board
        self._editing_index: int | None = None  # None = adding, int = replacing

    def compose(self) -> ComposeResult:
        with Horizontal(id="labels-bar"):
            yield Static(ICON_LABEL, id="labels-add")
            yield Horizontal(id="labels-tags")
            yield SearchInput([], placeholder="label", id="labels-search")

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
                tag = Static(classes="label-tag")
                tag._label_name = name
                container.mount(tag)
                tag.update(_label_display(name, self.board))

    def _enter_edit_mode(self, index: int | None = None) -> None:
        """Enter edit mode. index=None means adding, int means replacing."""
        self._editing_index = index
        self.add_class("-editing")
        current_labels = list(self.meta.labels or [])
        if index is not None and index < len(current_labels):
            filter_labels = current_labels[:index] + current_labels[index + 1 :]
        else:
            filter_labels = current_labels
        search = self.query_one("#labels-search", SearchInput)
        search.set_options(build_label_options(self.board, filter_labels))
        inp = search.query_one(Input)
        inp.value = ""
        self._update_indicator("")
        inp.focus()

    def _exit_edit_mode(self) -> None:
        self._editing_index = None
        search = self.query_one("#labels-search", SearchInput)
        search._close_dropdown()
        self.remove_class("-editing")
        self.query_one("#labels-add", Static).update(ICON_LABEL)
        self._rebuild_tags()
        self.screen.focus()

    def _update_indicator(self, text: str) -> None:
        """Update the icon to show the label colour as user types."""
        picker = self.query_one("#labels-add", Static)
        name = text.strip().lower()
        if name:
            color = _label_color(name, self.board)
            indicator = Text()
            indicator.append("\u2588\u2588", style=color)
            picker.update(indicator)
        else:
            picker.update(ICON_LABEL)

    def on_click(self, event) -> None:
        event.stop()
        if self.has_class("-editing"):
            return
        target = event.widget
        if target.id == "labels-add":
            self._enter_edit_mode()
        elif target.has_class("label-tag"):
            container = self.query_one("#labels-tags", Horizontal)
            idx = list(container.children).index(target)
            self._enter_edit_mode(index=idx)

    def on_search_input_submitted(self, event: SearchInput.Submitted) -> None:
        event.stop()
        label_name = event.value or event.text.strip()
        labels = list(self.meta.labels or [])
        if label_name:
            if self._editing_index is not None and self._editing_index < len(labels):
                labels[self._editing_index] = label_name
            else:
                labels.append(label_name)
        elif self._editing_index is not None and self._editing_index < len(labels):
            del labels[self._editing_index]
        else:
            self._exit_edit_mode()
            return
        with self.suppressing():
            self.meta.labels = labels or None
        self._exit_edit_mode()

    def on_search_input_cancelled(self, event: SearchInput.Cancelled) -> None:
        event.stop()
        self._exit_edit_mode()

    def on_descendant_blur(self, event: DescendantBlur) -> None:
        if self.has_class("-editing"):
            self.call_after_refresh(self._maybe_exit_on_blur)

    def _maybe_exit_on_blur(self) -> None:
        focused = self.app.focused
        if focused is None or focused not in self.walk_children():
            self._exit_edit_mode()

    def on_input_changed(self, event: Input.Changed) -> None:
        event.stop()
        if self.has_class("-editing"):
            self._update_indicator(event.value)

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        event.stop()
        if self.has_class("-editing") and event.option and event.option.id:
            self._update_indicator(event.option.id)
