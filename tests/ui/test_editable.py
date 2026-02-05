"""Tests for EditableText widget."""

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Button, Static

from ganban.ui.edit import EditableText, TextEditor


class EditableTextApp(App):
    """Test app with an EditableText."""

    def __init__(self, initial_value: str = "test value"):
        super().__init__()
        self.initial_value = initial_value
        self.changes: list[tuple[str, str]] = []

    def compose(self) -> ComposeResult:
        # Button first so it gets auto-focused, not the EditableText
        yield Button("focus target", id="focus-target")
        yield EditableText(
            self.initial_value,
            Static(self.initial_value),
            TextEditor(),
            id="editable",
        )

    def on_editable_text_changed(self, event: EditableText.Changed) -> None:
        self.changes.append((event.old_value, event.new_value))


@pytest.fixture
def app():
    return EditableTextApp()


@pytest.mark.asyncio
async def test_initial_state_shows_value(app):
    """EditableText shows its value as text initially."""
    async with app.run_test():
        editable = app.query_one("#editable", EditableText)
        assert editable.value == "test value"
        view = editable.query_one("#view")
        assert view.display is True


@pytest.mark.asyncio
async def test_focus_enters_edit_mode(app):
    """Focusing the widget enters edit mode."""
    async with app.run_test() as pilot:
        editable = app.query_one("#editable", EditableText)
        editable.focus()
        await pilot.pause()
        assert editable.query_one("#edit").display is True
        assert editable.query_one("#view").display is False


@pytest.mark.asyncio
async def test_blur_exits_edit_mode_and_saves(app):
    """Blurring the editor exits edit mode and saves changes."""
    async with app.run_test() as pilot:
        editable = app.query_one("#editable", EditableText)
        target = app.query_one("#focus-target", Button)

        editable.focus()
        await pilot.pause()

        editor = editable.query_one("#edit")
        editor.select_all()
        await pilot.press("n", "e", "w")
        await pilot.pause()

        target.focus()
        await pilot.pause()

        assert editable.query_one("#view").display is True
        assert editable.value == "new"
        assert app.changes == [("test value", "new")]


@pytest.mark.asyncio
async def test_escape_cancels_edit(app):
    """Escape key cancels editing without saving."""
    async with app.run_test() as pilot:
        editable = app.query_one("#editable", EditableText)

        editable.focus()
        await pilot.pause()

        editor = editable.query_one("#edit")
        editor.select_all()
        await pilot.press("x", "y", "z")
        await pilot.pause()

        await pilot.press("escape")
        await pilot.pause()

        assert editable.query_one("#view").display is True
        assert editable.value == "test value"
        assert app.changes == []


class EscapeTrackingApp(App):
    """Test app that tracks if escape was handled at app level."""

    BINDINGS = [("escape", "handle_escape", "Escape")]

    def __init__(self):
        super().__init__()
        self.escape_handled = False

    def compose(self) -> ComposeResult:
        yield Button("focus target", id="focus-target")
        yield EditableText("test", Static("test"), TextEditor(), id="editable")

    def action_handle_escape(self) -> None:
        self.escape_handled = True


@pytest.mark.asyncio
async def test_escape_while_editing_does_not_bubble():
    """Escape while editing should not bubble to parent bindings."""
    app = EscapeTrackingApp()
    async with app.run_test() as pilot:
        editable = app.query_one("#editable", EditableText)
        editable.focus()
        await pilot.pause()

        await pilot.press("escape")
        await pilot.pause()

        assert app.escape_handled is False  # Escape was stopped
        assert editable._editing is False  # But edit was canceled


@pytest.mark.asyncio
async def test_enter_saves_and_exits(app):
    """Enter key saves changes and exits edit mode."""
    async with app.run_test() as pilot:
        editable = app.query_one("#editable", EditableText)

        editable.focus()
        await pilot.pause()

        editor = editable.query_one("#edit")
        editor.select_all()
        await pilot.press("h", "e", "l", "l", "o")
        await pilot.pause()

        await pilot.press("enter")
        await pilot.pause()

        assert editable.query_one("#view").display is True
        assert editable.value == "hello"
        assert app.changes == [("test value", "hello")]


@pytest.mark.asyncio
async def test_tab_navigation_enters_edit_mode(app):
    """Tab navigation into the widget enters edit mode."""
    async with app.run_test() as pilot:
        editable = app.query_one("#editable", EditableText)

        # Button is already focused, tab to EditableText
        await pilot.press("tab")
        await pilot.pause()

        assert editable.query_one("#edit").display is True


@pytest.mark.asyncio
async def test_unchanged_value_no_event(app):
    """No Changed event if value wasn't modified."""
    async with app.run_test() as pilot:
        editable = app.query_one("#editable", EditableText)
        target = app.query_one("#focus-target", Button)

        editable.focus()
        await pilot.pause()

        target.focus()
        await pilot.pause()

        assert app.changes == []


@pytest.mark.asyncio
async def test_whitespace_normalization(app):
    """Whitespace is normalized (newlines become spaces, trimmed)."""
    async with app.run_test() as pilot:
        editable = app.query_one("#editable", EditableText)

        editable.focus()
        await pilot.pause()

        editor = editable.query_one("#edit")
        editor.select_all()
        await pilot.press("a", " ", " ", "b")
        await pilot.press("enter")
        await pilot.pause()

        assert editable.value == "a b"


@pytest.mark.asyncio
async def test_programmatic_value_change_emits_event():
    """Setting value programmatically emits Changed event."""
    app = EditableTextApp("original")
    async with app.run_test() as pilot:
        editable = app.query_one("#editable", EditableText)

        editable.value = "programmatic"
        await pilot.pause()

        assert editable.value == "programmatic"
        assert app.changes == [("original", "programmatic")]


@pytest.mark.asyncio
async def test_programmatic_same_value_no_event():
    """Setting same value programmatically doesn't emit event."""
    app = EditableTextApp("same")
    async with app.run_test() as pilot:
        editable = app.query_one("#editable", EditableText)

        editable.value = "same"
        await pilot.pause()

        assert app.changes == []


@pytest.mark.asyncio
async def test_click_enters_edit_mode(app):
    """Clicking the widget enters edit mode."""
    async with app.run_test() as pilot:
        editable = app.query_one("#editable", EditableText)

        await pilot.click(editable)
        await pilot.pause()

        assert editable.query_one("#edit").display is True
        assert editable.query_one("#view").display is False


class PlaceholderApp(App):
    """Test app with placeholder EditableText."""

    def compose(self) -> ComposeResult:
        yield Button("focus target", id="focus-target")
        yield EditableText("", Static("+"), TextEditor(), placeholder="+", id="editable")


@pytest.mark.asyncio
async def test_placeholder_shows_when_empty():
    """Placeholder is displayed when value is empty."""
    app = PlaceholderApp()
    async with app.run_test():
        editable = app.query_one("#editable", EditableText)
        viewer = editable.query_one("#view Static", Static)
        assert editable.value == ""
        assert str(viewer.render()) == "+"


@pytest.mark.asyncio
async def test_placeholder_editor_starts_empty():
    """Editor starts with empty value, not the placeholder."""
    app = PlaceholderApp()
    async with app.run_test() as pilot:
        editable = app.query_one("#editable", EditableText)
        editable.focus()
        await pilot.pause()

        editor = editable.query_one("#edit", TextEditor)
        assert editor.text == ""


@pytest.mark.asyncio
async def test_setting_value_while_editing_updates_editor(app):
    """Setting value programmatically while editing updates the editor text."""
    async with app.run_test() as pilot:
        editable = app.query_one("#editable", EditableText)
        editable.focus()
        await pilot.pause()

        editor = editable.query_one("#edit", TextEditor)
        assert editor.text == "test value"

        editable.value = "external update"
        await pilot.pause()

        assert editor.text == "external update"
        assert editable.value == "external update"


@pytest.mark.asyncio
async def test_start_edit_while_editing_is_noop(app):
    """Calling _start_edit when already editing does nothing."""
    async with app.run_test() as pilot:
        editable = app.query_one("#editable", EditableText)
        editable.focus()
        await pilot.pause()

        assert editable._editing is True
        editor = editable.query_one("#edit", TextEditor)
        editor.text = "modified"

        # Try to start editing again
        editable._start_edit()
        await pilot.pause()

        # Should still be editing with the same text (not reset)
        assert editable._editing is True
        assert editor.text == "modified"


@pytest.mark.asyncio
async def test_stop_edit_when_not_editing_is_noop(app):
    """Calling _stop_edit when not editing does nothing."""
    async with app.run_test() as pilot:
        editable = app.query_one("#editable", EditableText)

        assert editable._editing is False
        original_value = editable.value

        # Try to stop editing when not editing
        editable._stop_edit(save=True, value="should not save")
        await pilot.pause()

        # Should still not be editing and value unchanged
        assert editable._editing is False
        assert editable.value == original_value


@pytest.mark.asyncio
async def test_tab_in_shift_tab_out_tab_back_in(app):
    """Tab in, shift+tab out, tab back in, type, tab out - text should save."""
    async with app.run_test() as pilot:
        editable = app.query_one("#editable", EditableText)

        # Tab into editor
        await pilot.press("tab")
        await pilot.pause()
        assert editable._editing is True

        # Shift+tab out (blur saves)
        await pilot.press("shift+tab")
        await pilot.pause()
        assert editable._editing is False

        # Tab back in
        await pilot.press("tab")
        await pilot.pause()
        assert editable._editing is True

        # Type something
        editor = editable.query_one("#edit", TextEditor)
        editor.select_all()
        await pilot.press("n", "e", "w")
        await pilot.pause()

        # Tab out (blur saves)
        await pilot.press("tab")
        await pilot.pause()

        assert editable.value == "new"


@pytest.mark.asyncio
async def test_tab_in_escape_out_shift_tab_tab_back_in(app):
    """Tab in, escape out, shift+tab, tab back in, type, tab out - text should save."""
    async with app.run_test() as pilot:
        editable = app.query_one("#editable", EditableText)

        # Tab into editor
        await pilot.press("tab")
        await pilot.pause()
        assert editable._editing is True

        # Escape out (cancels, doesn't save)
        await pilot.press("escape")
        await pilot.pause()
        assert editable._editing is False

        # Shift+tab to focus target
        await pilot.press("shift+tab")
        await pilot.pause()

        # Tab back in
        await pilot.press("tab")
        await pilot.pause()
        assert editable._editing is True

        # Type something
        editor = editable.query_one("#edit", TextEditor)
        editor.select_all()
        await pilot.press("n", "e", "w")
        await pilot.pause()

        # Tab out (blur saves)
        await pilot.press("tab")
        await pilot.pause()

        assert editable.value == "new"
