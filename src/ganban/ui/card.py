"""Card widgets for ganban UI."""

from datetime import date

from textual.app import ComposeResult
from textual.message import Message
from textual.widgets import Rule, Static

from ganban.model.card import create_card, find_card_column
from ganban.model.node import Node
from ganban.parser import first_title
from ganban.ui.card_indicators import build_footer_text
from ganban.ui.constants import (
    ICON_BACK,
    ICON_CARD,
    ICON_CHECKED,
    ICON_CONFIRM,
    ICON_DELETE,
    ICON_EDIT,
    ICON_MOVE_TO,
    ICON_UNCHECKED,
)
from ganban.ui.detail import CardDetailModal
from ganban.ui.drag import DraggableMixin, DragGhost
from ganban.ui.menu import ContextMenu, MenuItem, MenuSeparator
from ganban.ui.edit import EditableText, TextEditor
from ganban.ui.static import PlainStatic
from ganban.ui.watcher import NodeWatcherMixin


def _card_title(board: Node, card_id: str) -> str:
    """Get the display title for a card."""
    card = board.cards[card_id]
    if not card or not card.sections:
        return card_id
    return first_title(card.sections) or card_id


class CardWidget(NodeWatcherMixin, DraggableMixin, Static, can_focus=True):
    """A single card in a column."""

    BINDINGS = [
        ("space", "open_card"),
        ("enter", "open_card"),
        ("delete", "confirm_archive"),
    ]

    def action_open_card(self) -> None:
        self.draggable_clicked()

    class MoveRequested(Message):
        """Posted when card should be moved to another column."""

        def __init__(self, card: "CardWidget", target_column: str):
            super().__init__()
            self.card = card
            self.target_column = target_column

    class ArchiveRequested(Message):
        """Posted when card should be archived."""

        def __init__(self, card: "CardWidget"):
            super().__init__()
            self.card = card

    DEFAULT_CSS = """
    CardWidget {
        width: 100%;
        height: auto;
        padding: 0 1;
        margin-bottom: 1;
        background: $surface;
    }
    CardWidget:focus {
        background: $primary;
    }
    CardWidget.blocked {
        background: $error-darken-3;
    }
    CardWidget.blocked:focus {
        background: $error;
    }
    CardWidget.dragging {
        display: none;
    }
    CardWidget #card-header {
        width: 100%;
        height: 1;
        margin: 0;
    }
    CardWidget #card-footer {
        width: 100%;
        height: 1;
        color: $text-muted;
    }
    """

    def __init__(self, card_id: str, board: Node):
        self._init_watcher()
        Static.__init__(self)
        self._init_draggable()
        self.card_id = card_id
        self.board = board
        self.title = _card_title(board, card_id)

    def compose(self) -> ComposeResult:
        yield Rule(id="card-header")
        yield PlainStatic(self.title or self.card_id, id="card-title")
        yield PlainStatic(id="card-footer")

    def on_mount(self) -> None:
        card = self.board.cards[self.card_id]
        self.node_watch(card, "sections", self._on_card_changed)
        self.node_watch(card, "meta", self._on_card_changed)
        if self.board.meta:
            self.node_watch(self.board.meta, "users", self._on_card_changed)
        self._refresh_indicators()

    def _on_card_changed(self, node, key, old, new) -> None:
        """Update card display when sections or meta change."""
        new_title = _card_title(self.board, self.card_id)
        if new_title != self.title:
            self.title = new_title
            self.query_one("#card-title", PlainStatic).update(self.title or self.card_id)
        self._refresh_indicators()

    def _refresh_indicators(self) -> None:
        """Update footer indicator text and blocked state."""
        card = self.board.cards[self.card_id]
        footer_text = build_footer_text(card.sections, card.meta, self.board.meta)
        self.query_one("#card-footer", PlainStatic).update(footer_text)
        self.set_class(bool(card.meta.blocked), "blocked")

    def draggable_make_ghost(self):
        return DragGhost(self)

    def draggable_clicked(self) -> None:
        card = self.board.cards[self.card_id]
        self.app.push_screen(CardDetailModal(card, self.board))

    def _find_column(self) -> Node | None:
        """Find the column containing this card."""
        return find_card_column(self.board, self.card_id)

    def on_click(self, event) -> None:
        if event.button == 3:  # Right click
            event.stop()
            self.show_context_menu(event.screen_x, event.screen_y)

    def show_context_menu(self, x: int | None = None, y: int | None = None) -> None:
        if x is None or y is None:
            region = self.region
            x = region.x + region.width // 2
            y = region.y + region.height // 2
        current_col = self._find_column()
        move_items = [
            MenuItem(first_title(col.sections), f"move:{first_title(col.sections)}", disabled=(col is current_col))
            for col in self.board.columns
            if not col.hidden
        ]
        card = self.board.cards[self.card_id]
        done_label = f"{ICON_CHECKED} Done" if card.meta.done else f"{ICON_UNCHECKED} Done"
        blocked_label = f"{ICON_CHECKED} Blocked" if card.meta.blocked else f"{ICON_UNCHECKED} Blocked"
        items = [
            MenuItem(f"{ICON_CARD} {self.title}", disabled=True),
            MenuSeparator(),
            MenuItem(f"{ICON_EDIT} Edit", "edit"),
            MenuItem(f"{ICON_MOVE_TO} Move to", submenu=move_items),
            MenuItem(done_label, "toggle-done"),
            MenuItem(blocked_label, "toggle-blocked"),
            MenuSeparator(),
            MenuItem(f"{ICON_DELETE} Archive", "archive"),
        ]
        self.app.push_screen(ContextMenu(items, x, y), self._on_menu_closed)

    def _on_menu_closed(self, item: MenuItem | None) -> None:
        if item is None:
            return
        match item.item_id:
            case "edit":
                card = self.board.cards[self.card_id]
                self.app.push_screen(CardDetailModal(card, self.board))
            case "archive":
                self._confirm_archive()
            case "toggle-done":
                card = self.board.cards[self.card_id]
                card.meta.done = None if card.meta.done else date.today().isoformat()
            case "toggle-blocked":
                card = self.board.cards[self.card_id]
                card.meta.blocked = None if card.meta.blocked else True
            case s if s and s.startswith("move:"):
                col_name = s[5:]
                self._move_to_column(col_name)

    def action_confirm_archive(self) -> None:
        self._confirm_archive()

    def _confirm_archive(self) -> None:
        region = self.region
        x = region.x + region.width // 2
        y = region.y + region.height // 2
        items = [
            MenuItem(f"{ICON_DELETE} Archive {self.title}?", disabled=True),
            MenuSeparator(),
            MenuItem(f"{ICON_CONFIRM} Confirm", "confirm"),
            MenuItem(f"{ICON_BACK} Cancel", "cancel"),
        ]
        self.app.push_screen(ContextMenu(items, x, y), self._on_archive_confirmed)

    def _on_archive_confirmed(self, item: MenuItem | None) -> None:
        if item and item.item_id == "confirm":
            self.post_message(self.ArchiveRequested(self))

    def _move_to_column(self, col_name: str) -> None:
        """Request move to the named column."""
        self.post_message(self.MoveRequested(self, col_name))


class AddCard(Static, can_focus=True):
    """Widget to add a new card to a column."""

    BINDINGS = [
        ("space", "start_editing"),
        ("enter", "start_editing"),
    ]

    def action_start_editing(self) -> None:
        self.query_one(EditableText)._start_edit()

    class CardCreated(Message):
        """Posted when a new card is created."""

        def __init__(self, column: Node, card_id: str, title: str):
            super().__init__()
            self.column = column
            self.card_id = card_id
            self.title = title

    DEFAULT_CSS = """
    AddCard {
        width: 100%;
        height: auto;
        padding: 0 1;
        margin-bottom: 1;
        border: dashed $surface-lighten-2;
    }
    AddCard:focus {
        background: $primary;
        color: $text;
    }
    AddCard > EditableText > ContentSwitcher > Static {
        text-align: center;
        color: $text-muted;
    }
    """

    def __init__(self, column: Node, board: Node):
        super().__init__()
        self.column = column
        self.board = board

    def compose(self) -> ComposeResult:
        yield EditableText("", Static("+"), TextEditor(), placeholder="+")

    def on_click(self, event) -> None:
        if event.button == 3:
            event.stop()

    def on_editable_text_changed(self, event: EditableText.Changed) -> None:
        event.stop()
        if event.new_value:
            card_id, card = create_card(self.board, event.new_value, column=self.column)
            self.post_message(self.CardCreated(self.column, card_id, event.new_value))
        self.query_one(EditableText).value = ""
        self.focus()
