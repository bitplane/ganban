"""Drag-and-drop infrastructure for ganban UI.

Two mixins:
- DraggableMixin: on dragged widgets, owns the "flying" phase
- DropTarget: on containers, owns the "landing" phase
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.geometry import Offset, Region
from textual.widgets import Static

if TYPE_CHECKING:
    from textual.widget import Widget


class DropTarget:
    """Mixin for widgets that can accept drops.

    Returns False to ignore (bubbles to parent), True to consume.
    """

    def drag_over(self, draggable: DraggableMixin, x: int, y: int) -> bool:
        """Called while a draggable hovers over this target. Return True to accept."""
        return False

    def drag_away(self, draggable: DraggableMixin) -> None:
        """Called when a draggable leaves this target."""

    def try_drop(self, draggable: DraggableMixin, x: int, y: int) -> bool:
        """Called on mouse-up to attempt the drop. Return True if accepted."""
        return False

    def find_nearest(self, region: Region) -> "Widget | None":
        """Find the nearest child widget to the given region."""
        return None


class DraggableMixin:
    """Mixin for widgets that can be dragged.

    Subclasses should:
    - Call _init_draggable() in __init__
    - Implement draggable_make_ghost() to return the ghost widget
    - Implement draggable_clicked() for click-without-drag behavior
    - Optionally override DRAG_THRESHOLD and HORIZONTAL_ONLY
    """

    DRAG_THRESHOLD = 2
    HORIZONTAL_ONLY = False

    def _init_draggable(self) -> None:
        self._drag_start_pos: Offset | None = None
        self._dragging = False
        self._ghost: Widget | None = None
        self._drag_offset: Offset = Offset(0, 0)
        self._current_target: DropTarget | None = None

    @property
    def is_dragging(self) -> bool:
        return self._dragging

    def on_mouse_down(self, event) -> None:
        if event.button != 1:
            return
        event.stop()
        event.prevent_default()
        self._drag_start_pos = Offset(event.screen_x, event.screen_y)
        self.capture_mouse()

    def on_mouse_move(self, event) -> None:
        if self._drag_start_pos is None:
            return
        event.stop()
        event.prevent_default()
        dx = abs(event.screen_x - self._drag_start_pos.x)
        dy = abs(event.screen_y - self._drag_start_pos.y)
        threshold_exceeded = (
            dx > self.DRAG_THRESHOLD if self.HORIZONTAL_ONLY else (dx > self.DRAG_THRESHOLD or dy > self.DRAG_THRESHOLD)
        )
        if threshold_exceeded:
            self.release_mouse()
            mouse_pos = self._drag_start_pos
            self._drag_start_pos = None
            self._drag_start(mouse_pos)

    def on_mouse_up(self, event) -> None:
        event.stop()
        event.prevent_default()
        self.release_mouse()
        if self._drag_start_pos is not None:
            self._drag_start_pos = None
            self.draggable_clicked()

    def _drag_start(self, mouse_pos: Offset) -> None:
        """Begin drag: create ghost, add .dragging class, register on screen."""
        self._dragging = True
        self.add_class("dragging")
        self.screen.set_focus(None)

        region = self.region
        self._drag_offset = Offset(
            mouse_pos.x - region.x,
            mouse_pos.y - region.y,
        )

        self._ghost = self.draggable_make_ghost()

        if self._ghost is not self:
            self._ghost.styles.width = region.width
            self._ghost.styles.offset = (region.x, region.y)
            self.screen.mount(self._ghost)

        self.screen._active_draggable = self
        self.screen.capture_mouse()

    def _drag_move(self, x: int, y: int) -> None:
        """Called by screen on mouse move during drag."""
        self._reposition_ghost(x, y)
        self._update_drop_target(x, y)

    def _reposition_ghost(self, x: int, y: int) -> None:
        """Position the ghost widget. Override for scroll-relative positioning."""
        if self._ghost is None:
            return
        new_x = x - self._drag_offset.x
        new_y = y - self._drag_offset.y
        self._ghost.styles.offset = (new_x, new_y)

    def _update_drop_target(self, x: int, y: int) -> None:
        """Hit-test for DropTargets and call drag_over/drag_away."""
        new_target = self._find_drop_target(x, y)

        if new_target is self._current_target:
            # Same target, just update position
            if new_target is not None:
                new_target.drag_over(self, x, y)
            return

        if new_target is not None:
            # Switching to a new valid target
            if self._current_target is not None:
                self._current_target.drag_away(self)
            self._current_target = new_target
            new_target.drag_over(self, x, y)
        # If new_target is None, keep current (sticky placeholder behavior)

    def _drag_finish(self, x: int, y: int) -> None:
        """Called by screen on mouse-up. Try to drop, innermost-out."""
        self.screen.release_mouse()

        dropped = False
        for target in self._iter_drop_targets(x, y):
            if target.try_drop(self, x, y):
                dropped = True
                break

        if not dropped and self._current_target is not None:
            # Fallback: try the last hovered target
            dropped = self._current_target.try_drop(self, x, y)

        if not dropped:
            self._drag_cancel()
            return

        if self._current_target is not None:
            self._current_target = None
        self._drag_cleanup()

    def _drag_cancel(self) -> None:
        """Cancel drag: drag_away + cleanup."""
        self.screen.release_mouse()
        if self._current_target is not None:
            self._current_target.drag_away(self)
            self._current_target = None
        self.remove_class("dragging")
        self._drag_cleanup()

    def _drag_cleanup(self) -> None:
        """Remove ghost, clear state, deregister from screen."""
        if self._ghost is not None and self._ghost is not self:
            self._ghost.remove()
        self._ghost = None
        self._dragging = False
        self._drag_offset = Offset(0, 0)
        self.remove_class("dragging")
        if hasattr(self.screen, "_active_draggable"):
            self.screen._active_draggable = None

    def _find_drop_target(self, x: int, y: int) -> DropTarget | None:
        """Find the innermost DropTarget at screen position, skipping the ghost."""
        try:
            widgets = self.screen.get_widgets_at(x, y)
        except Exception:
            return None

        for widget, _region in widgets:
            # Skip ghost and its children
            if self._ghost is not None and self._ghost is not self:
                if widget is self._ghost or self._ghost in widget.ancestors:
                    continue
            # Walk ancestors for DropTarget
            candidate = widget
            while candidate is not None:
                if isinstance(candidate, DropTarget) and candidate is not self:
                    return candidate
                candidate = candidate.parent
        return None

    def _iter_drop_targets(self, x: int, y: int) -> list[DropTarget]:
        """Yield all DropTargets at position, innermost-out."""
        targets = []
        try:
            widgets = self.screen.get_widgets_at(x, y)
        except Exception:
            return targets

        seen = set()
        for widget, _region in widgets:
            if self._ghost is not None and self._ghost is not self:
                if widget is self._ghost or self._ghost in widget.ancestors:
                    continue
            candidate = widget
            while candidate is not None:
                if isinstance(candidate, DropTarget) and candidate is not self:
                    cid = id(candidate)
                    if cid not in seen:
                        seen.add(cid)
                        targets.append(candidate)
                candidate = candidate.parent
        return targets

    def draggable_make_ghost(self) -> Widget:
        """Create and return the ghost widget for dragging. Override in subclass."""
        raise NotImplementedError

    def draggable_clicked(self) -> None:
        """Called when mouse released without dragging. Override for click behavior."""
        raise NotImplementedError


class DragGhost(Static):
    """Floating overlay showing the card being dragged."""

    def __init__(self, card):
        super().__init__()
        self._card = card

    def compose(self):
        from ganban.ui.card import CardWidget

        yield CardWidget(self._card.card_id, self._card.board)

    def on_mount(self) -> None:
        from ganban.ui.card import CardWidget

        self.query_one(CardWidget).focus()


class CardPlaceholder(Static):
    """Placeholder showing where a dragged card will drop."""

    pass


class ColumnPlaceholder(Static):
    """Placeholder showing where a dragged column will drop."""

    pass
