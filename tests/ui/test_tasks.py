"""Tests for the task list editor widget."""

import pytest
from textual.app import App, ComposeResult

from ganban.ui.confirm import ConfirmButton
from ganban.ui.edit.editable import EditableText
from ganban.ui.edit.section import SectionEditor
from ganban.ui.edit.tasks import TaskCheckbox, TaskRow, TasksEditor

from tests.ui.conftest import GANBAN_CSS_PATH


BODY_WITH_TASKS = "- [ ] first task\n" "- [x] second task\n" "- [ ] third task"


class TasksApp(App):
    """Minimal app for testing TasksEditor."""

    CSS_PATH = GANBAN_CSS_PATH

    def __init__(self, body=BODY_WITH_TASKS):
        super().__init__()
        self._body = body
        self.body_changes = []

    def compose(self) -> ComposeResult:
        yield TasksEditor("Tasks", self._body)

    def on_section_editor_body_changed(self, event: SectionEditor.BodyChanged) -> None:
        self.body_changes.append(event.new_value)


@pytest.mark.asyncio
async def test_tasks_render_as_rows():
    """Tasks render as individual TaskRow widgets."""
    app = TasksApp()
    async with app.run_test():
        rows = app.query(TaskRow)
        assert len(rows) == 3


@pytest.mark.asyncio
async def test_all_tasks_are_editable():
    """Every task has an EditableText widget (no ownership gating)."""
    app = TasksApp()
    async with app.run_test():
        rows = list(app.query(TaskRow))
        for row in rows:
            editable = row.query(EditableText)
            assert len(editable) == 1


@pytest.mark.asyncio
async def test_add_task_emits_body_changed():
    """Adding a task emits BodyChanged with the new body."""
    app = TasksApp()
    async with app.run_test() as pilot:
        add_input = app.query_one(".add-task", EditableText)
        add_input.focus()
        await pilot.pause()

        text_area = add_input.query_one("#edit")
        text_area.text = "new task"
        await pilot.press("enter")
        await pilot.pause()

        assert len(app.body_changes) == 1
        assert "- [ ] new task" in app.body_changes[0]


@pytest.mark.asyncio
async def test_delete_task_emits_body_changed():
    """Deleting a task emits BodyChanged without that task."""
    app = TasksApp(body="- [ ] only task")
    async with app.run_test() as pilot:
        row = app.query_one(TaskRow)
        delete_btn = row.query_one(".task-delete", ConfirmButton)
        msg = ConfirmButton.Confirmed()
        msg._sender = delete_btn
        delete_btn.post_message(msg)
        await pilot.pause()
        await pilot.pause()

        assert len(app.body_changes) == 1
        assert "only task" not in app.body_changes[0]


@pytest.mark.asyncio
async def test_toggle_checkbox_emits_body_changed():
    """Clicking a checkbox toggles the task state and emits BodyChanged."""
    app = TasksApp(body="- [ ] unchecked task")
    async with app.run_test() as pilot:
        checkbox = app.query_one(TaskCheckbox)
        msg = TaskCheckbox.Toggled()
        msg._sender = checkbox
        checkbox.checked = True
        checkbox.post_message(msg)
        await pilot.pause()
        await pilot.pause()

        assert len(app.body_changes) == 1
        assert "[x]" in app.body_changes[0]
        assert "unchecked task" in app.body_changes[0]


@pytest.mark.asyncio
async def test_no_tasks_shows_empty_list():
    """A body with no bullet list shows no task rows."""
    app = TasksApp(body="Just some text, no bullets")
    async with app.run_test():
        rows = app.query(TaskRow)
        assert len(rows) == 0
