"""Tests for the reactive Node and ListNode tree."""

from ganban.model.node import ListNode, Node


# --- Node basics ---


def test_node_set_and_get():
    node = Node()
    node.name = "Backlog"
    assert node.name == "Backlog"


def test_node_get_missing_returns_none():
    node = Node()
    assert node.nonexistent is None


def test_node_set_none_deletes():
    node = Node(color="#800000")
    node.color = None
    assert node.color is None
    assert "color" not in node


def test_node_delete_missing_is_noop():
    node = Node()
    node.color = None  # should not raise
    assert "color" not in node


def test_node_init_kwargs():
    node = Node(name="Backlog", order="1")
    assert node.name == "Backlog"
    assert node.order == "1"


def test_node_auto_wrap_dict():
    node = Node()
    node.meta = {"color": "#800000"}
    assert isinstance(node.meta, Node)
    assert node.meta.color == "#800000"


def test_node_auto_wrap_sets_parent():
    node = Node()
    node.meta = {"color": "#800000"}
    assert node.meta._parent is node
    assert node.meta._key == "meta"


def test_node_version_increments():
    node = Node()
    assert node._version == 0
    node.name = "Backlog"
    assert node._version == 1
    node.name = "Done"
    assert node._version == 2


def test_node_version_no_change():
    node = Node()
    node.name = "Backlog"
    v = node._version
    node.name = "Backlog"  # equal value, different object
    assert node._version == v


def test_node_keys():
    node = Node(a="1", b="2")
    assert set(node.keys()) == {"a", "b"}


def test_node_no_event_on_equal_list():
    """Setting a list property to an equal list should not emit."""
    events = []
    node = Node()
    node.links = ["a", "b", "c"]
    node.watch("links", lambda n, k, old, new: events.append(1))
    node.links = ["a", "b", "c"]
    assert len(events) == 0


def test_node_contains():
    node = Node(color="#800000")
    assert "color" in node
    assert "name" not in node


def test_node_path_root():
    node = Node()
    assert node.path == ""


def test_node_path_nested():
    root = Node()
    root.meta = {"color": "#800000"}
    assert root.meta.path == "meta"
    assert root.meta.color is not None  # it's a scalar, no path


# --- Watchers ---


def test_watch_fires_on_change():
    events = []
    node = Node(color="#800000")
    node.watch("color", lambda n, k, old, new: events.append((n, k, old, new)))
    node.color = "#ff0000"
    assert len(events) == 1
    assert events[0] == (node, "color", "#800000", "#ff0000")


def test_watch_fires_on_delete():
    events = []
    node = Node(color="#800000")
    node.watch("color", lambda n, k, old, new: events.append((old, new)))
    node.color = None
    assert len(events) == 1
    assert events[0] == ("#800000", None)


def test_watch_fires_on_add():
    events = []
    node = Node()
    node.watch("color", lambda n, k, old, new: events.append((old, new)))
    node.color = "#800000"
    assert len(events) == 1
    assert events[0] == (None, "#800000")


def test_unwatch():
    events = []
    node = Node()
    unwatch = node.watch("color", lambda n, k, old, new: events.append(1))
    node.color = "#800000"
    assert len(events) == 1
    unwatch()
    node.color = "#ff0000"
    assert len(events) == 1  # no new event


def test_multiple_watchers():
    a_events = []
    b_events = []
    node = Node()
    node.watch("color", lambda n, k, old, new: a_events.append(1))
    node.watch("color", lambda n, k, old, new: b_events.append(1))
    node.color = "#800000"
    assert len(a_events) == 1
    assert len(b_events) == 1


def test_watcher_not_called_on_no_change():
    events = []
    node = Node()
    node.name = "Backlog"
    node.watch("name", lambda n, k, old, new: events.append(1))
    node.name = "Backlog"  # equal value, different object
    assert len(events) == 0


# --- Bubbling ---


def test_bubble_to_parent():
    events = []
    root = Node()
    root.meta = {"color": "#800000"}
    root.watch("meta", lambda n, k, old, new: events.append((k, old, new)))
    root.meta.color = "#ff0000"
    assert len(events) == 1
    assert events[0] == ("color", "#800000", "#ff0000")


def test_bubble_node_arg_is_source():
    received_nodes = []
    root = Node()
    root.meta = {"color": "#800000"}
    root.watch("meta", lambda n, k, old, new: received_nodes.append(n))
    root.meta.color = "#ff0000"
    assert received_nodes[0] is root.meta


def test_bubble_through_list_node():
    events = []
    root = Node()
    root.columns = ListNode()
    root.columns["1"] = {"name": "Backlog", "color": "#800000"}
    root.watch("columns", lambda n, k, old, new: events.append((k, old, new)))
    root.columns["1"].color = "#ff0000"
    assert len(events) == 1
    assert events[0] == ("color", "#800000", "#ff0000")


def test_deep_bubble():
    events = []
    root = Node()
    root.columns = ListNode()
    root.columns["1"] = {"meta": {"color": "#800000"}}
    root.watch("columns", lambda n, k, old, new: events.append((k, new)))
    root.columns["1"].meta.color = "#ff0000"
    assert len(events) == 1
    assert events[0] == ("color", "#ff0000")


# --- ListNode basics ---


def test_list_node_set_and_get():
    lst = ListNode()
    lst["1"] = {"name": "Backlog"}
    assert isinstance(lst["1"], Node)
    assert lst["1"].name == "Backlog"


def test_list_node_delete():
    lst = ListNode()
    lst["1"] = {"name": "Backlog"}
    lst["1"] = None
    assert lst["1"] is None
    assert "1" not in lst


def test_list_node_iter_order():
    lst = ListNode()
    lst["1"] = {"name": "Backlog"}
    lst["2"] = {"name": "Doing"}
    lst["3"] = {"name": "Done"}
    names = [item.name for item in lst]
    assert names == ["Backlog", "Doing", "Done"]


def test_list_node_len():
    lst = ListNode()
    assert len(lst) == 0
    lst["1"] = {"name": "Backlog"}
    assert len(lst) == 1
    lst["2"] = {"name": "Done"}
    assert len(lst) == 2


def test_list_node_contains():
    lst = ListNode()
    lst["1"] = {"name": "Backlog"}
    assert "1" in lst
    assert "2" not in lst


def test_list_node_replace_keeps_position():
    lst = ListNode()
    lst["1"] = {"name": "Backlog"}
    lst["2"] = {"name": "Doing"}
    lst["3"] = {"name": "Done"}
    lst["2"] = {"name": "In Progress"}
    names = [item.name for item in lst]
    assert names == ["Backlog", "In Progress", "Done"]


def test_list_node_delete_with_duplicate_values():
    """Deleting a key works correctly when multiple keys have the same value."""
    lst = ListNode()
    lst["a"] = "same"
    lst["b"] = "same"
    lst["c"] = "different"
    lst["a"] = None
    assert lst.keys() == ["b", "c"]
    assert list(lst) == ["same", "different"]


def test_list_node_replace_with_duplicate_values():
    """Replacing a key works correctly when multiple keys have the same value."""
    lst = ListNode()
    lst["a"] = "same"
    lst["b"] = "same"
    lst["c"] = "other"
    lst["b"] = "updated"
    assert lst.keys() == ["a", "b", "c"]
    assert list(lst) == ["same", "updated", "other"]


def test_list_node_no_event_on_equal_value():
    """Setting a key to an equal value should not emit."""
    events = []
    lst = ListNode()
    lst["a"] = "hello"
    lst.watch("a", lambda n, k, old, new: events.append(1))
    lst["a"] = "hello"
    assert len(events) == 0


def test_list_node_no_version_bump_on_equal_value():
    lst = ListNode()
    lst["a"] = "hello"
    v = lst._version
    lst["a"] = "hello"
    assert lst._version == v


def test_list_node_auto_wrap():
    lst = ListNode()
    lst["1"] = {"name": "Backlog"}
    assert isinstance(lst["1"], Node)


def test_list_node_child_parent():
    lst = ListNode()
    lst["1"] = {"name": "Backlog"}
    assert lst["1"]._parent is lst
    assert lst["1"]._key == "1"


def test_list_node_watch():
    events = []
    lst = ListNode()
    lst.watch("1", lambda n, k, old, new: events.append(("watch", old, new)))
    lst["1"] = {"name": "Backlog"}
    assert len(events) == 1
    assert events[0][0] == "watch"
    assert events[0][1] is None  # old
    assert events[0][2].name == "Backlog"  # new


def test_list_node_watch_delete():
    events = []
    lst = ListNode()
    lst["1"] = {"name": "Backlog"}
    lst.watch("1", lambda n, k, old, new: events.append((old, new)))
    lst["1"] = None
    assert len(events) == 1
    assert events[0][0].name == "Backlog"  # old node
    assert events[0][1] is None  # new


def test_list_node_version():
    lst = ListNode()
    assert lst._version == 0
    lst["1"] = {"name": "Backlog"}
    assert lst._version == 1
    lst["1"] = None
    assert lst._version == 2


def test_list_node_path():
    root = Node()
    root.columns = ListNode()
    root.columns["1"] = {"name": "Backlog"}
    assert root.columns.path == "columns"
    assert root.columns["1"].path == "columns.1"


def test_list_node_keys():
    lst = ListNode()
    lst["a"] = "first"
    lst["b"] = "second"
    lst["c"] = "third"
    assert lst.keys() == ["a", "b", "c"]


def test_list_node_keys_empty():
    lst = ListNode()
    assert lst.keys() == []


def test_list_node_items():
    lst = ListNode()
    lst["a"] = "first"
    lst["b"] = "second"
    assert lst.items() == [("a", "first"), ("b", "second")]


def test_list_node_items_empty():
    lst = ListNode()
    assert lst.items() == []


# --- Integration ---


def test_board_like_tree():
    """Build a board-shaped tree, mutate deep in it, verify watchers fire at all levels."""
    board_events = []
    columns_events = []
    column_events = []

    board = Node()
    board.title = "My Project"
    board.columns = ListNode()
    board.cards = ListNode()

    # Add a column with a nested meta
    board.columns["1"] = {"name": "Backlog", "color": "#800000"}
    board.columns["2"] = {"name": "Done"}

    # Add a card
    board.cards["001"] = {"title": "Fix bug", "body": "It's broken"}

    # Set up watchers at every level
    board.watch("columns", lambda n, k, old, new: board_events.append((n.path, k, new)))
    board.columns.watch("1", lambda n, k, old, new: columns_events.append((n.path, k, new)))
    board.columns["1"].watch("color", lambda n, k, old, new: column_events.append((old, new)))

    # Mutate deep in the tree
    board.columns["1"].color = "#ff0000"

    # All three levels should have fired
    assert len(column_events) == 1
    assert column_events[0] == ("#800000", "#ff0000")

    assert len(columns_events) == 1
    assert columns_events[0] == ("columns.1", "color", "#ff0000")

    assert len(board_events) == 1
    assert board_events[0] == ("columns.1", "color", "#ff0000")

    # Card mutation doesn't fire column watchers
    card_events = []
    board.cards.watch("001", lambda n, k, old, new: card_events.append((k, new)))
    board.cards["001"].title = "Fixed bug"
    assert len(card_events) == 1
    assert card_events[0] == ("title", "Fixed bug")
    assert len(column_events) == 1  # unchanged


# --- Node.update ---


def test_node_update_adds_keys():
    node = Node(a="1")
    other = Node(a="1", b="2")
    node.update(other)
    assert node.b == "2"


def test_node_update_deletes_keys():
    node = Node(a="1", b="2")
    other = Node(a="1")
    node.update(other)
    assert node.b is None
    assert "b" not in node


def test_node_update_changes_values():
    node = Node(a="1")
    other = Node(a="2")
    node.update(other)
    assert node.a == "2"


def test_node_update_skips_equal_values():
    events = []
    node = Node(a="1")
    node.watch("a", lambda n, k, old, new: events.append(1))
    other = Node(a="1")
    node.update(other)
    assert len(events) == 0


def test_node_update_recurses_into_child_nodes():
    node = Node()
    node.meta = {"color": "red"}
    original_meta = node.meta
    other = Node()
    other.meta = {"color": "blue"}
    node.update(other)
    assert node.meta is original_meta
    assert node.meta.color == "blue"


def test_node_update_preserves_watchers_on_children():
    events = []
    node = Node()
    node.meta = {"color": "red"}
    node.meta.watch("color", lambda n, k, old, new: events.append((old, new)))
    other = Node()
    other.meta = {"color": "blue"}
    node.update(other)
    assert events == [("red", "blue")]


def test_node_update_replaces_type_mismatch():
    """When old is a Node but new is a scalar (or vice versa), replace."""
    node = Node()
    node.meta = {"color": "red"}
    other = Node(meta="raw string")
    node.update(other)
    assert node.meta == "raw string"


def test_node_update_fires_watchers_for_changes():
    events = []
    node = Node(a="1", b="2")
    node.watch("a", lambda n, k, old, new: events.append(("a", old, new)))
    node.watch("b", lambda n, k, old, new: events.append(("b", old, new)))
    other = Node(a="1", b="3")
    node.update(other)
    assert events == [("b", "2", "3")]


# --- ListNode.update ---


def test_list_node_update_adds_keys():
    lst = ListNode()
    lst["a"] = "one"
    other = ListNode()
    other["a"] = "one"
    other["b"] = "two"
    lst.update(other)
    assert lst.keys() == ["a", "b"]
    assert list(lst) == ["one", "two"]


def test_list_node_update_deletes_keys():
    lst = ListNode()
    lst["a"] = "one"
    lst["b"] = "two"
    other = ListNode()
    other["a"] = "one"
    lst.update(other)
    assert lst.keys() == ["a"]
    assert list(lst) == ["one"]


def test_list_node_update_reorders():
    lst = ListNode()
    lst["a"] = "one"
    lst["b"] = "two"
    lst["c"] = "three"
    other = ListNode()
    other["c"] = "three"
    other["a"] = "one"
    other["b"] = "two"
    lst.update(other)
    assert lst.keys() == ["c", "a", "b"]
    assert list(lst) == ["three", "one", "two"]


def test_list_node_update_recurses_into_child_nodes():
    lst = ListNode()
    lst["a"] = {"name": "Backlog"}
    original = lst["a"]
    other = ListNode()
    other["a"] = {"name": "Archive"}
    lst.update(other)
    assert lst["a"] is original
    assert lst["a"].name == "Archive"


def test_list_node_update_preserves_watchers():
    events = []
    lst = ListNode()
    lst["a"] = {"name": "Backlog"}
    lst["a"].watch("name", lambda n, k, old, new: events.append((old, new)))
    other = ListNode()
    other["a"] = {"name": "Archive"}
    lst.update(other)
    assert events == [("Backlog", "Archive")]


def test_list_node_update_skips_equal_values():
    events = []
    lst = ListNode()
    lst["a"] = "one"
    lst.watch("a", lambda n, k, old, new: events.append(1))
    other = ListNode()
    other["a"] = "one"
    lst.update(other)
    assert len(events) == 0


# --- Node.rename_key ---


def test_node_rename_key():
    node = Node(a="1", b="2", c="3")
    node.rename_key("b", "beta")
    assert list(node.keys()) == ["a", "beta", "c"]
    assert node.beta == "2"
    assert node.b is None


def test_node_rename_key_preserves_order():
    node = Node(x="first", y="second", z="third")
    node.rename_key("x", "alpha")
    assert list(node.keys()) == ["alpha", "y", "z"]


def test_node_rename_key_fires_events():
    events = []
    node = Node(a="1", b="2")
    node.watch("a", lambda n, k, old, new: events.append(("a", old, new)))
    node.watch("beta", lambda n, k, old, new: events.append(("beta", old, new)))
    node.rename_key("a", "beta")
    assert ("a", "1", None) in events
    assert ("beta", None, "1") in events


def test_node_rename_key_missing():
    node = Node(a="1")
    node.rename_key("nonexistent", "whatever")
    assert list(node.keys()) == ["a"]


def test_node_rename_key_updates_child_key():
    node = Node()
    node.child = {"nested": "value"}
    node.rename_key("child", "renamed")
    assert node.renamed._key == "renamed"


def test_node_rename_key_conflict():
    node = Node(a="1", b="2", c="3")
    node.rename_key("a", "b")
    assert list(node.keys()) == ["b (1)", "b", "c"]
    assert node._children["b (1)"] == "1"
    assert node.b == "2"


def test_node_rename_key_conflict_multiple():
    node = Node()
    node.x = "original"
    setattr(node, "x (1)", "first copy")
    node.y = "to rename"
    node.rename_key("y", "x")
    assert list(node.keys()) == ["x", "x (1)", "x (2)"]
    assert node._children["x (2)"] == "to rename"


# --- ListNode.rename_first_key ---


def test_list_node_rename_first_key():
    lst = ListNode()
    lst["Title"] = "body"
    lst["Section"] = "content"
    lst.rename_first_key("New Title")
    assert lst.keys() == ["New Title", "Section"]
    assert lst["New Title"] == "body"
    assert lst["Title"] is None


def test_list_node_rename_first_key_preserves_values():
    lst = ListNode()
    lst["A"] = "one"
    lst["B"] = "two"
    lst["C"] = "three"
    lst.rename_first_key("Alpha")
    assert lst.keys() == ["Alpha", "B", "C"]
    assert list(lst) == ["one", "two", "three"]


def test_list_node_rename_first_key_empty():
    lst = ListNode()
    lst.rename_first_key("Whatever")
    assert lst.keys() == []


def test_list_node_rename_first_key_conflict():
    lst = ListNode()
    lst["Description"] = "about this card"
    lst["Notes"] = "some notes"
    lst.rename_first_key("Notes")
    assert lst.keys() == ["Notes (1)", "Notes"]
    assert lst["Notes (1)"] == "about this card"
    assert lst["Notes"] == "some notes"


def test_list_node_rename_first_key_conflict_multiple():
    lst = ListNode()
    lst["A"] = "first"
    lst["B"] = "second"
    lst["B (1)"] = "third"
    lst.rename_first_key("B")
    assert lst.keys() == ["B (2)", "B", "B (1)"]
    assert lst["B (2)"] == "first"


def test_list_node_add_no_conflict():
    lst = ListNode()
    actual = lst.add("Notes", "content")
    assert actual == "Notes"
    assert lst["Notes"] == "content"


def test_list_node_add_conflict():
    lst = ListNode()
    lst["Notes"] = "existing"
    actual = lst.add("Notes", "new content")
    assert actual == "Notes (1)"
    assert lst["Notes"] == "existing"
    assert lst["Notes (1)"] == "new content"


def test_list_node_add_conflict_multiple():
    lst = ListNode()
    lst["test"] = "first"
    assert lst.add("test", "second") == "test (1)"
    assert lst.add("test", "third") == "test (2)"
    assert lst.keys() == ["test", "test (1)", "test (2)"]


def test_rename_markdown_sections_conflict():
    """Renaming a markdown section heading to match an existing one gets suffixed."""
    doc = ListNode()
    doc["Description"] = "Card description"
    doc["Notes"] = "Existing notes"
    doc.rename_first_key("Notes")
    assert "Notes (1)" in doc.keys()
    assert doc["Notes"] == "Existing notes"
    assert doc["Notes (1)"] == "Card description"


def test_rename_users_conflict():
    """Renaming a user to a name that already exists gets suffixed."""
    users = Node()
    users.alice = {"email": "alice@example.com"}
    users.bob = {"email": "bob@example.com"}
    users.rename_key("alice", "bob")
    assert users._children["bob (1)"].email == "alice@example.com"
    assert users.bob.email == "bob@example.com"


def test_list_node_update_emits_on_reorder():
    events = []
    root = Node()
    root.things = ListNode(_parent=root, _key="things")
    root.things["a"] = "one"
    root.things["b"] = "two"
    root.watch("things", lambda n, k, old, new: events.append(k))
    other = ListNode()
    other["b"] = "two"
    other["a"] = "one"
    root.things.update(other)
    assert root.things.keys() == ["b", "a"]
    assert len(events) == 1
    assert events[0] == "*"
