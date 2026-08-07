"""Reactive tree nodes with change notification and bubbling."""

from __future__ import annotations

from typing import Any, Callable

Callback = Callable[["Node | ListNode", str, Any, Any], None]


def _unique_key(desired: str, existing: set[str]) -> str:
    """Return desired if unused, otherwise append (1), (2), etc."""
    if desired not in existing:
        return desired
    n = 1
    while f"{desired} ({n})" in existing:
        n += 1
    return f"{desired} ({n})"


def _wrap(value: Any, parent: Node | ListNode, key: str) -> Any:
    """Auto-wrap dicts as Nodes; adopt or clone existing Nodes/ListNodes.

    Parentless nodes and same-parent reassignments are adopted in place,
    preserving identity and watchers. A node that already lives in a
    different container is cloned instead of silently reparented, so the
    original tree keeps its watcher bubbling intact.
    """
    if isinstance(value, dict) and not isinstance(value, Node):
        return Node(_parent=parent, _key=key, **value)
    if isinstance(value, (Node, ListNode)):
        if value._parent is not None and value._parent is not parent:
            value = value.clone()
        object.__setattr__(value, "_parent", parent)
        object.__setattr__(value, "_key", key)
    return value


def _clone_value(value: Any, parent: Node | ListNode, key: str) -> Any:
    """Deep-copy a value for clone(), reparenting child nodes to the clone."""
    if isinstance(value, (Node, ListNode)):
        child = value.clone()
        object.__setattr__(child, "_parent", parent)
        object.__setattr__(child, "_key", key)
        return child
    if isinstance(value, dict):
        return {k: _clone_value(v, parent, key) for k, v in value.items()}
    if isinstance(value, list):
        return [_clone_value(v, parent, key) for v in value]
    return value


def _emit(node: Node | ListNode, key: str, old: Any, new: Any) -> None:
    """Fire local watchers for key, then bubble up the parent chain."""
    for cb in node._watchers.get(key, ()):
        cb(node, key, old, new)
    child = node
    while child._parent is not None:
        parent = child._parent
        for cb in parent._watchers.get(child._key, ()):
            cb(node, key, old, new)
        child = parent


class _Watchable:
    """Shared watcher registry and path computation for Node and ListNode."""

    def watch(self, key: str, callback: Callback) -> Callable[[], None]:
        """Watch a key for changes. Returns an unwatch callable."""
        key = str(key)
        self._watchers.setdefault(key, []).append(callback)
        return lambda: self._watchers.get(key, []) and self._watchers[key].remove(callback)

    @property
    def path(self) -> str:
        """Dotted path from root to this node."""
        parts: list[str] = []
        current: Node | ListNode | None = self
        while current is not None and current._key is not None:
            parts.append(current._key)
            current = current._parent
        return ".".join(reversed(parts))


class Node(_Watchable):
    """Reactive dict-like tree node.

    Stores data in an internal dict, accessed via attribute syntax.
    Setting a value to None deletes the key. Dict values are
    auto-wrapped as child Nodes. Changes fire watchers and bubble
    up through the parent chain.
    """

    def __init__(
        self,
        _parent: Node | ListNode | None = None,
        _key: str | None = None,
        **data: Any,
    ) -> None:
        object.__setattr__(self, "_children", {})
        object.__setattr__(self, "_watchers", {})
        object.__setattr__(self, "_parent", None)
        object.__setattr__(self, "_key", _key)
        for k, v in data.items():
            setattr(self, k, v)
        object.__setattr__(self, "_parent", _parent)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        return self._children.get(name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("_"):
            object.__setattr__(self, name, value)
            return
        old = self._children.get(name)
        if value is None:
            self._children.pop(name, None)
        else:
            value = _wrap(value, parent=self, key=name)
            self._children[name] = value
        if old != value:
            _emit(self, name, old, value)

    def __contains__(self, key: str) -> bool:
        return key in self._children

    def keys(self):
        """Return children keys."""
        return self._children.keys()

    def items(self):
        """Return children items."""
        return self._children.items()

    def values(self):
        """Return children values."""
        return self._children.values()

    def update(self, other: Node) -> None:
        """Update this node in-place to match other, preserving watchers."""
        other_keys = set(other.keys())
        for key in set(self.keys()) - other_keys:
            setattr(self, key, None)
        for key in other.keys():
            old_value = self._children.get(key)
            new_value = other._children.get(key)
            if isinstance(old_value, Node) and isinstance(new_value, Node):
                old_value.update(new_value)
            elif isinstance(old_value, ListNode) and isinstance(new_value, ListNode):
                old_value.update(new_value)
            elif old_value == new_value:
                continue
            else:
                setattr(self, key, new_value)
        # Match other's key order so serialization (e.g. YAML front-matter)
        # is deterministic and identical across replicas
        order = list(other.keys())
        if list(self._children.keys()) != order:
            self._children = {key: self._children[key] for key in order}

    def clone(self) -> "Node":
        """Deep-copy this subtree without watchers or the parent link.

        Used to snapshot the board on the event-loop thread so background
        saves never iterate structures the UI is still mutating.
        """
        n = Node()
        for key, value in self._children.items():
            n._children[key] = _clone_value(value, n, key)
        return n

    def rename_key(self, old_key: str, new_key: str) -> None:
        """Rename a key in _children, preserving insertion order."""
        value = self._children.get(old_key)
        if value is None:
            return
        siblings = set(self._children.keys()) - {old_key}
        new_key = _unique_key(new_key, siblings)
        items = list(self.items())
        for key, _ in items:
            self._children.pop(key, None)
        for key, val in items:
            k = new_key if key == old_key else key
            self._children[k] = val
        if hasattr(value, "_key"):
            object.__setattr__(value, "_key", new_key)
        _emit(self, old_key, value, None)
        _emit(self, new_key, None, value)

    def __repr__(self) -> str:
        p = self.path
        keys = ", ".join(self._children.keys())
        label = f"Node({p})" if p else "Node"
        return f"<{label} [{keys}]>"


class ListNode(_Watchable):
    """Ordered, id-keyed collection with change notification.

    Items are accessed by string id. Setting to None deletes.
    Dicts are auto-wrapped as Nodes. Changes fire watchers and
    bubble up through the parent chain. Order is the insertion order
    of _by_id; replacing a value keeps its position.
    """

    def __init__(
        self,
        _parent: Node | None = None,
        _key: str | None = None,
    ) -> None:
        object.__setattr__(self, "_by_id", {})
        object.__setattr__(self, "_watchers", {})
        object.__setattr__(self, "_parent", _parent)
        object.__setattr__(self, "_key", _key)

    def __getitem__(self, key: str) -> Any:
        return self._by_id.get(str(key))

    def __setitem__(self, key: str, value: Any) -> None:
        key = str(key)
        old = self._by_id.get(key)
        if value is None:
            if old is not None:
                del self._by_id[key]
            _emit(self, key, old, None)
        else:
            value = _wrap(value, parent=self, key=key)
            self._by_id[key] = value
            if old != value:
                _emit(self, key, old, value)

    def __iter__(self):
        return iter(list(self._by_id.values()))

    def __len__(self) -> int:
        return len(self._by_id)

    def __contains__(self, key: str) -> bool:
        return str(key) in self._by_id

    def keys(self):
        """Return ordered keys."""
        return list(self._by_id.keys())

    def items(self):
        """Return ordered (key, value) pairs."""
        return list(self._by_id.items())

    def update(self, other: ListNode) -> None:
        """Update this list in-place to match other, preserving watchers."""
        existing_keys = set(self._by_id.keys())
        other_keys = set(other._by_id.keys())
        # Delete removed keys
        for key in existing_keys - other_keys:
            self[key] = None
        # Update matching keys, add new keys
        for key in other._by_id:
            old_value = self._by_id.get(key)
            new_value = other._by_id.get(key)
            if old_value is None:
                self[key] = new_value
            elif isinstance(old_value, Node) and isinstance(new_value, Node):
                old_value.update(new_value)
            elif isinstance(old_value, ListNode) and isinstance(new_value, ListNode):
                old_value.update(new_value)
            elif old_value == new_value:
                continue
            else:
                self[key] = new_value
        # Reorder to match other
        old_keys = self.keys()
        new_keys = list(other._by_id.keys())
        if old_keys != new_keys:
            new_by_id = {k: self._by_id[k] for k in new_keys}
            object.__setattr__(self, "_by_id", new_by_id)
            _emit(self, "*", old_keys, new_keys)

    def clone(self) -> "ListNode":
        """Deep-copy this list without watchers or the parent link."""
        ln = ListNode()
        for key, value in self._by_id.items():
            ln._by_id[key] = _clone_value(value, ln, key)
        return ln

    def add(self, key: str, value: Any) -> str:
        """Add a new item, deduplicating the key if it already exists.

        Returns the actual key used.
        """
        key = _unique_key(str(key), set(self._by_id.keys()))
        self[key] = value
        return key

    def rename_first_key(self, new_title: str) -> None:
        """Rename the first key by rebuilding the list."""
        items = self.items()
        if items:
            other_keys = set(self._by_id.keys()) - {items[0][0]}
            new_title = _unique_key(new_title, other_keys)
        for key, _ in items:
            self[key] = None
        if items:
            items[0] = (new_title, items[0][1])
        for key, val in items:
            self[key] = val

    def __repr__(self) -> str:
        p = self.path
        ids = ", ".join(self._by_id.keys())
        label = f"ListNode({p})" if p else "ListNode"
        return f"<{label} [{ids}]>"
