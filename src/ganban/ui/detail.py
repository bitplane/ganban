"""Detail modals for viewing and editing markdown content."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import Click
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import ContentSwitcher, Static

from ganban.model.node import Node
from ganban.ui.assignee import AssigneeWidget
from ganban.ui.blocked import BlockedWidget
from ganban.ui.color import ColorButton
from ganban.ui.constants import ICON_TAB_DOC, ICON_TAB_META, ICON_TAB_RAW, ICON_TAB_USERS
from ganban.ui.done import DoneWidget
from ganban.ui.due import DueDateWidget
from ganban.ui.edit import DocHeader, MarkdownDocEditor, MetaEditor
from ganban.ui.markdown import ganban_parser_factory
from ganban.ui.users import UsersEditor


def _board_context(board: Node | None) -> tuple[Node | None, list[str] | None]:
    """Extract meta and committers from a board node."""
    if not board:
        return None, None
    meta = board.meta
    committers = board.git.committers if board.git else None
    return meta, committers if isinstance(committers, list) else None


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
    }

    #detail-title-bar {
        width: 100%;
        height: auto;
        background: $primary;
        padding: 0 1;
    }

    #detail-id {
        width: auto;
        height: 1;
        text-style: bold;
    }

    #detail-bar {
        width: 100%;
        height: 1;
        padding: 0 1;
    }

    #detail-tabs {
        width: auto;
        height: 1;
        dock: right;
    }

    #detail-content {
        width: 100%;
        height: 1fr;
        padding: 1 1 0 1;
    }
    """

    BINDINGS = [
        ("escape", "close", "Close"),
        ("ctrl+q", "quit", "Quit"),
    ]

    def on_mount(self) -> None:
        self.call_after_refresh(self._focus_content)

    def _focus_content(self) -> None:
        content = self.query_one("#detail-content", ContentSwitcher)
        for widget in content.query("*"):
            if widget.can_focus:
                widget.focus()
                return

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

    DEFAULT_CSS = """
    CardDetailModal.blocked #detail-container {
        background: $error-darken-3;
    }
    CardDetailModal.blocked #detail-title-bar {
        background: $error;
    }
    """

    def __init__(self, card: Node, board: Node | None = None) -> None:
        super().__init__()
        self.card = card
        self.board = board

    def on_mount(self) -> None:
        super().on_mount()
        self.set_class(bool(self.card.meta.blocked), "blocked")
        self._unwatch_blocked = self.card.meta.watch("blocked", self._on_blocked_changed)

    def _on_blocked_changed(self, node, key, old, new) -> None:
        self.set_class(bool(new), "blocked")

    def on_unmount(self) -> None:
        self._unwatch_blocked()

    def compose(self) -> ComposeResult:
        meta, committers = _board_context(self.board)
        pf = ganban_parser_factory(meta, committers)
        card_id = self.card.file_path.split("/")[-1].removesuffix(".md")
        with Vertical(id="detail-container"):
            with Horizontal(id="detail-title-bar"):
                yield Static(f"#{card_id} ", id="detail-id")
                yield DocHeader(self.card.sections)
                with Horizontal(id="detail-tabs"):
                    yield TabButton(ICON_TAB_DOC, "tab-doc", classes="-active")
                    yield TabButton(ICON_TAB_META, "tab-meta")
                    yield TabButton(ICON_TAB_RAW, "tab-raw")
            with Horizontal(id="detail-bar"):
                yield DoneWidget(self.card.meta)
                yield BlockedWidget(self.card.meta)
                yield DueDateWidget(self.card.meta)
                if self.board:
                    yield AssigneeWidget(self.card.meta, self.board)
            with ContentSwitcher(initial="tab-doc", id="detail-content"):
                yield MarkdownDocEditor(
                    self.card.sections, include_header=False, meta=meta, parser_factory=pf, id="tab-doc"
                )
                yield MetaEditor(self.card.meta, id="tab-meta")
                yield Static("Coming soon", id="tab-raw")


class CompactButton(Static):
    """Toggle button for compact/card view mode."""

    DEFAULT_CSS = """
    CompactButton { width: 2; height: 1; }
    CompactButton:hover { background: $primary-darken-2; }
    """

    def __init__(self, meta: Node, **kwargs) -> None:
        super().__init__(**kwargs)
        self._meta = meta

    def on_mount(self) -> None:
        self._refresh_label()

    def on_click(self, event) -> None:
        event.stop()
        self._meta.compact = None if self._meta.compact else True
        self._refresh_label()

    def _refresh_label(self) -> None:
        self.update("\u2261\u2261" if self._meta.compact else "\u2fbf")


class ColumnDetailModal(DetailModal):
    """Modal screen showing full column details."""

    def __init__(self, column: Node, board: Node | None = None) -> None:
        super().__init__()
        self.column = column
        self.board = board

    def compose(self) -> ComposeResult:
        meta, committers = _board_context(self.board)
        pf = ganban_parser_factory(meta, committers)
        color = self.column.meta.color
        with Vertical(id="detail-container"):
            with Horizontal(id="detail-title-bar"):
                yield DocHeader(self.column.sections)
                with Horizontal(id="detail-tabs"):
                    yield TabButton(ICON_TAB_DOC, "tab-doc", classes="-active")
                    yield TabButton(ICON_TAB_META, "tab-meta")
                    yield TabButton(ICON_TAB_RAW, "tab-raw")
            with Horizontal(id="detail-bar"):
                yield ColorButton(color=color)
                yield CompactButton(self.column.meta)
            with ContentSwitcher(initial="tab-doc", id="detail-content"):
                yield MarkdownDocEditor(
                    self.column.sections, include_header=False, meta=meta, parser_factory=pf, id="tab-doc"
                )
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
        meta, committers = _board_context(self.board)
        pf = ganban_parser_factory(meta, committers)
        with Vertical(id="detail-container"):
            with Horizontal(id="detail-title-bar"):
                yield DocHeader(self.board.sections)
                with Horizontal(id="detail-tabs"):
                    yield TabButton(ICON_TAB_DOC, "tab-doc", classes="-active")
                    yield TabButton(ICON_TAB_META, "tab-meta")
                    yield TabButton(ICON_TAB_USERS, "tab-users")
                    yield TabButton(ICON_TAB_RAW, "tab-raw")
            with ContentSwitcher(initial="tab-doc", id="detail-content"):
                yield MarkdownDocEditor(
                    self.board.sections, include_header=False, meta=meta, parser_factory=pf, id="tab-doc"
                )
                yield MetaEditor(self.board.meta, id="tab-meta")
                yield UsersEditor(self.board.meta, id="tab-users")
                yield Static("Coming soon", id="tab-raw")
