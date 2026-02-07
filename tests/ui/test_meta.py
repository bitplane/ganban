"""Tests for the metadata editor widgets."""

import pytest
from textual.app import App, ComposeResult

from textual.widgets import Button

from ganban.model.node import Node
from ganban.ui.edit.editable import EditableText
from ganban.ui.edit.editors import NumberEditor, TextEditor
from ganban.ui.edit.meta import (
    AddKeyRow,
    AddListItemRow,
    BoolToggle,
    DictEditor,
    KeyValueRow,
    ListEditor,
    ListItemRow,
    MetaEditor,
    _parse_number,
    rename_node_key,
)


class MetaEditorApp(App):
    """Test app wrapping a MetaEditor."""

    def __init__(self, meta: Node):
        super().__init__()
        self.meta = meta

    def compose(self) -> ComposeResult:
        yield Button("focus target", id="focus-target")
        yield MetaEditor(self.meta)


class DictEditorApp(App):
    """Test app wrapping a DictEditor.

    Wraps the node in a parent so that DictEditor's watcher can
    observe external changes via the parent chain.
    """

    def __init__(self, node: Node):
        super().__init__()
        self.root_node = Node(child=node)
        self.node = self.root_node.child

    def compose(self) -> ComposeResult:
        yield Button("focus target", id="focus-target")
        yield DictEditor(self.node)


class ListEditorApp(App):
    """Test app wrapping a ListEditor."""

    def __init__(self, items: list):
        super().__init__()
        self.items = items

    def compose(self) -> ComposeResult:
        yield Button("focus target", id="focus-target")
        yield ListEditor(self.items)


# --- Unit tests for helpers ---


def test_parse_number_int():
    assert _parse_number("42") == 42
    assert isinstance(_parse_number("42"), int)


def test_parse_number_float():
    assert _parse_number("3.14") == 3.14
    assert isinstance(_parse_number("3.14"), float)


def test_rename_node_key():
    node = Node(alpha="a", beta="b", gamma="c")
    rename_node_key(node, "beta", "bravo")
    assert list(node.keys()) == ["alpha", "bravo", "gamma"]
    assert node.bravo == "b"
    assert node.beta is None


# --- DictEditor widget tests ---


@pytest.mark.asyncio
async def test_dict_editor_renders_keys():
    """DictEditor renders a row for each key in the node."""
    node = Node(name="test", count=42, active=True)
    app = DictEditorApp(node)
    async with app.run_test():
        rows = app.query(KeyValueRow)
        assert len(rows) == 3
        keys = {row.key for row in rows}
        assert keys == {"name", "count", "active"}


@pytest.mark.asyncio
async def test_edit_string_value_updates_node():
    """Editing a string value updates the underlying node."""
    node = Node(title="hello")
    app = DictEditorApp(node)
    async with app.run_test() as pilot:
        row = app.query_one(KeyValueRow)
        value_editor = row.query_one(".kv-value", EditableText)
        value_editor.focus()
        await pilot.pause()

        editor = value_editor.query_one("#edit", TextEditor)
        editor.select_all()
        await pilot.press("w", "o", "r", "l", "d")
        await pilot.press("enter")
        await pilot.pause()

        assert node.title == "world"


@pytest.mark.asyncio
async def test_edit_number_value_updates_node():
    """Editing a number value updates the node with the parsed number."""
    node = Node(count=10)
    app = DictEditorApp(node)
    async with app.run_test() as pilot:
        row = app.query_one(KeyValueRow)
        value_editor = row.query_one(".kv-value", EditableText)
        value_editor.focus()
        await pilot.pause()

        editor = value_editor.query_one("#edit", NumberEditor)
        editor.select_all()
        await pilot.press("9", "9")
        await pilot.press("enter")
        await pilot.pause()

        assert node.count == 99
        assert isinstance(node.count, int)


@pytest.mark.asyncio
async def test_bool_toggle_updates_node():
    """Clicking a bool toggle updates the node value."""
    node = Node(active=False)
    app = DictEditorApp(node)
    async with app.run_test() as pilot:
        row = app.query_one(KeyValueRow)
        toggle = row.query_one(BoolToggle)
        assert toggle.value is False

        await pilot.click(toggle)
        await pilot.pause()

        assert node.active is True
        assert toggle.value is True


@pytest.mark.asyncio
async def test_delete_key_removes_from_node():
    """Deleting a key removes it from the node."""
    node = Node(keep="yes", remove="no")
    app = DictEditorApp(node)
    async with app.run_test() as pilot:
        rows = list(app.query(KeyValueRow))
        target = [r for r in rows if r.key == "remove"][0]

        # Simulate the delete confirmation directly
        target.post_message(KeyValueRow.DeleteRequested("remove"))
        await pilot.pause()

        assert node.remove is None
        assert "remove" not in node.keys()


@pytest.mark.asyncio
async def test_nested_dict_renders_dict_editor():
    """A Node with a dict child renders a nested DictEditor."""
    node = Node(info={"color": "red", "size": 5})
    app = DictEditorApp(node)
    async with app.run_test():
        # Should have outer DictEditor + nested DictEditor
        editors = app.query(DictEditor)
        assert len(editors) >= 2

        # Nested editor should have the inner keys
        inner_rows = [r for r in app.query(KeyValueRow) if r.key in ("color", "size")]
        assert len(inner_rows) == 2


@pytest.mark.asyncio
async def test_nested_dict_edit_updates_node():
    """Editing a value in a nested dict updates the node."""
    node = Node(info={"color": "red"})
    app = DictEditorApp(node)
    async with app.run_test() as pilot:
        inner_row = [r for r in app.query(KeyValueRow) if r.key == "color"][0]
        value_editor = inner_row.query_one(".kv-value", EditableText)
        value_editor.focus()
        await pilot.pause()

        editor = value_editor.query_one("#edit", TextEditor)
        editor.select_all()
        await pilot.press("b", "l", "u", "e")
        await pilot.press("enter")
        await pilot.pause()

        assert node.info.color == "blue"


@pytest.mark.asyncio
async def test_list_renders_list_editor():
    """A Node with a list child renders a ListEditor."""
    node = Node(tags=["a", "b", "c"])
    app = DictEditorApp(node)
    async with app.run_test():
        list_editor = app.query_one(ListEditor)
        assert list_editor is not None

        rows = app.query(ListItemRow)
        assert len(rows) == 3


@pytest.mark.asyncio
async def test_add_key_creates_entry():
    """Adding a key via AddKeyRow creates a new entry in the node."""
    node = Node(existing="value")
    app = DictEditorApp(node)
    async with app.run_test() as pilot:
        add_row = app.query_one(AddKeyRow)
        add_row.post_message(AddKeyRow.KeyAdded("new_key", "default"))
        await pilot.pause()

        assert node.new_key == "default"
        rows = app.query(KeyValueRow)
        keys = {row.key for row in rows}
        assert "new_key" in keys


@pytest.mark.asyncio
async def test_meta_editor_wraps_dict_editor():
    """MetaEditor renders a DictEditor for the given node."""
    meta = Node(foo="bar", num=1)
    app = MetaEditorApp(meta)
    async with app.run_test():
        editor = app.query_one(MetaEditor)
        dict_editor = editor.query_one(DictEditor)
        assert dict_editor.node is meta


@pytest.mark.asyncio
async def test_null_value_renders_static():
    """None values render as a Static('null') widget."""
    app = App()
    async with app.run_test():
        row = KeyValueRow("empty", None)
        await app.mount(row)
        statics = row.query(".kv-value")
        assert len(statics) == 1


@pytest.mark.asyncio
async def test_rename_key_updates_node():
    """Renaming a key in KeyValueRow updates the node."""
    node = Node(old_name="value")
    app = DictEditorApp(node)
    async with app.run_test() as pilot:
        row = app.query_one(KeyValueRow)
        key_editor = row.query_one(".kv-key", EditableText)
        key_editor.focus()
        await pilot.pause()

        editor = key_editor.query_one("#edit", TextEditor)
        editor.select_all()
        await pilot.press("n", "e", "w")
        await pilot.press("enter")
        await pilot.pause()

        assert "new" in node.keys()
        assert node.new == "value"


# --- ListEditor widget tests ---


@pytest.mark.asyncio
async def test_list_editor_renders_items():
    """ListEditor renders a row for each item."""
    app = ListEditorApp(["a", "b", "c"])
    async with app.run_test():
        rows = app.query(ListItemRow)
        assert len(rows) == 3


@pytest.mark.asyncio
async def test_list_edit_string_updates():
    """Editing a list item string updates the list."""
    app = ListEditorApp(["hello", "world"])
    async with app.run_test() as pilot:
        rows = list(app.query(ListItemRow))
        value_editor = rows[0].query_one(".li-value", EditableText)
        value_editor.focus()
        await pilot.pause()

        editor = value_editor.query_one("#edit", TextEditor)
        editor.select_all()
        await pilot.press("h", "i")
        await pilot.press("enter")
        await pilot.pause()

        list_editor = app.query_one(ListEditor)
        assert list_editor.items[0] == "hi"
        assert list_editor.items[1] == "world"


@pytest.mark.asyncio
async def test_list_delete_item():
    """Deleting a list item removes it."""
    app = ListEditorApp(["a", "b", "c"])
    async with app.run_test() as pilot:
        rows = list(app.query(ListItemRow))
        rows[1].post_message(ListItemRow.DeleteRequested(1))
        await pilot.pause()

        list_editor = app.query_one(ListEditor)
        assert list_editor.items == ["a", "c"]


@pytest.mark.asyncio
async def test_list_add_item():
    """Adding an item via AddListItemRow appends to the list."""
    app = ListEditorApp(["existing"])
    async with app.run_test() as pilot:
        add_row = app.query_one(AddListItemRow)
        add_row.post_message(AddListItemRow.ItemAdded("new_item"))
        await pilot.pause()

        list_editor = app.query_one(ListEditor)
        assert list_editor.items == ["existing", "new_item"]
        rows = app.query(ListItemRow)
        assert len(rows) == 2


@pytest.mark.asyncio
async def test_list_in_node_updates_on_edit():
    """Editing a list item via the meta editor updates the node."""
    node = Node(tags=["urgent", "bug"])
    app = DictEditorApp(node)
    async with app.run_test() as pilot:
        rows = list(app.query(ListItemRow))
        value_editor = rows[0].query_one(".li-value", EditableText)
        value_editor.focus()
        await pilot.pause()

        editor = value_editor.query_one("#edit", TextEditor)
        editor.select_all()
        await pilot.press("f", "i", "x")
        await pilot.press("enter")
        await pilot.pause()

        assert node.tags[0] == "fix"
        assert node.tags[1] == "bug"


@pytest.mark.asyncio
async def test_list_of_dicts_renders_nested():
    """List items that are dicts render nested DictEditors."""
    app = ListEditorApp([{"name": "alice"}, {"name": "bob"}])
    async with app.run_test():
        item_rows = app.query(ListItemRow)
        assert len(item_rows) == 2

        # Each dict item should have a nested DictEditor
        dict_editors = app.query(DictEditor)
        assert len(dict_editors) == 2

        # Inner rows should have the keys
        kv_rows = app.query(KeyValueRow)
        keys = {row.key for row in kv_rows}
        assert "name" in keys


@pytest.mark.asyncio
async def test_dict_editor_reacts_to_external_change():
    """DictEditor adds a row when an external change adds a key to the node."""
    node = Node(color="red")
    app = DictEditorApp(node)
    async with app.run_test() as pilot:
        rows = app.query(KeyValueRow)
        assert len(rows) == 1

        # External change (simulates due date widget etc.)
        app.node.due = "2026-01-15"
        await pilot.pause()

        rows = app.query(KeyValueRow)
        keys = {row.key for row in rows}
        assert "due" in keys
        assert "color" in keys
