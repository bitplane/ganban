"""Detail modals for viewing and editing markdown content."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import Click
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import ContentSwitcher, Static

from ganban.model.node import Node
from ganban.ui.color import ColorButton
from ganban.ui.due import DueDateWidget
from ganban.ui.edit import DocHeader, MarkdownDocEditor, MetaEditor


class TabButton(Static):
    """A clickable tab icon button."""

    class Clicked(Message):
        def __init__(self, tab_id: str) -> None:
            super().__init__()
            self.tab_id = tab_id

    DEFAULT_CSS = """
    TabButton {
        width: auto;
        height: 1;
        padding: 0 1;
    }
    TabButton:hover {
        background: $primary-darken-2;
    }
    TabButton.-active {
        background: $primary-darken-2;
        text-style: bold;
    }
    """

    def __init__(self, label: str, tab_id: str, **kwargs) -> None:
        super().__init__(label, **kwargs)
        self.tab_id = tab_id

    def on_click(self, event: Click) -> None:
        event.stop()
        self.post_message(self.Clicked(self.tab_id))


class DetailModal(ModalScreen[None]):
    """Base modal screen for detail editing."""

    DEFAULT_CSS = """
    DetailModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.6);
    }

    #detail-container {
        width: 90%;
        height: 90%;
        background: $surface;
        border: solid $primary;
        padding: 0 1;
    }

    #detail-bar {
        width: 100%;
        height: 1;
    }

    #detail-tabs {
        width: auto;
        height: 1;
        dock: right;
    }

    #detail-content {
        width: 100%;
        height: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "close", "Close"),
        ("ctrl+q", "quit", "Quit"),
    ]

    def on_click(self, event: Click) -> None:
        """Dismiss modal when clicking outside the detail container."""
        container = self.query_one("#detail-container")
        if not container.region.contains(event.screen_x, event.screen_y):
            self.dismiss()

    def on_tab_button_clicked(self, event: TabButton.Clicked) -> None:
        event.stop()
        self.query_one("#detail-content", ContentSwitcher).current = event.tab_id
        for btn in self.query(TabButton):
            btn.set_class(btn.tab_id == event.tab_id, "-active")

    def action_close(self) -> None:
        """Close the modal."""
        self.dismiss()

    async def action_quit(self) -> None:
        """Quit the app via the main save-and-exit path."""
        await self.app.run_action("quit")


class CardDetailModal(DetailModal):
    """Modal screen showing full card details."""

    def __init__(self, card: Node) -> None:
        super().__init__()
        self.card = card

    def compose(self) -> ComposeResult:
        with Vertical(id="detail-container"):
            yield DocHeader(self.card.sections)
            with Horizontal(id="detail-bar"):
                yield DueDateWidget(self.card.meta)
                with Horizontal(id="detail-tabs"):
                    yield TabButton("\U0001f4dd", "tab-doc", classes="-active")
                    yield TabButton("\U0001f527", "tab-meta")
                    yield TabButton("\U0001f440", "tab-raw")
            with ContentSwitcher(initial="tab-doc", id="detail-content"):
                yield MarkdownDocEditor(self.card.sections, include_header=False, id="tab-doc")
                yield MetaEditor(self.card.meta, id="tab-meta")
                yield Static("Coming soon", id="tab-raw")


class ColumnDetailModal(DetailModal):
    """Modal screen showing full column details."""

    def __init__(self, column: Node) -> None:
        super().__init__()
        self.column = column

    def compose(self) -> ComposeResult:
        color = self.column.meta.color
        with Vertical(id="detail-container"):
            yield DocHeader(self.column.sections)
            with Horizontal(id="detail-bar"):
                yield ColorButton(color=color)
                with Horizontal(id="detail-tabs"):
                    yield TabButton("\U0001f4dd", "tab-doc", classes="-active")
                    yield TabButton("\U0001f527", "tab-meta")
                    yield TabButton("\U0001f440", "tab-raw")
            with ContentSwitcher(initial="tab-doc", id="detail-content"):
                yield MarkdownDocEditor(self.column.sections, include_header=False, id="tab-doc")
                yield MetaEditor(self.column.meta, id="tab-meta")
                yield Static("Coming soon", id="tab-raw")

    def on_color_button_color_selected(self, event: ColorButton.ColorSelected) -> None:
        event.stop()
        self.column.meta.color = event.color


class BoardDetailModal(DetailModal):
    """Modal screen showing full board details."""

    def __init__(self, board: Node) -> None:
        super().__init__()
        self.board = board

    def compose(self) -> ComposeResult:
        with Vertical(id="detail-container"):
            with Horizontal(id="detail-bar"):
                with Horizontal(id="detail-tabs"):
                    yield TabButton("\U0001f4dd", "tab-doc", classes="-active")
                    yield TabButton("\U0001f527", "tab-meta")
                    yield TabButton("\U0001f440", "tab-raw")
            with ContentSwitcher(initial="tab-doc", id="detail-content"):
                yield MarkdownDocEditor(self.board.sections, id="tab-doc")
                yield MetaEditor(self.board.meta, id="tab-meta")
                yield Static("Coming soon", id="tab-raw")
