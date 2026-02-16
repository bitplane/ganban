"""Inline autocomplete for editors.

Typing a trigger character (e.g. ``@`` or ``#``) after whitespace or at the
start of a line opens a floating dropdown that filters as you type.
Enter/Tab selects the top match, Space or Escape cancels.
Ctrl+Space shows all sources merged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from textual.widgets import OptionList
from textual.widgets.option_list import Option

if TYPE_CHECKING:
    from textual.events import Key


@dataclass
class CompletionSource:
    """A trigger character and a callable that returns completion options.

    The callable returns ``list[tuple[str, str]]`` where each tuple is
    ``(display_label, insert_value)``.

    If ``replace_trigger`` is True, the trigger character is removed on
    selection and only the value is inserted.
    """

    trigger: str
    options: Callable[[], list[tuple[str, str]]]
    replace_trigger: bool = False


class CompletionDropdown(OptionList):
    """Floating dropdown for completion results.

    Mounted once on the screen and shown/hidden as needed.  Uses
    ``overlay: screen`` CSS so it floats above all other widgets.
    """

    can_focus = False

    def filter(self, query: str, options: list[tuple[str, str]]) -> None:
        """Repopulate the list with options matching *query*."""
        self.clear_options()
        query_lower = query.lower()
        for label, value in options:
            if query_lower in label.lower():
                self.add_option(Option(label, id=value))
        if self.option_count:
            self.highlighted = 0

    def select_highlighted(self) -> tuple[str, str] | None:
        """Return ``(label, value)`` of the highlighted option, or None."""
        if self.highlighted is None:
            return None
        opt = self.get_option_at_index(self.highlighted)
        return str(opt.prompt), opt.id

    def show_at(self, x: int, y: int) -> None:
        """Position the dropdown and make it visible."""
        self.styles.offset = (x, y)
        self.add_class("-visible")

    def hide(self) -> None:
        """Hide the dropdown."""
        self.remove_class("-visible")


class CompletionMixin:
    """Mixin for BaseEditor subclasses that adds trigger-based completion.

    Must be listed *before* the editor base in the MRO so that ``_on_key``
    intercepts events before the editor handles them.

    Call ``_init_completion(sources)`` from ``__init__`` and
    ``_deactivate_completion()`` on blur.
    """

    def _init_completion(self, sources: list[CompletionSource] | None) -> None:
        self._completion_sources: list[CompletionSource] = sources or []
        self._completion_active = False
        self._completion_trigger: str = ""
        self._completion_trigger_col: int = 0
        self._completion_trigger_row: int = 0
        self._completion_options: list[tuple[str, str]] = []
        self._completion_dropdown: CompletionDropdown | None = None
        self._completion_needs_refilter = False
        self._completion_active_source: CompletionSource | None = None
        self._completion_trigger_screen_x: int = 0
        self._completion_trigger_screen_y: int = 0

    # -- activation / deactivation -----------------------------------------

    def _activate_completion(
        self,
        trigger: str,
        options: list[tuple[str, str]],
        source: CompletionSource | None = None,
    ) -> None:
        row, col = self.cursor_location  # type: ignore[attr-defined]
        self._completion_active = True
        self._completion_trigger = trigger
        self._completion_active_source = source
        # The trigger char has already been inserted, so col is *after* it.
        self._completion_trigger_col = col
        self._completion_trigger_row = row
        self._completion_options = options
        # Capture screen position of the trigger char (cursor is just after it)
        offset = self.cursor_screen_offset  # type: ignore[attr-defined]
        self._completion_trigger_screen_x = offset.x - 1  # back up to the trigger char
        self._completion_trigger_screen_y = offset.y
        dd = self._ensure_dropdown()
        dd.filter("", options)
        self._position_dropdown(dd)

    def _deactivate_completion(self) -> None:
        if not self._completion_active:
            return
        self._completion_active = False
        self._completion_needs_refilter = False
        self._completion_active_source = None
        if self._completion_dropdown is not None:
            self._completion_dropdown.hide()

    # -- dropdown management -----------------------------------------------

    def _find_editable_parent(self):
        """Walk up to the EditableText ancestor."""
        from ganban.ui.edit.editable import EditableText

        node = self.parent  # type: ignore[attr-defined]
        while node is not None:
            if isinstance(node, EditableText):
                return node
            node = node.parent
        return self.parent  # type: ignore[attr-defined]

    def _ensure_dropdown(self) -> CompletionDropdown:
        if self._completion_dropdown is not None:
            return self._completion_dropdown
        dd = CompletionDropdown()
        self._completion_dropdown = dd
        self._find_editable_parent().mount(dd)
        return dd

    def _position_dropdown(self, dd: CompletionDropdown) -> None:
        parent = self._find_editable_parent()
        # Dropdown's natural flow position is at the bottom of the parent.
        # Offset from there to just below the trigger character.
        natural_y = parent.region.y + parent.region.height
        natural_x = parent.region.x
        dd.show_at(
            self._completion_trigger_screen_x - natural_x,
            self._completion_trigger_screen_y + 1 - natural_y,
        )

    # -- query helpers -----------------------------------------------------

    def _completion_query(self) -> str:
        """Return text typed after the trigger char."""
        row, col = self.cursor_location  # type: ignore[attr-defined]
        if row != self._completion_trigger_row:
            return ""
        return self.document.get_line(row)[self._completion_trigger_col : col]  # type: ignore[attr-defined]

    def _refilter_from_document(self) -> None:
        """Validate trigger is still present and refilter the dropdown.

        Called from on_text_area_changed where cursor_location is reliable.
        """
        if not self._completion_active:
            return
        row = self._completion_trigger_row
        trigger_col = self._completion_trigger_col
        cur_row, cur_col = self.cursor_location  # type: ignore[attr-defined]

        # Cursor moved to a different row
        if cur_row != row:
            self._deactivate_completion()
            return

        # Cursor retreated past trigger position
        if cur_col < trigger_col:
            self._deactivate_completion()
            return

        line = self.document.get_line(row)  # type: ignore[attr-defined]

        # Trigger char deleted
        if self._completion_trigger and (
            trigger_col < 1 or trigger_col - 1 >= len(line) or line[trigger_col - 1] != self._completion_trigger
        ):
            self._deactivate_completion()
            return

        # Refilter with updated query
        query = line[trigger_col:cur_col]
        dd = self._completion_dropdown
        if dd is not None:
            dd.filter(query, self._completion_options)
            if dd.option_count == 0:
                dd.hide()
            else:
                self._position_dropdown(dd)

    # -- TextArea.Changed handler ------------------------------------------

    def on_text_area_changed(self, event) -> None:
        """React to text changes with reliable cursor position."""
        if self._completion_needs_refilter:
            self._completion_needs_refilter = False
            self._refilter_from_document()

    # -- selection ---------------------------------------------------------

    def _select_completion(self) -> None:
        dd = self._completion_dropdown
        if dd is None:
            return
        result = dd.select_highlighted()
        if result is None:
            self._deactivate_completion()
            return
        _, value = result
        source = self._completion_active_source
        trigger = self._completion_trigger
        row = self._completion_trigger_row
        # trigger char is at trigger_col - 1 (trigger_col is *after* it)
        start_col = self._completion_trigger_col - 1
        end = self.cursor_location  # type: ignore[attr-defined]
        prefix = "" if (source and source.replace_trigger) else trigger
        self.replace(  # type: ignore[attr-defined]
            f"{prefix}{value}",
            start=(row, start_col),
            end=end,
        )
        self._deactivate_completion()

    # -- key interception --------------------------------------------------

    async def _on_key(self, event: Key) -> None:
        if self._completion_active:
            await self._on_key_active(event)
        else:
            await self._on_key_inactive(event)

    async def _on_key_inactive(self, event: Key) -> None:
        """Check for trigger chars or Ctrl+Space."""
        if event.key == "ctrl+space" and self._completion_sources:
            # Merge all sources
            merged: list[tuple[str, str]] = []
            for src in self._completion_sources:
                merged.extend(src.options())
            if merged:
                self._activate_completion("", merged)
            return

        char = event.character
        if char and len(char) == 1:
            source = self._source_for_trigger(char)
            if source is not None:
                # Check if preceded by whitespace or start of line
                row, col = self.cursor_location  # type: ignore[attr-defined]
                if col == 0 or self.document.get_line(row)[col - 1] in (" ", "\t"):  # type: ignore[attr-defined]
                    # Let the char be inserted first
                    await super()._on_key(event)  # type: ignore[misc]
                    options = source.options()
                    if options:
                        self._activate_completion(char, options, source)
                    return

        await super()._on_key(event)  # type: ignore[misc]

    async def _on_key_active(self, event: Key) -> None:
        """Handle keys while completion is active."""
        key = event.key

        if key in ("up", "down"):
            event.prevent_default()
            event.stop()
            dd = self._completion_dropdown
            if dd is not None:
                if key == "up":
                    dd.action_cursor_up()
                else:
                    dd.action_cursor_down()
            return

        if key in ("enter", "tab"):
            event.prevent_default()
            event.stop()
            self._select_completion()
            return

        if key == "escape":
            event.prevent_default()
            event.stop()
            self._deactivate_completion()
            return

        if key == "space":
            self._deactivate_completion()
            await super()._on_key(event)  # type: ignore[misc]
            return

        if key == "backspace":
            self._completion_needs_refilter = True
            await super()._on_key(event)  # type: ignore[misc]
            return

        # Printable characters
        if event.character and event.is_printable:
            self._completion_needs_refilter = True
            await super()._on_key(event)  # type: ignore[misc]
            return

        # Non-printable (arrows, home, etc.) - deactivate and pass through
        self._deactivate_completion()
        await super()._on_key(event)  # type: ignore[misc]

    def _source_for_trigger(self, char: str) -> CompletionSource | None:
        """Find a source matching the given trigger character."""
        for src in self._completion_sources:
            if src.trigger == char:
                return src
        return None
