"""Card widgets for ganban UI."""

from textual.app import ComposeResult
from textual.geometry import Offset
from textual.message import Message
from textual.widgets import Rule, Static

from ganban.model.node import Node
from ganban.model.writer import create_card
from ganban.parser import first_title
from ganban.ui.card_indicators import build_footer_text
from ganban.ui.detail import CardDetailModal
from ganban.ui.drag import DraggableMixin, DragStarted
from ganban.ui.menu import ContextMenu, MenuItem, MenuSeparator
from ganban.ui.edit import EditableText, TextEditor
from ganban.ui.static import PlainStatic


def _card_title(board: Node, card_id: str) -> str:
    """Get the display title for a card."""
    card = board.cards[card_id]
    if not card or not card.sections:
        return card_id
    return first_title(card.sections) or card_id


class CardWidget(DraggableMixin, Static):
    """A single card in a column."""

    class MoveRequested(Message):
        """Posted when card should be moved to another column."""

        def __init__(self, card: "CardWidget", target_column: str):
            super().__init__()
            self.card = card
            self.target_column = target_column

    class DeleteRequested(Message):
        """Posted when card should be deleted."""

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
        self._unwatch_sections = card.watch("sections", self._on_card_changed)
        self._unwatch_meta = card.watch("meta", self._on_card_changed)
        self._unwatch_users = self.board.meta.watch("users", self._on_card_changed) if self.board.meta else None
        self._refresh_indicators()

    def on_unmount(self) -> None:
        self._unwatch_sections()
        self._unwatch_meta()
        if self._unwatch_users:
            self._unwatch_users()

    def _on_card_changed(self, node, key, old, new) -> None:
        """Update card display when sections or meta change."""
        new_title = _card_title(self.board, self.card_id)
        if new_title != self.title:
            self.title = new_title
            self.query_one("#card-title", PlainStatic).update(self.title or self.card_id)
        self._refresh_indicators()

    def _refresh_indicators(self) -> None:
        """Update footer indicator text."""
        card = self.board.cards[self.card_id]
        footer_text = build_footer_text(card.sections, card.meta, self.board.meta)
        self.query_one("#card-footer", PlainStatic).update(footer_text)

    def draggable_drag_started(self, mouse_pos: Offset) -> None:
        self.post_message(DragStarted(self, mouse_pos))

    def draggable_clicked(self) -> None:
        card = self.board.cards[self.card_id]
        self.app.push_screen(CardDetailModal(card, self.board))

    def _find_column(self) -> Node | None:
        """Find the column containing this card."""
        for col in self.board.columns:
            if self.card_id in col.links:
                return col
        return None

    def on_click(self, event) -> None:
        if event.button == 3:  # Right click
            event.stop()
            current_col = self._find_column()

            # Build move submenu from visible columns (current disabled)
            move_items = [
                MenuItem(first_title(col.sections), f"move:{first_title(col.sections)}", disabled=(col is current_col))
                for col in self.board.columns
                if not col.hidden
            ]

            items = [
                MenuItem("Edit", "edit"),
                MenuItem("Move to", submenu=move_items),
            ]
            items.append(MenuSeparator())
            items.append(MenuItem("Delete", "delete"))

            menu = ContextMenu(items, event.screen_x, event.screen_y)
            self.app.push_screen(menu, self._on_menu_closed)

    def _on_menu_closed(self, item: MenuItem | None) -> None:
        if item is None:
            return
        match item.item_id:
            case "edit":
                card = self.board.cards[self.card_id]
                self.app.push_screen(CardDetailModal(card, self.board))
            case "delete":
                self._delete_card()
            case s if s and s.startswith("move:"):
                col_name = s[5:]
                self._move_to_column(col_name)

    def _delete_card(self) -> None:
        """Request deletion of this card."""
        self.post_message(self.DeleteRequested(self))

    def _move_to_column(self, col_name: str) -> None:
        """Request move to the named column."""
        self.post_message(self.MoveRequested(self, col_name))


class AddCard(Static):
    """Widget to add a new card to a column."""

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
