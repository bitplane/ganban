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
