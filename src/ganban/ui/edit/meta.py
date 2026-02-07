"""Tree-shaped metadata editor for Node objects."""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.events import Click
from textual.message import Message
from textual.widgets import Static

from ganban.model.node import Node, _emit
from ganban.model.writer import _meta_to_dict
from ganban.ui.confirm import ConfirmButton
from ganban.ui.edit.editable import EditableText
from ganban.ui.edit.editors import NumberEditor, TextEditor
from ganban.ui.edit.viewers import TextViewer
from ganban.ui.menu import ContextMenu, MenuItem
from ganban.ui.watcher import NodeWatcherMixin


class BoolToggle(Static):
    """A simple true/false toggle that cycles on click."""

    class Changed(Message):
        def __init__(self, value: bool) -> None:
            super().__init__()
            self.value = value

    DEFAULT_CSS = """
    BoolToggle {
        width: auto;
        height: 1;
    }
    BoolToggle:hover {
        text-style: bold;
    }
    """

    def __init__(self, value: bool, **kwargs) -> None:
        super().__init__(str(value).lower(), **kwargs)
        self._value = value

    @property
    def value(self) -> bool:
        return self._value

    def on_click(self, event: Click) -> None:
        event.stop()
        self._value = not self._value
        self.update(str(self._value).lower())
        self.post_message(self.Changed(self._value))


def rename_node_key(node: Node, old_key: str, new_key: str) -> None:
    """Rename a key in a Node's _children, preserving insertion order."""
    value = node._children.get(old_key)
    if value is None:
        return
    items = list(node.items())
    for key, _ in items:
        node._children.pop(key, None)
    for key, val in items:
        k = new_key if key == old_key else key
        node._children[k] = val
    if hasattr(value, "_key"):
        object.__setattr__(value, "_key", new_key)
    node._version += 1
    _emit(node, old_key, value, None)
    _emit(node, new_key, None, value)


def _parse_number(text: str) -> int | float:
    """Parse a numeric string to int or float."""
    if "." in text:
        return float(text)
    return int(text)


def _is_compound(value: Any) -> bool:
    """Check if a value is a compound type (dict/Node/list)."""
    return isinstance(value, (dict, Node, list))


def _compose_scalar(value: Any, css_class: str = "kv-value") -> ComposeResult:
    """Yield the appropriate editor widget for a scalar value."""
    if isinstance(value, bool):
        yield BoolToggle(value, classes=css_class)
    elif isinstance(value, (int, float)):
        yield EditableText(
            str(value),
            TextViewer(str(value)),
            NumberEditor(),
            classes=css_class,
        )
    elif isinstance(value, str):
        yield EditableText(
            value,
            TextViewer(value or '""'),
            TextEditor(),
            classes=css_class,
        )
    else:
        yield Static("null", classes=css_class)


def _compose_compound(value: Any) -> ComposeResult:
    """Yield the appropriate nested editor for a compound value."""
    if isinstance(value, Node):
        yield DictEditor(value)
    elif isinstance(value, dict):
        yield DictEditor(Node(**value))
    elif isinstance(value, list):
        yield ListEditor(value)


# --- List editor ---


class ListItemRow(Vertical):
    """A single item row in a list editor.

    Scalar values render inline. Compound values (dict, list)
    render with a header row and the nested editor below.
    """

    class ValueChanged(Message):
        def __init__(self, index: int, value: Any) -> None:
            super().__init__()
            self.index = index
            self.value = value

    class DeleteRequested(Message):
        def __init__(self, index: int) -> None:
            super().__init__()
            self.index = index

    DEFAULT_CSS = """
    ListItemRow {
        width: 100%;
        height: auto;
    }
    ListItemRow > .li-header {
        width: 100%;
        height: auto;
    }
    ListItemRow .li-bullet {
        width: 2;
        height: 1;
    }
    ListItemRow .li-value, ListItemRow .kv-value {
        width: 1fr;
        height: auto;
    }
    ListItemRow .li-delete {
        width: 2;
        height: 1;
        dock: right;
    }
    """

    def __init__(self, index: int, value: Any, **kwargs) -> None:
        super().__init__(**kwargs)
        self.index = index
        self._value = value
        self._node: Node | None = None

    def compose(self) -> ComposeResult:
        compound = _is_compound(self._value)
        with Horizontal(classes="li-header"):
            yield Static("- ", classes="li-bullet")
            if not compound:
                yield from _compose_scalar(self._value, "li-value")
            yield ConfirmButton(classes="li-delete")
        if compound:
            yield from self._mount_compound()

    def _mount_compound(self) -> ComposeResult:
        v = self._value
        if isinstance(v, dict):
            self._node = Node(**v)
            yield DictEditor(self._node)
        elif isinstance(v, Node):
            self._node = v
            yield DictEditor(self._node)
        elif isinstance(v, list):
            yield ListEditor(v)

    def on_editable_text_changed(self, event: EditableText.Changed) -> None:
        event.stop()
        value: Any = event.new_value
        if isinstance(self._value, (int, float)):
            try:
                value = _parse_number(event.new_value)
            except ValueError:
                return
        self._value = value
        self.post_message(self.ValueChanged(self.index, value))

    def on_bool_toggle_changed(self, event: BoolToggle.Changed) -> None:
        event.stop()
        self._value = event.value
        self.post_message(self.ValueChanged(self.index, event.value))

    def on_key_value_row_value_changed(self, event) -> None:
        """Propagate changes from nested DictEditor."""
        event.stop()
        if self._node is not None:
            self.post_message(self.ValueChanged(self.index, _meta_to_dict(self._node)))

    def on_key_value_row_key_renamed(self, event) -> None:
        event.stop()
        if self._node is not None:
            self.post_message(self.ValueChanged(self.index, _meta_to_dict(self._node)))

    def on_key_value_row_delete_requested(self, event) -> None:
        # Let it bubble to the DictEditor inside us, don't intercept
        pass

    def on_list_editor_changed(self, event) -> None:
        event.stop()
        self._value = event.items
        self.post_message(self.ValueChanged(self.index, event.items))

    def on_confirm_button_confirmed(self, event: ConfirmButton.Confirmed) -> None:
        event.stop()
        self.post_message(self.DeleteRequested(self.index))


class AddListItemRow(Static):
    """Clickable '+' that opens a type picker to add a new list item."""

    class ItemAdded(Message):
        def __init__(self, value: Any) -> None:
            super().__init__()
            self.value = value

    TYPE_DEFAULTS: dict[str, Any] = {
        "text": "",
        "number": 0,
        "bool": False,
        "dict": {},
        "list": [],
    }

    DEFAULT_CSS = """
    AddListItemRow {
        width: 100%;
        height: 1;
        text-align: center;
        color: $text-muted;
        border: dashed $surface-lighten-2;
    }
    AddListItemRow:hover {
        background: $primary-darken-2;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__("+", **kwargs)

    def on_click(self, event: Click) -> None:
        event.stop()
        items = [
            MenuItem("Text", item_id="text"),
            MenuItem("Number", item_id="number"),
            MenuItem("True/False", item_id="bool"),
            MenuItem("Dict", item_id="dict"),
            MenuItem("List", item_id="list"),
        ]
        region = self.region
        menu = ContextMenu(items, region.x, region.y + region.height)
        self.app.push_screen(menu, self._on_type_selected)

    def _on_type_selected(self, item: MenuItem | None) -> None:
        if item:
            default = self.TYPE_DEFAULTS.get(item.item_id, "")
            self.post_message(self.ItemAdded(default))


class ListEditor(Vertical):
    """Renders a list's items as editable rows."""

    class Changed(Message):
        """Emitted when the list contents change."""

        def __init__(self, items: list) -> None:
            super().__init__()
            self.items = items

    DEFAULT_CSS = """
    ListEditor {
        width: 100%;
        height: auto;
        padding: 0 0 0 2;
    }
    """

    def __init__(self, items: list, **kwargs) -> None:
        super().__init__(**kwargs)
        self.items = list(items)

    def compose(self) -> ComposeResult:
        for i, value in enumerate(self.items):
            yield ListItemRow(i, value)
        yield AddListItemRow()

    def _reindex(self) -> None:
        """Update indices on all item rows after a change."""
        for i, row in enumerate(self.query(ListItemRow)):
            row.index = i

    def _emit_changed(self) -> None:
        """Post a Changed message with a snapshot of the current items."""
        self.post_message(self.Changed(list(self.items)))

    def on_list_item_row_value_changed(self, event: ListItemRow.ValueChanged) -> None:
        event.stop()
        self.items[event.index] = event.value
        self._emit_changed()

    def on_list_item_row_delete_requested(self, event: ListItemRow.DeleteRequested) -> None:
        event.stop()
        del self.items[event.index]
        rows = list(self.query(ListItemRow))
        rows[event.index].remove()
        self._reindex()
        self._emit_changed()

    def on_add_list_item_row_item_added(self, event: AddListItemRow.ItemAdded) -> None:
        event.stop()
        self.items.append(event.value)
        row = ListItemRow(len(self.items) - 1, event.value)
        self.mount(row, before=self.query_one(AddListItemRow))
        self._emit_changed()


# --- Key-value row ---


class KeyValueRow(Vertical):
    """A single key:value row in the metadata editor.

    Scalar values render inline as key : value.
    Compound values (dict, list) render with a header row and
    the nested editor indented below.
    """

    class KeyRenamed(Message):
        def __init__(self, old_key: str, new_key: str) -> None:
            super().__init__()
            self.old_key = old_key
            self.new_key = new_key

    class ValueChanged(Message):
        def __init__(self, key: str, value: Any) -> None:
            super().__init__()
            self.key = key
            self.value = value

    class DeleteRequested(Message):
        def __init__(self, key: str) -> None:
            super().__init__()
            self.key = key

    DEFAULT_CSS = """
    KeyValueRow {
        width: 100%;
        height: auto;
        padding: 0;
    }
    KeyValueRow > .kv-header {
        width: 100%;
        height: auto;
    }
    KeyValueRow .kv-key {
        width: 16;
        height: auto;
    }
    KeyValueRow .kv-sep {
        width: 3;
        height: 1;
        content-align: center middle;
    }
    KeyValueRow .kv-value {
        width: 1fr;
        height: auto;
    }
    KeyValueRow .kv-delete {
        width: 2;
        height: 1;
        dock: right;
    }
    """

    def __init__(self, key: str, value: Any, **kwargs) -> None:
        super().__init__(**kwargs)
        self.key = key
        self._value = value

    def compose(self) -> ComposeResult:
        compound = _is_compound(self._value)
        with Horizontal(classes="kv-header"):
            yield EditableText(
                self.key,
                TextViewer(self.key),
                TextEditor(),
                classes="kv-key",
            )
            yield Static(" : ", classes="kv-sep")
            if not compound:
                yield from _compose_scalar(self._value)
            yield ConfirmButton(classes="kv-delete")
        if compound:
            yield from _compose_compound(self._value)

    def on_editable_text_changed(self, event: EditableText.Changed) -> None:
        event.stop()
        sender = event.control
        if "kv-key" in sender.classes:
            self.post_message(self.KeyRenamed(self.key, event.new_value))
            self.key = event.new_value
        elif "kv-value" in sender.classes:
            value: Any = event.new_value
            if isinstance(self._value, (int, float)):
                try:
                    value = _parse_number(event.new_value)
                except ValueError:
                    return
            self._value = value
            self.post_message(self.ValueChanged(self.key, value))

    def on_bool_toggle_changed(self, event: BoolToggle.Changed) -> None:
        event.stop()
        self._value = event.value
        self.post_message(self.ValueChanged(self.key, event.value))

    def on_list_editor_changed(self, event: ListEditor.Changed) -> None:
        event.stop()
        self._value = event.items
        self.post_message(self.ValueChanged(self.key, event.items))

    def on_confirm_button_confirmed(self, event: ConfirmButton.Confirmed) -> None:
        event.stop()
        self.post_message(self.DeleteRequested(self.key))


# --- Add key row ---


class AddKeyRow(Container):
    """Row to add a new key to the metadata."""

    class KeyAdded(Message):
        def __init__(self, key: str, value: Any) -> None:
            super().__init__()
            self.key = key
            self.value = value

    DEFAULT_CSS = """
    AddKeyRow {
        width: 100%;
        height: auto;
        border: dashed $surface-lighten-2;
    }
    AddKeyRow > EditableText > ContentSwitcher > Static {
        text-align: center;
        color: $text-muted;
    }
    """

    TYPE_DEFAULTS: dict[str, Any] = {
        "text": "",
        "number": 0,
        "bool": False,
        "dict": {},
        "list": [],
    }

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._pending_key: str = ""

    def compose(self) -> ComposeResult:
        yield EditableText("", Static("+"), TextEditor(), placeholder="+")

    def on_editable_text_changed(self, event: EditableText.Changed) -> None:
        event.stop()
        if event.new_value:
            self._pending_key = event.new_value
            self.query_one(EditableText).value = ""
            self._show_type_picker()

    def _show_type_picker(self) -> None:
        items = [
            MenuItem("Text", item_id="text"),
            MenuItem("Number", item_id="number"),
            MenuItem("True/False", item_id="bool"),
            MenuItem("Dict", item_id="dict"),
            MenuItem("List", item_id="list"),
        ]
        region = self.region
        menu = ContextMenu(items, region.x, region.y + region.height)
        self.app.push_screen(menu, self._on_type_selected)

    def _on_type_selected(self, item: MenuItem | None) -> None:
        if item and self._pending_key:
            default = self.TYPE_DEFAULTS.get(item.item_id, "")
            self.post_message(self.KeyAdded(self._pending_key, default))
        self._pending_key = ""


# --- Dict editor ---


class DictEditor(NodeWatcherMixin, Vertical):
    """Renders a Node's children as KeyValueRows + AddKeyRow."""

    DEFAULT_CSS = """
    DictEditor {
        width: 100%;
        height: auto;
        padding: 0 0 0 2;
    }
    """

    def __init__(self, node: Node, **kwargs) -> None:
        self._init_watcher()
        super().__init__(**kwargs)
        self.node = node

    def compose(self) -> ComposeResult:
        for key, value in self.node.items():
            yield KeyValueRow(key, value)
        yield AddKeyRow()

    def on_mount(self) -> None:
        if self.node._parent is not None and self.node._key is not None:
            self.node_watch(self.node._parent, self.node._key, self._on_node_changed)

    def _on_node_changed(self, source_node, key, old, new) -> None:
        """React to model changes that bubbled up through our node."""
        if source_node is not self.node:
            return
        self.call_later(self._sync_row, key, new)

    def _sync_row(self, key: str, new_value: Any) -> None:
        """Add, remove, or replace a single row to match the node."""
        existing = None
        for row in self.query(KeyValueRow):
            if row.key == key:
                existing = row
                break

        if new_value is None:
            if existing:
                existing.remove()
            return

        if existing:
            rows = list(self.query(KeyValueRow))
            idx = rows.index(existing)
            insert_before = rows[idx + 1] if idx + 1 < len(rows) else self.query_one(AddKeyRow)
            existing.remove()
        else:
            insert_before = self.query_one(AddKeyRow)

        self.mount(KeyValueRow(key, new_value), before=insert_before)

    def _set_node(self, key: str, value: Any) -> None:
        """Set a value on the node with change suppression."""
        with self.suppressing():
            setattr(self.node, key, value)

    def on_key_value_row_value_changed(self, event: KeyValueRow.ValueChanged) -> None:
        event.stop()
        self._set_node(event.key, event.value)

    def on_key_value_row_key_renamed(self, event: KeyValueRow.KeyRenamed) -> None:
        event.stop()
        with self.suppressing():
            rename_node_key(self.node, event.old_key, event.new_key)

    def on_key_value_row_delete_requested(self, event: KeyValueRow.DeleteRequested) -> None:
        event.stop()
        self._set_node(event.key, None)
        for row in self.query(KeyValueRow):
            if row.key == event.key:
                row.remove()
                break

    def on_add_key_row_key_added(self, event: AddKeyRow.KeyAdded) -> None:
        event.stop()
        self._set_node(event.key, event.value)
        row = KeyValueRow(event.key, event.value)
        self.mount(row, before=self.query_one(AddKeyRow))


# --- Top-level wrapper ---


class MetaEditor(Container):
    """Thin wrapper for the tree metadata editor with scroll support."""

    DEFAULT_CSS = """
    MetaEditor {
        width: 100%;
        height: 1fr;
        overflow-y: auto;
    }
    """

    def __init__(self, meta: Node, **kwargs) -> None:
        super().__init__(**kwargs)
        self.meta = meta

    def compose(self) -> ComposeResult:
        yield DictEditor(self.meta)
