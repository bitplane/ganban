"""Due date widget with inline editing."""

from datetime import date

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.message import Message
from textual.widgets import Static

from ganban.ui.cal import DateButton, date_diff
from ganban.ui.menu import ContextMenu, MenuItem, MenuRow


class DueDateLabel(Static):
    """Shows due date text, swaps to delete icon on hover."""

    class Confirmed(Message):
        """Emitted when delete is confirmed."""

    DEFAULT_CSS = """
    DueDateLabel { width: auto; height: 1; }
    DueDateLabel:hover { background: $primary-darken-2; }
    DueDateLabel.overdue { color: $error; }
    """

    def __init__(self, text: str = "", **kwargs):
        super().__init__(text, **kwargs)
        self._label_text = text
        self._hovering = False

    def set_label(self, text: str) -> None:
        self._label_text = text
        if not self._hovering:
            self.update(text)

    def on_enter(self, event) -> None:
        if event.node is self and self._label_text:
            self._hovering = True
            self.update("🚫")

    def on_leave(self, event) -> None:
        if event.node is self:
            self._hovering = False
            self.update(self._label_text)

    def on_click(self, event) -> None:
        if not self._hovering:
            return
        event.stop()
        menu = ContextMenu(
            [MenuRow(MenuItem("🔙", item_id="cancel"), MenuItem("🚫", item_id="confirm"))],
            event.screen_x,
            event.screen_y,
        )
        self.app.push_screen(menu, self._on_menu_closed)

    def _on_menu_closed(self, item: MenuItem | None) -> None:
        if item and item.item_id == "confirm":
            self.post_message(self.Confirmed())


class DueDateWidget(Container):
    """Inline due date display with calendar picker."""

    class Changed(Message):
        """Emitted when due date changes."""

        def __init__(self, due: date | None) -> None:
            super().__init__()
            self.due = due

        @property
        def control(self) -> "DueDateWidget":
            return self._sender

    DEFAULT_CSS = """
    DueDateWidget {
        width: auto;
        height: 1;
    }
    DueDateWidget Horizontal {
        width: auto;
        height: 1;
    }
    DueDateWidget #due-picker {
        margin-right: 1;
    }
    """

    def __init__(self, due: date | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._due = due

    @property
    def due(self) -> date | None:
        return self._due

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield DateButton(selected=self._due, icon="⏰", id="due-picker")
            yield DueDateLabel("", id="due-label")

    def on_mount(self) -> None:
        self._update_label()

    def _update_label(self) -> None:
        label = self.query_one("#due-label", DueDateLabel)
        if self._due:
            text = date_diff(self._due, date.today())
            label.set_label(text)
            label.set_class(self._due <= date.today(), "overdue")
            self.set_class(True, "has-due")
        else:
            label.set_label("")
            self.set_class(False, "has-due")

    def on_date_button_date_selected(self, event: DateButton.DateSelected) -> None:
        event.stop()
        self._due = event.date
        self._update_label()
        self.post_message(self.Changed(self._due))

    def on_due_date_label_confirmed(self, event: DueDateLabel.Confirmed) -> None:
        event.stop()
        self._due = None
        self._update_label()
        self.post_message(self.Changed(None))
