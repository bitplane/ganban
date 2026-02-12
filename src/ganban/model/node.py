"""Reactive tree nodes with change notification and bubbling."""

from __future__ import annotations

from typing import Any, Callable

BRANCH_NAME = "ganban"

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
    """Auto-wrap dicts as Nodes. Reparent existing Nodes/ListNodes."""
    if isinstance(value, dict) and not isinstance(value, Node):
        return Node(_parent=parent, _key=key, **value)
    if isinstance(value, (Node, ListNode)):
        object.__setattr__(value, "_parent", parent)
        object.__setattr__(value, "_key", key)
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


class Node:
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
        object.__setattr__(self, "_version", 0)
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
            self._version += 1
            _emit(self, name, old, value)

    def __contains__(self, key: str) -> bool:
        return key in self._children

    def watch(self, key: str, callback: Callback) -> Callable[[], None]:
        """Watch a key for changes. Returns an unwatch callable."""
        self._watchers.setdefault(key, []).append(callback)
        return lambda: self._watchers.get(key, []) and self._watchers[key].remove(callback)

    def keys(self):
        """Return children keys."""
        return self._children.keys()

    def items(self):
        """Return children items."""
        return self._children.items()

    def values(self):
        """Return children values."""
        return self._children.values()

    @property
    def path(self) -> str:
        """Dotted path from root to this node."""
        parts: list[str] = []
        current: Node | ListNode | None = self
        while current is not None and current._key is not None:
            parts.append(current._key)
            current = current._parent
        return ".".join(reversed(parts))

    def update(self, other: Node) -> None:
        """Update this node in-place to match other, preserving watchers."""
        existing_keys = set(self.keys())
        other_keys = set(other.keys())
        for key in existing_keys - other_keys:
            setattr(self, key, None)
        for key in other_keys:
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
        self._version += 1
        _emit(self, old_key, value, None)
        _emit(self, new_key, None, value)

    def __repr__(self) -> str:
        p = self.path
        keys = ", ".join(self._children.keys())
        label = f"Node({p})" if p else "Node"
        return f"<{label} [{keys}]>"


class ListNode:
    """Ordered, id-keyed collection with change notification.

    Items are accessed by string id. Setting to None deletes.
    Dicts are auto-wrapped as Nodes. Changes fire watchers and
    bubble up through the parent chain.
    """

    def __init__(
        self,
        _parent: Node | None = None,
        _key: str | None = None,
    ) -> None:
        object.__setattr__(self, "_items", [])
        object.__setattr__(self, "_by_id", {})
        object.__setattr__(self, "_watchers", {})
        object.__setattr__(self, "_parent", _parent)
        object.__setattr__(self, "_key", _key)
        object.__setattr__(self, "_version", 0)

    def __getitem__(self, key: str) -> Any:
        return self._by_id.get(str(key))

    def _key_index(self, key: str) -> int:
        """Find the index of a key in insertion order."""
        for i, k in enumerate(self._by_id):
            if k == key:
                return i
        raise KeyError(key)

    def __setitem__(self, key: str, value: Any) -> None:
        key = str(key)
        old = self._by_id.get(key)
        if value is None:
            if old is not None:
                idx = self._key_index(key)
                del self._items[idx]
                del self._by_id[key]
            self._version += 1
            _emit(self, key, old, None)
        else:
            value = _wrap(value, parent=self, key=key)
            if old is not None:
                idx = self._key_index(key)
                self._items[idx] = value
            else:
                self._items.append(value)
            self._by_id[key] = value
            if old != value:
                self._version += 1
                _emit(self, key, old, value)

    def __iter__(self):
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __contains__(self, key: str) -> bool:
        return str(key) in self._by_id

    def watch(self, key: str, callback: Callback) -> Callable[[], None]:
        """Watch an item id for changes. Returns an unwatch callable."""
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

    def keys(self):
        """Return ordered keys."""
        return list(self._by_id.keys())

    def items(self):
        """Return ordered (key, value) pairs."""
        return list(zip(self._by_id.keys(), self._items))

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
            new_items = [new_by_id[k] for k in new_keys]
            object.__setattr__(self, "_by_id", new_by_id)
            object.__setattr__(self, "_items", new_items)
            self._version += 1
            _emit(self, "*", old_keys, new_keys)

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
