"""Card widgets for ganban UI."""

from textual.app import ComposeResult
from textual.geometry import Offset
from textual.message import Message
from textual.widgets import Static

from ganban.models import Board, CardLink, Column
from ganban.writer import create_card
from ganban.ui.detail import CardDetailModal
from ganban.ui.drag import DraggableMixin, DragStarted
from ganban.ui.menu import ContextMenu, MenuItem, MenuSeparator
from ganban.ui.edit import EditableText, TextEditor
from ganban.ui.static import PlainStatic


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
        border: solid $primary-lighten-2;
        background: $surface;
    }
    CardWidget:hover {
        border: solid $primary;
    }
    CardWidget.dragging {
        display: none;
    }
    """

    def __init__(self, link: CardLink, title: str, board: Board):
        Static.__init__(self)
        self._init_draggable()
        self.link = link
        self.title = title
        self.board = board

    def compose(self) -> ComposeResult:
        yield PlainStatic(self.title or self.link.slug)

    def draggable_drag_started(self, mouse_pos: Offset) -> None:
        self.post_message(DragStarted(self, mouse_pos))

    def draggable_clicked(self, click_pos: Offset) -> None:
        card = self.board.cards.get(self.link.card_id)
        if card:
            self.app.push_screen(CardDetailModal(card), self._on_modal_closed)

    def _on_modal_closed(self, result: None) -> None:
        card = self.board.cards.get(self.link.card_id)
        if card:
            self.title = card.content.title
            self.query_one(PlainStatic).update(self.title or self.link.slug)

    def _find_column(self) -> Column | None:
        """Find the column containing this card's link."""
        for col in self.board.columns:
            if self.link in col.links:
                return col
        return None

    def on_click(self, event) -> None:
        if event.button == 3:  # Right click
            event.stop()
            current_col = self._find_column()

            # Build move submenu from visible columns (current disabled)
            move_items = [
                MenuItem(col.name, f"move:{col.name}", disabled=(col is current_col))
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
                card = self.board.cards.get(self.link.card_id)
                if card:
                    self.app.push_screen(CardDetailModal(card), self._on_modal_closed)
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

        def __init__(self, column: Column, card_link: CardLink, title: str):
            super().__init__()
            self.column = column
            self.card_link = card_link
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

    def __init__(self, column: Column, board: Board):
        super().__init__()
        self.column = column
        self.board = board

    def compose(self) -> ComposeResult:
        yield EditableText("", Static("+"), TextEditor(), placeholder="+")

    def on_editable_text_changed(self, event: EditableText.Changed) -> None:
        event.stop()
        if event.new_value:
            new_card = create_card(self.board, event.new_value, column=self.column)
            link = self.column.links[-1]  # create_card adds link to end
            self.post_message(self.CardCreated(self.column, link, new_card.content.title))
        self.query_one(EditableText).value = ""
