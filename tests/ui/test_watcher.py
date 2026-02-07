"""Tests for NodeWatcherMixin."""

from ganban.model.node import Node
from ganban.ui.watcher import NodeWatcherMixin


class FakeWidget(NodeWatcherMixin):
    """Minimal stand-in for a Textual widget."""

    def __init__(self):
        self._init_watcher()


def test_watch_fires_callback():
    widget = FakeWidget()
    node = Node(color="red")
    calls = []
    widget.node_watch(node, "color", lambda src, key, old, new: calls.append((old, new)))

    node.color = "blue"
    assert calls == [("red", "blue")]


def test_suppression_skips_callback():
    widget = FakeWidget()
    node = Node(color="red")
    calls = []
    widget.node_watch(node, "color", lambda src, key, old, new: calls.append((old, new)))

    with widget.suppressing():
        node.color = "blue"
    assert calls == []

    node.color = "green"
    assert calls == [("blue", "green")]


def test_on_unmount_cleans_up():
    widget = FakeWidget()
    node = Node(color="red")
    calls = []
    widget.node_watch(node, "color", lambda src, key, old, new: calls.append(new))

    widget.on_unmount()

    node.color = "blue"
    assert calls == []


def test_multi_watch_cleanup():
    widget = FakeWidget()
    node = Node(color="red", size=10)
    color_calls = []
    size_calls = []
    widget.node_watch(node, "color", lambda src, key, old, new: color_calls.append(new))
    widget.node_watch(node, "size", lambda src, key, old, new: size_calls.append(new))

    node.color = "blue"
    node.size = 20
    assert color_calls == ["blue"]
    assert size_calls == [20]

    widget.on_unmount()

    node.color = "green"
    node.size = 30
    assert color_calls == ["blue"]
    assert size_calls == [20]


def test_suppression_is_exception_safe():
    widget = FakeWidget()
    node = Node(color="red")
    calls = []
    widget.node_watch(node, "color", lambda src, key, old, new: calls.append(new))

    try:
        with widget.suppressing():
            raise ValueError("boom")
    except ValueError:
        pass

    assert not widget._suppressing
    node.color = "blue"
    assert calls == ["blue"]
