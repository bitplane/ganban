"""Base event messages for UI widgets."""

from __future__ import annotations

from textual.message import Message


class ValueChanged(Message):
    """Base message for value change events."""

    def __init__(self, old_value: str, new_value: str) -> None:
        super().__init__()
        self.old_value = old_value
        self.new_value = new_value
