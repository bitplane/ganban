"""Messages for editable widgets."""

from textual.message import Message


class Save(Message):
    """Editor finished - save this value."""

    def __init__(self, value: str) -> None:
        super().__init__()
        self.value = value


class Cancel(Message):
    """Editor finished - discard changes."""
