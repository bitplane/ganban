"""Text area widgets with submission behavior."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.message import Message
from textual.widgets import TextArea

if TYPE_CHECKING:
    from textual.events import Key


class SubmittingTextArea(TextArea):
    """TextArea that submits on Enter and blur, cancels on Escape."""

    class Submitted(Message):
        """Emitted when Enter is pressed or focus lost."""

    class Cancelled(Message):
        """Emitted when Escape is pressed."""

    async def _on_key(self, event: Key) -> None:
        if event.key == "enter":
            event.prevent_default()
            event.stop()
            self.post_message(self.Submitted())
        elif event.key == "escape":
            event.prevent_default()
            event.stop()
            self.post_message(self.Cancelled())
        else:
            await super()._on_key(event)

    def on_blur(self) -> None:
        self.post_message(self.Submitted())


class MarkdownTextArea(SubmittingTextArea):
    """TextArea for markdown - submits on blur only, Enter inserts newline."""

    async def _on_key(self, event: Key) -> None:
        if event.key == "escape":
            event.prevent_default()
            event.stop()
            self.post_message(self.Cancelled())
        else:
            await TextArea._on_key(self, event)
