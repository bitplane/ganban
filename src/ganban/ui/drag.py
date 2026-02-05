"""Drag-and-drop infrastructure for ganban UI."""

from textual.geometry import Offset
from textual.message import Message
from textual.widget import Widget


class DragStarted(Message):
    """Posted when any draggable widget starts being dragged."""

    def __init__(self, widget: Widget, mouse_offset: Offset) -> None:
        super().__init__()
        self.widget = widget
        self.mouse_offset = mouse_offset

    @property
    def control(self) -> Widget:
        """The widget being dragged."""
        return self.widget


class DraggableMixin:
    """Mixin for widgets that can be dragged.

    Subclasses should:
    - Call _init_draggable() in __init__
    - Implement draggable_drag_started() to post appropriate messages
    - Implement draggable_clicked() for click-without-drag behavior
    - Optionally override DRAG_THRESHOLD and HORIZONTAL_ONLY
    """

    DRAG_THRESHOLD = 2
    HORIZONTAL_ONLY = False

    def _init_draggable(self) -> None:
        self._drag_start_pos: Offset | None = None

    def on_mouse_down(self, event) -> None:
        if event.button != 1:  # Only handle left click for drag
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
            self.draggable_drag_started(self._drag_start_pos)
            self._drag_start_pos = None

    def on_mouse_up(self, event) -> None:
        event.stop()
        event.prevent_default()
        self.release_mouse()
        if self._drag_start_pos is not None:
            self.draggable_clicked(Offset(event.x, event.y))
        self._drag_start_pos = None

    def draggable_drag_started(self, mouse_pos: Offset) -> None:
        """Called when drag threshold is exceeded. Override to post messages."""
        raise NotImplementedError

    def draggable_clicked(self, click_pos: Offset) -> None:
        """Called when mouse released without dragging. Override for click behavior."""
        raise NotImplementedError
