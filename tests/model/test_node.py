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
    node.name = node.name  # same object
    assert node._version == v


def test_node_keys():
    node = Node(a="1", b="2")
    assert set(node.keys()) == {"a", "b"}


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
    node.name = node.name  # same object identity
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
