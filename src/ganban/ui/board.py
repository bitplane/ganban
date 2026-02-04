"""Board screen showing kanban columns and tickets."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.geometry import Offset
from textual.message import Message
from textual.screen import Screen
from textual.widgets import Static

from ganban.models import Board, Column, TicketLink
from ganban.writer import create_column, create_ticket
from ganban.ui.widgets import EditableLabel


class DropPlaceholder(Static):
    """Placeholder showing where a dragged card will drop."""

    DEFAULT_CSS = """
    DropPlaceholder {
        width: 100%;
        height: 3;
        margin-bottom: 1;
        border: dashed $primary;
        background: $surface-darken-1;
    }
    """


class ColumnPlaceholder(Static):
    """Placeholder showing where a dragged column will drop."""

    DEFAULT_CSS = """
    ColumnPlaceholder {
        width: 1fr;
        min-width: 20;
        max-width: 25;
        height: 100%;
        border: dashed $primary;
        background: $surface-darken-1;
    }
    """


class DragOverlay(Static):
    """Floating overlay showing the card being dragged."""

    DEFAULT_CSS = """
    DragOverlay {
        layer: overlay;
        width: 22;
        height: auto;
        padding: 0 1;
        border: solid $primary;
        background: $surface;
    }
    """

    def __init__(self, title: str):
        super().__init__(title)


class TicketCard(Static):
    """A single ticket card in a column."""

    DEFAULT_CSS = """
    TicketCard {
        width: 100%;
        height: auto;
        padding: 0 1;
        margin-bottom: 1;
        border: solid $primary-lighten-2;
        background: $surface;
    }
    TicketCard:hover {
        border: solid $primary;
    }
    TicketCard.dragging {
        display: none;
    }
    """

    class DragStart(Message):
        """Posted when a card drag begins."""

        def __init__(self, card: "TicketCard", mouse_offset: Offset) -> None:
            super().__init__()
            self.card = card
            self.mouse_offset = mouse_offset

    def __init__(self, link: TicketLink, title: str):
        super().__init__()
        self.link = link
        self.title = title
        self._drag_start_pos: Offset | None = None

    def compose(self) -> ComposeResult:
        yield EditableLabel(self.title or self.link.slug, click_to_edit=False)

    def on_mouse_down(self, event) -> None:
        event.stop()
        event.prevent_default()
        self._drag_start_pos = Offset(event.screen_x, event.screen_y)
        self.capture_mouse()

    def on_mouse_move(self, event) -> None:
        if self._drag_start_pos is None:
            return
        event.stop()
        event.prevent_default()
        # Start drag if moved more than 2 cells
        dx = abs(event.screen_x - self._drag_start_pos.x)
        dy = abs(event.screen_y - self._drag_start_pos.y)
        if dx > 2 or dy > 2:
            self.release_mouse()  # BoardScreen will capture instead
            self.post_message(self.DragStart(self, self._drag_start_pos))
            self._drag_start_pos = None

    def on_mouse_up(self, event) -> None:
        event.stop()
        event.prevent_default()
        self.release_mouse()
        # If drag never started, treat as click - start editing
        if self._drag_start_pos is not None:
            self.query_one(EditableLabel).start_editing()
        self._drag_start_pos = None


class AddTicketWidget(Static):
    """Widget to add a new ticket to a column."""

    DEFAULT_CSS = """
    AddTicketWidget {
        width: 100%;
        height: auto;
        padding: 0 1;
        margin-bottom: 1;
        border: dashed $surface-lighten-2;
    }
    AddTicketWidget > EditableLabel > Static {
        text-align: center;
        color: $text-muted;
    }
    """

    def __init__(self, column: Column, board: Board):
        super().__init__()
        self.column = column
        self.board = board

    def compose(self) -> ComposeResult:
        yield EditableLabel("+", click_to_edit=False)

    def on_click(self) -> None:
        self.query_one(EditableLabel).start_editing(text="")

    def on_editable_label_changed(self, event: EditableLabel.Changed) -> None:
        event.stop()
        if event.new_value and event.new_value != "+":
            ticket = create_ticket(self.board, event.new_value, column=self.column)
            link = self.column.links[-1]  # create_ticket adds link to end
            card = TicketCard(link, ticket.content.title)
            self.parent.mount(card, before=self)
        self.query_one(EditableLabel).value = "+"


class ColumnHeader(Static):
    """Draggable column header."""

    DEFAULT_CSS = """
    ColumnHeader {
        width: 100%;
        height: auto;
    }
    ColumnHeader > Static {
        width: 100%;
        text-align: center;
        text-style: bold;
    }
    """

    class DragStart(Message):
        """Posted when a column header drag begins."""

        def __init__(self, header: "ColumnHeader", mouse_offset: Offset) -> None:
            super().__init__()
            self.header = header
            self.mouse_offset = mouse_offset

    def __init__(self, column_name: str):
        super().__init__()
        self.column_name = column_name
        self._drag_start_pos: Offset | None = None

    def compose(self) -> ComposeResult:
        yield EditableLabel(self.column_name)

    def on_mouse_down(self, event) -> None:
        event.stop()
        event.prevent_default()
        self._drag_start_pos = Offset(event.screen_x, event.screen_y)
        self.capture_mouse()

    def on_mouse_move(self, event) -> None:
        if self._drag_start_pos is None:
            return
        event.stop()
        event.prevent_default()
        # Start drag if moved more than 2 cells horizontally
        dx = abs(event.screen_x - self._drag_start_pos.x)
        if dx > 2:
            self.release_mouse()
            self.post_message(self.DragStart(self, self._drag_start_pos))
            self._drag_start_pos = None

    def on_mouse_up(self, event) -> None:
        event.stop()
        event.prevent_default()
        self.release_mouse()
        # If drag never started, treat as click - start editing
        if self._drag_start_pos is not None:
            self.query_one(EditableLabel).start_editing()
        self._drag_start_pos = None


class ColumnWidget(Vertical):
    """A single column on the board."""

    DEFAULT_CSS = """
    ColumnWidget {
        width: 1fr;
        height: 100%;
        min-width: 20;
        max-width: 25;
        padding: 0 1;
        border-right: tall $surface-lighten-1;
    }
    ColumnWidget.dragging {
        layer: overlay;
        border: solid $primary;
        opacity: 0.8;
    }
    .column-body {
        width: 100%;
        height: 1fr;
    }
    """

    class DragStart(Message):
        """Posted when a column drag begins."""

        def __init__(self, column_widget: "ColumnWidget", mouse_offset: Offset) -> None:
            super().__init__()
            self.column_widget = column_widget
            self.mouse_offset = mouse_offset

    def __init__(self, column: Column, board: Board):
        super().__init__()
        self.column = column
        self.board = board

    def compose(self) -> ComposeResult:
        yield ColumnHeader(self.column.name)
        with VerticalScroll(classes="column-body"):
            for link in self.column.links:
                ticket = self.board.tickets.get(link.ticket_id)
                title = ticket.content.title if ticket else link.slug
                yield TicketCard(link, title)
            yield AddTicketWidget(self.column, self.board)

    def on_column_header_drag_start(self, event: ColumnHeader.DragStart) -> None:
        """Bubble up as ColumnWidget.DragStart."""
        event.stop()
        self.post_message(self.DragStart(self, event.mouse_offset))

    def on_editable_label_changed(self, event: EditableLabel.Changed) -> None:
        """Update column name when header is edited."""
        event.stop()
        if event.new_value:
            self.column.name = event.new_value


class AddColumnWidget(Vertical):
    """Widget to add a new column."""

    DEFAULT_CSS = """
    AddColumnWidget {
        width: 1fr;
        height: 100%;
        min-width: 20;
        max-width: 25;
        padding: 0 1;
    }
    AddColumnWidget .column-header > Static {
        text-align: center;
        text-style: bold;
    }
    """

    def __init__(self, board: Board):
        super().__init__()
        self.board = board

    def compose(self) -> ComposeResult:
        yield EditableLabel("+", click_to_edit=False, classes="column-header")

    def on_click(self) -> None:
        self.query_one(EditableLabel).start_editing(text="")

    def on_editable_label_changed(self, event: EditableLabel.Changed) -> None:
        event.stop()
        if event.new_value and event.new_value != "+":
            new_column = create_column(self.board, event.new_value)
            new_widget = ColumnWidget(new_column, self.board)
            self.parent.mount(new_widget, before=self)
        label = self.query_one(EditableLabel)
        label.value = "+"


class BoardScreen(Screen):
    """Main board screen showing all columns."""

    BINDINGS = [("escape", "cancel_drag", "Cancel drag")]

    DEFAULT_CSS = """
    BoardScreen {
        width: 100%;
        height: 100%;
        layout: vertical;
        layers: base overlay;
    }
    #board-header {
        width: 100%;
        height: auto;
        background: $primary;
    }
    #board-header > Static {
        width: 100%;
        text-align: center;
        text-style: bold;
    }
    #columns {
        width: 100%;
        height: 1fr;
        overflow-x: auto;
    }
    """

    def __init__(self, board: Board):
        super().__init__()
        self.board = board
        # Card drag state
        self._dragging: TicketCard | None = None
        self._drag_overlay: DragOverlay | None = None
        self._placeholder: DropPlaceholder | None = None
        self._drag_offset: Offset = Offset(0, 0)
        self._target_scroll: VerticalScroll | None = None
        self._insert_before: Static | None = None
        # Column drag state
        self._dragging_column: ColumnWidget | None = None
        self._column_placeholder: ColumnPlaceholder | None = None
        self._column_insert_before: Static | None = None
        self._column_drag_offset: Offset = Offset(0, 0)

    def compose(self) -> ComposeResult:
        title = self.board.content.title or "ganban"
        yield EditableLabel(title, id="board-header")

        visible_columns = [c for c in self.board.columns if not c.hidden]

        with Horizontal(id="columns"):
            for column in visible_columns:
                yield ColumnWidget(column, self.board)
            yield AddColumnWidget(self.board)

    def on_ticket_card_drag_start(self, event: TicketCard.DragStart) -> None:
        """Handle the start of a card drag."""
        event.stop()
        self._dragging = event.card
        self._dragging.add_class("dragging")

        # Calculate offset from mouse to card top-left
        card_region = event.card.region
        self._drag_offset = Offset(
            event.mouse_offset.x - card_region.x,
            event.mouse_offset.y - card_region.y,
        )

        # Create overlay at current position
        self._drag_overlay = DragOverlay(event.card.title)
        self._drag_overlay.styles.offset = (card_region.x, card_region.y)
        self.mount(self._drag_overlay)

        # Create placeholder where card was
        self._placeholder = DropPlaceholder()
        event.card.parent.mount(self._placeholder, after=event.card)

        self.capture_mouse()

    def on_column_widget_drag_start(self, event: ColumnWidget.DragStart) -> None:
        """Handle the start of a column drag."""
        event.stop()
        self._dragging_column = event.column_widget
        self._dragging_column.add_class("dragging")

        # Calculate offset from mouse to column top-left
        col_region = event.column_widget.region
        self._column_drag_offset = Offset(
            event.mouse_offset.x - col_region.x,
            event.mouse_offset.y - col_region.y,
        )

        # Position the column absolutely (it's now on overlay layer via CSS)
        self._dragging_column.styles.offset = (col_region.x, col_region.y)

        # Create placeholder where column was
        columns_container = self.query_one("#columns", Horizontal)
        self._column_placeholder = ColumnPlaceholder()
        columns_container.mount(self._column_placeholder, after=event.column_widget)

        self.capture_mouse()

    def on_mouse_move(self, event) -> None:
        """Update drag overlay position."""
        # Handle column drag
        if self._dragging_column:
            new_x = event.screen_x - self._column_drag_offset.x
            new_y = event.screen_y - self._column_drag_offset.y
            self._dragging_column.styles.offset = (new_x, new_y)
            self._update_column_placeholder_position(event.screen_x)
            return

        # Handle card drag
        if not self._dragging or not self._drag_overlay:
            return

        # Move overlay to follow mouse
        new_x = event.screen_x - self._drag_offset.x
        new_y = event.screen_y - self._drag_offset.y
        self._drag_overlay.styles.offset = (new_x, new_y)

        # Find which column we're over and update placeholder position
        self._update_placeholder_position(event.screen_x, event.screen_y)

    def _update_placeholder_position(self, screen_x: int, screen_y: int) -> None:
        """Move placeholder to show where card will drop."""
        if not self._placeholder:
            return

        # Find nearest column by horizontal distance to cursor
        columns = list(self.query(ColumnWidget))
        if not columns:
            return

        def column_distance(col):
            region = col.region
            if screen_x < region.x:
                return region.x - screen_x
            if screen_x >= region.x + region.width:
                return screen_x - (region.x + region.width - 1)
            return 0  # Cursor is inside column

        column_widget = min(columns, key=column_distance)
        scroll = column_widget.query_one(VerticalScroll)
        add_widget = scroll.query_one(AddTicketWidget)

        # Get visible cards (excluding the one being dragged)
        visible_cards = [c for c in scroll.children if isinstance(c, TicketCard) and c is not self._dragging]

        # Find insert position based on y coordinate
        insert_before = add_widget  # Default: insert at end
        for card in visible_cards:
            card_mid_y = card.region.y + card.region.height // 2
            if screen_y < card_mid_y:
                insert_before = card
                break

        # Store drop target state (independent of placeholder DOM)
        self._target_scroll = scroll
        self._insert_before = insert_before

        # Only move placeholder if it needs to move
        if self._placeholder.parent is scroll:
            # Check if already in correct position
            children = list(scroll.children)
            placeholder_idx = children.index(self._placeholder)
            insert_idx = children.index(insert_before)
            if placeholder_idx + 1 == insert_idx:
                return  # Already in correct position
            scroll.move_child(self._placeholder, before=insert_before)
        else:
            # Moving to different column - mount handles reparenting
            if self._placeholder.parent is not None:
                self._placeholder.remove()

            scroll.mount(self._placeholder, before=insert_before)

    def _update_column_placeholder_position(self, screen_x: int) -> None:
        """Move column placeholder to show where column will drop."""
        if not self._column_placeholder:
            return

        columns_container = self.query_one("#columns", Horizontal)

        # Get visible columns (excluding the one being dragged)
        visible_columns = [
            c for c in columns_container.children if isinstance(c, ColumnWidget) and c is not self._dragging_column
        ]

        if not visible_columns:
            return

        # Find insert position based on x coordinate (compare to column midpoints)
        add_column = columns_container.query_one(AddColumnWidget)
        insert_before = add_column  # Default: insert at end (before AddColumnWidget)

        for col in visible_columns:
            col_mid_x = col.region.x + col.region.width // 2
            if screen_x < col_mid_x:
                insert_before = col
                break

        self._column_insert_before = insert_before

        # Only move placeholder if it needs to move
        children = list(columns_container.children)
        placeholder_idx = children.index(self._column_placeholder)
        insert_idx = children.index(insert_before)
        if placeholder_idx + 1 == insert_idx:
            return  # Already in correct position
        columns_container.move_child(self._column_placeholder, before=insert_before)

    def on_mouse_up(self, event) -> None:
        """Complete the drag operation."""
        if self._dragging_column:
            self._finish_column_drag()
            return
        if self._dragging:
            self._finish_drag()

    def action_cancel_drag(self) -> None:
        """Cancel the current drag operation."""
        if self._dragging_column:
            self._cancel_column_drag()
        elif self._dragging:
            self._cancel_drag()

    def _finish_drag(self) -> None:
        """Finalize the drop - move card to placeholder position."""
        if not self._dragging or not self._target_scroll:
            self._cancel_drag()
            return

        self.release_mouse()

        card = self._dragging
        placeholder = self._placeholder
        overlay = self._drag_overlay
        target_scroll = self._target_scroll
        insert_before = self._insert_before

        target_column_widget = target_scroll.parent
        target_column = target_column_widget.column

        # Get source column
        source_column = None
        for col in self.board.columns:
            if any(link.ticket_id == card.link.ticket_id for link in col.links):
                source_column = col
                break

        # Move the link in the model
        if source_column and card.link in source_column.links:
            source_column.links.remove(card.link)

        # Find insert position in target column based on insert_before widget
        actual_pos = 0
        for c in target_scroll.children:
            if c is insert_before:
                break
            if isinstance(c, TicketCard) and c is not card:
                actual_pos += 1
        target_column.links.insert(actual_pos, card.link)

        # Clear state first
        self._dragging = None
        self._placeholder = None
        self._drag_overlay = None
        self._target_scroll = None
        self._insert_before = None

        # Remove old card and create fresh one at new position
        card.remove()
        new_card = TicketCard(card.link, card.title)
        target_scroll.mount(new_card, before=insert_before)

        # Cleanup overlay and placeholder
        if placeholder and placeholder.parent is not None:
            placeholder.remove()
        if overlay:
            overlay.remove()

    def _cancel_drag(self) -> None:
        """Cancel drag and restore card to original position."""
        if not self._dragging:
            return

        self.release_mouse()
        self._dragging.remove_class("dragging")

        if self._placeholder and self._placeholder.parent is not None:
            self._placeholder.remove()
        if self._drag_overlay:
            self._drag_overlay.remove()

        self._dragging = None
        self._placeholder = None
        self._drag_overlay = None
        self._target_scroll = None
        self._insert_before = None

    def _finish_column_drag(self) -> None:
        """Finalize the column drop - move column to placeholder position."""
        if not self._dragging_column:
            self._cancel_column_drag()
            return

        self.release_mouse()

        column_widget = self._dragging_column
        column = column_widget.column
        placeholder = self._column_placeholder
        insert_before = self._column_insert_before

        columns_container = self.query_one("#columns", Horizontal)

        # Calculate new index in board.columns
        new_index = 0
        for child in columns_container.children:
            if child is insert_before:
                break
            if isinstance(child, ColumnWidget) and child is not column_widget:
                new_index += 1

        # Reorder in model
        self.board.columns.remove(column)
        self.board.columns.insert(new_index, column)

        # Reassign order values
        for i, col in enumerate(self.board.columns):
            col.order = str(i + 1)

        # Clear state
        self._dragging_column = None
        self._column_placeholder = None
        self._column_insert_before = None

        # Reset column styles and move to new position
        column_widget.remove_class("dragging")
        column_widget.styles.offset = (0, 0)
        columns_container.move_child(column_widget, before=insert_before)

        # Cleanup placeholder
        if placeholder and placeholder.parent is not None:
            placeholder.remove()

    def _cancel_column_drag(self) -> None:
        """Cancel column drag and restore to original position."""
        if not self._dragging_column:
            return

        self.release_mouse()
        self._dragging_column.remove_class("dragging")
        self._dragging_column.styles.offset = (0, 0)

        if self._column_placeholder and self._column_placeholder.parent is not None:
            self._column_placeholder.remove()

        self._dragging_column = None
        self._column_placeholder = None
        self._column_insert_before = None
