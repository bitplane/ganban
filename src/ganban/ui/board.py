"""Board screen showing kanban columns and cards."""

import asyncio
import time

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Static

from ganban.model.card import archive_card, move_card
from ganban.model.column import archive_column, move_column
from ganban.model.node import Node
from ganban.git import write_git_config_key
from ganban.model.writer import save_board
from ganban.parser import first_title
from ganban.sync import run_sync_cycle
from ganban.ui.card import AddCard, CardWidget
from ganban.ui.column import AddColumn, ColumnWidget
from ganban.ui.constants import ICON_BOARD, ICON_EDIT, ICON_SETTINGS
from ganban.ui.detail import BoardDetailModal
from ganban.ui.drag import ColumnPlaceholder, DropTarget
from ganban.ui.edit import EditableText, TextEditor
from ganban.ui.menu import ContextMenu, MenuItem, MenuSeparator
from ganban.ui.static import CloseButton
from ganban.ui.sync_widget import SyncWidget
from ganban.ui.watcher import NodeWatcherMixin


class BoardScreen(NodeWatcherMixin, DropTarget, Screen):
    """Main board screen showing all columns."""

    BINDINGS = [
        Binding("escape", "cancel_drag", "Cancel drag", show=False),
        ("ctrl+s", "save", "Save"),
        ("ctrl+@", "context_menu", "Context menu"),
    ]

    def __init__(self, board: Node):
        self._init_watcher()
        super().__init__()
        self.board = board
        self._active_draggable = None
        self._column_placeholder: ColumnPlaceholder | None = None
        self._sync_task: asyncio.Task | None = None
        self._last_sync: float = time.monotonic()

        # Initialize transient sync status (not persisted)
        if not board.git:
            board.git = Node()
        board.git.sync = Node(status="idle")

    def compose(self) -> ComposeResult:
        title = first_title(self.board.sections)
        with Horizontal(id="board-header"):
            yield EditableText(title, Static(title), TextEditor(), id="board-title")
            yield Static(ICON_SETTINGS, id="board-settings")
            yield SyncWidget(self.board, id="sync-status")
            yield CloseButton()

        visible_columns = [c for c in self.board.columns if not c.hidden]

        with Horizontal(id="columns"):
            for column in visible_columns:
                yield ColumnWidget(column, self.board)
            yield AddColumn(self.board)

        yield Footer()

    def on_mount(self) -> None:
        self.node_watch(self.board, "sections", self._on_board_sections_changed)
        self.node_watch(self.board.git, "config", self._on_config_changed)
        self.call_after_refresh(self._focus_first_card)
        self.set_interval(1.0, self._sync_tick)

    def _focus_first_card(self) -> None:
        columns = list(self.query(ColumnWidget))
        for col in columns:
            focusable = [c for c in col.children if c.can_focus]
            if focusable:
                focusable[0].focus()
                return

    def _on_config_changed(self, node, key, old, new) -> None:
        """Persist changed config key to git config."""
        section = node._key
        if section and key != "*":
            write_git_config_key(self.board.repo_path, section, key, new)

    def _sync_tick(self) -> None:
        """Called every 1s. Starts a sync cycle if interval has elapsed."""
        sync = self.board.git.sync
        config = self.board.git.config.ganban
        if sync.status != "idle":
            return
        if not config.sync_local and not config.sync_remote:
            return
        now = time.monotonic()
        interval = config.sync_interval or 30
        if now - self._last_sync < interval:
            return
        self._last_sync = now
        self._sync_task = asyncio.create_task(run_sync_cycle(self.board))

    def _on_board_sections_changed(self, node, key, old, new) -> None:
        """Update board header when title changes."""
        keys = self.board.sections.keys()
        if not keys:
            return  # transient empty state during rename_first_key rebuild
        new_title = keys[0]
        header = self.query_one("#board-title", EditableText)
        if header.value != new_title:
            header.value = new_title

    # -- Thin delegation: screen routes mouse events to active draggable --

    def on_mouse_move(self, event) -> None:
        if self._active_draggable is not None:
            self._active_draggable._drag_move(event.screen_x, event.screen_y)

    def on_mouse_up(self, event) -> None:
        if self._active_draggable is not None:
            self._active_draggable._drag_finish(event.screen_x, event.screen_y)

    def action_cancel_drag(self) -> None:
        if self._active_draggable is not None:
            self._active_draggable._drag_cancel()

    # -- DropTarget: board accepting column drops --

    def drag_over(self, draggable, x: int, y: int) -> bool:
        if not isinstance(draggable, ColumnWidget):
            return False
        insert_before = self._calculate_column_insert_position(draggable, x)
        self._ensure_column_placeholder(insert_before)
        return True

    def drag_away(self, draggable) -> None:
        if self._column_placeholder and self._column_placeholder.parent is not None:
            self._column_placeholder.remove()
        self._column_placeholder = None

    def try_drop(self, draggable, x: int, y: int) -> bool:
        if not isinstance(draggable, ColumnWidget):
            return False

        insert_before = self._calculate_column_insert_position(draggable, x)
        new_index = self._calculate_column_model_position(draggable, insert_before)

        draggable.remove_class("dragging")
        draggable.styles.offset = (0, 0)

        if self._column_placeholder and self._column_placeholder.parent is not None:
            self._column_placeholder.remove()
        self._column_placeholder = None

        self._move_column_to_index(draggable, new_index)
        return True

    def _calculate_column_insert_position(self, draggable, screen_x: int) -> Static:
        columns_container = self.query_one("#columns", Horizontal)
        visible_columns = [c for c in columns_container.children if isinstance(c, ColumnWidget) and c is not draggable]
        add_column = columns_container.query_one(AddColumn)

        for col in visible_columns:
            col_mid_x = col.region.x + col.region.width // 2
            if screen_x < col_mid_x:
                return col
        return add_column

    def _ensure_column_placeholder(self, insert_before: Static) -> None:
        columns_container = self.query_one("#columns", Horizontal)

        if self._column_placeholder is None:
            self._column_placeholder = ColumnPlaceholder()
            columns_container.mount(self._column_placeholder, before=insert_before)
            return

        children = list(columns_container.children)
        placeholder_idx = children.index(self._column_placeholder)
        insert_idx = children.index(insert_before)
        if placeholder_idx + 1 != insert_idx:
            columns_container.move_child(self._column_placeholder, before=insert_before)

    def _calculate_column_model_position(self, draggable, insert_before: Static) -> int:
        columns_container = self.query_one("#columns", Horizontal)
        pos = 0
        for child in columns_container.children:
            if child is insert_before:
                break
            if isinstance(child, ColumnWidget) and child is not draggable:
                pos += 1
        return pos

    # -- Existing board behavior --

    def on_editable_text_changed(self, event: EditableText.Changed) -> None:
        """Update board title when header is edited."""
        header = self.query_one("#board-title", EditableText)
        if event.control is header:
            event.stop()
            self.board.sections.rename_first_key(event.new_value)

    def on_click(self, event) -> None:
        """Handle clicks on board header area."""
        settings = self.query_one("#board-settings", Static)
        if settings.region.contains(event.screen_x, event.screen_y):
            event.stop()
            self.app.push_screen(BoardDetailModal(self.board))
            return
        if event.button != 3:
            return
        header = self.query_one("#board-title", EditableText)
        if header.region.contains(event.screen_x, event.screen_y):
            event.stop()
            self.show_context_menu(event.screen_x, event.screen_y)

    def show_context_menu(self, x: int | None = None, y: int | None = None) -> None:
        if x is None or y is None:
            region = self.query_one("#board-title", EditableText).region
            x = region.x + region.width // 2
            y = region.y + region.height // 2
        title = first_title(self.board.sections)
        items = [
            MenuItem(f"{ICON_BOARD} {title}", disabled=True),
            MenuSeparator(),
            MenuItem(f"{ICON_EDIT} Edit", "edit"),
        ]
        self.app.push_screen(ContextMenu(items, x, y), self._on_header_menu_closed)

    def _on_header_menu_closed(self, item: MenuItem | None) -> None:
        """Handle board header context menu selection."""
        if item and item.item_id == "edit":
            self.app.push_screen(BoardDetailModal(self.board))

    def action_context_menu(self) -> None:
        """Show context menu for the focused widget."""
        focused = self.focused
        if focused is None:
            return
        region = focused.region
        x = region.x + region.width // 2
        y = region.y + region.height // 2
        widget = focused
        while widget is not None:
            if hasattr(widget, "show_context_menu"):
                widget.show_context_menu(x, y)
                return
            widget = widget.parent

    async def action_close(self) -> None:
        """Close the board (quit the app)."""
        await self.app.run_action("quit")

    def action_save(self) -> None:
        """Save the board to git."""
        new_commit = save_board(self.board)
        self.board.commit = new_commit
        self.notify("Saved")

    def on_card_widget_move_requested(self, event: CardWidget.MoveRequested) -> None:
        """Handle card move request."""
        event.stop()
        card = event.card
        col_name = event.target_column

        target_col = next((c for c in self.board.columns if first_title(c.sections) == col_name), None)
        if not target_col:
            return

        move_card(self.board, card.card_id, target_col)

    def on_card_widget_archive_requested(self, event: CardWidget.ArchiveRequested) -> None:
        """Handle card archive request."""
        event.stop()
        archive_card(self.board, event.card.card_id)

    def on_add_card_card_created(self, event: AddCard.CardCreated) -> None:
        """Handle new card creation — commit immediately for timestamp."""
        event.stop()
        new_commit = save_board(self.board, message=f"Add card: {event.title}")
        self.board.commit = new_commit
        self._last_sync = time.monotonic()

    def on_add_column_column_created(self, event: AddColumn.ColumnCreated) -> None:
        """Handle new column creation."""
        event.stop()
        columns_container = self.query_one("#columns", Horizontal)
        add_widget = columns_container.query_one(AddColumn)
        new_widget = ColumnWidget(event.column, self.board)
        columns_container.mount(new_widget, before=add_widget)

    def _move_column_to_index(self, col_widget: ColumnWidget, new_index: int) -> None:
        """Move column to new position in both model and UI."""
        move_column(self.board, col_widget.column, new_index)
        self._sync_column_order()

    def _sync_column_order(self) -> None:
        """Reorder column widgets to match model order."""
        columns_container = self.query_one("#columns", Horizontal)
        add_column = columns_container.query_one(AddColumn)
        widgets_by_column = {id(cw.column): cw for cw in self.query(ColumnWidget)}

        insert_before = add_column
        for column in reversed(list(self.board.columns)):
            if id(column) not in widgets_by_column:
                continue  # skip hidden columns
            widget = widgets_by_column[id(column)]
            columns_container.move_child(widget, before=insert_before)
            insert_before = widget

    def on_column_widget_move_requested(self, event: ColumnWidget.MoveRequested) -> None:
        """Handle column move request."""
        event.stop()
        col_widget = event.column_widget
        direction = event.direction

        all_cols = list(self.board.columns)
        current_index = next(i for i, c in enumerate(all_cols) if c is col_widget.column)
        new_index = current_index + direction

        if new_index < 0 or new_index >= len(all_cols):
            return

        self._move_column_to_index(col_widget, new_index)

    def on_column_widget_archive_requested(self, event: ColumnWidget.ArchiveRequested) -> None:
        """Handle column archive request."""
        event.stop()
        col_widget = event.column_widget
        archive_column(self.board, col_widget.column.order)
        col_widget.remove()
