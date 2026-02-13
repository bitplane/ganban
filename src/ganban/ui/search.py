"""Autocomplete search input with dropdown suggestions."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container
from textual.events import DescendantBlur, Key
from textual.message import Message
from textual.widgets import Input, OptionList
from textual.widgets.option_list import Option


class SearchInput(Container):
    """Text input with a filterable dropdown of suggestions.

    Options are (label, value) tuples. The label is shown in the dropdown,
    the value is returned on selection. Free-text is always allowed.
    """

    class Submitted(Message):
        """Posted when the user submits a selection or free text."""

        def __init__(self, text: str, value: str | None) -> None:
            super().__init__()
            self.text = text
            self.value = value

    class Cancelled(Message):
        """Posted when the user cancels (double-escape)."""

        pass

    def __init__(
        self,
        options: list[tuple[str, str]],
        *,
        placeholder: str = "",
        value: str = "",
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._options = list(options)
        self._placeholder = placeholder
        self._initial_value = value
        self._dropdown_open = False

    def compose(self) -> ComposeResult:
        yield Input(placeholder=self._placeholder, value=self._initial_value)
        yield OptionList()

    def set_options(self, options: list[tuple[str, str]]) -> None:
        """Replace the option list."""
        self._options = list(options)
        query = self.query_one(Input).value
        self._filter_options(query)

    def _filter_options(self, query: str) -> None:
        """Update the dropdown to show options matching the query."""
        option_list = self.query_one(OptionList)
        option_list.clear_options()

        query_lower = query.lower()
        matches = [(label, value) for label, value in self._options if query_lower in label.lower()]

        if matches:
            for label, value in matches:
                option_list.add_option(Option(label, id=value))
            option_list.highlighted = 0
            self._show_dropdown()
        else:
            self._close_dropdown()

    def _show_dropdown(self) -> None:
        """Show the dropdown overlay."""
        option_list = self.query_one(OptionList)
        if option_list.option_count == 0:
            return
        option_list.add_class("-visible")
        self._dropdown_open = True

    def _close_dropdown(self) -> None:
        """Hide the dropdown overlay."""
        self.query_one(OptionList).remove_class("-visible")
        self._dropdown_open = False

    def _submit_highlighted(self) -> bool:
        """Submit the currently highlighted option. Returns True if one was highlighted."""
        option_list = self.query_one(OptionList)
        highlighted = option_list.highlighted
        if highlighted is not None:
            option = option_list.get_option_at_index(highlighted)
            text = str(option.prompt)
            value = option.id
            inp = self.query_one(Input)
            inp.value = text
            self._close_dropdown()
            self.post_message(self.Submitted(text, value))
            return True
        return False

    def on_input_changed(self, event: Input.Changed) -> None:
        """Filter dropdown on every keystroke."""
        self._filter_options(event.value)

    def _on_key(self, event: Key) -> None:
        """Intercept keys before they reach the Input."""
        if event.key == "down" and self._dropdown_open:
            event.prevent_default()
            event.stop()
            self.query_one(OptionList).action_cursor_down()
        elif event.key == "up" and self._dropdown_open:
            event.prevent_default()
            event.stop()
            self.query_one(OptionList).action_cursor_up()
        elif event.key == "enter":
            event.prevent_default()
            event.stop()
            if self._dropdown_open and self._submit_highlighted():
                return
            # Free-text submit
            text = self.query_one(Input).value
            self._close_dropdown()
            self.post_message(self.Submitted(text, None))
        elif event.key == "escape":
            event.prevent_default()
            event.stop()
            if self._dropdown_open:
                self._close_dropdown()
            else:
                self.post_message(self.Cancelled())

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle mouse click on a dropdown item."""
        event.stop()
        text = str(event.option.prompt)
        value = event.option.id
        inp = self.query_one(Input)
        inp.value = text
        self._close_dropdown()
        self.post_message(self.Submitted(text, value))

    def on_descendant_blur(self, event: DescendantBlur) -> None:
        """Close dropdown when focus leaves a child widget."""
        self.call_after_refresh(self._maybe_close_on_blur)

    def _maybe_close_on_blur(self) -> None:
        """Close dropdown if focus has truly left us."""
        if not self.is_attached:
            return
        focused = self.app.focused
        if focused is None or focused not in self.walk_children():
            self._close_dropdown()
