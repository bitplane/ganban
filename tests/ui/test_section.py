"""Tests for the section editor widget."""

import pytest
from textual.app import App, ComposeResult

from ganban.ui.edit import EditableText, SectionEditor


class SectionApp(App):
    """Minimal app for testing section editor."""

    def __init__(self):
        super().__init__()
        self.heading_control = None

    def compose(self) -> ComposeResult:
        yield SectionEditor("Notes", "content")

    def on_section_editor_heading_changed(self, event: SectionEditor.HeadingChanged) -> None:
        self.heading_control = event.control


@pytest.mark.asyncio
async def test_heading_changed_control_is_section():
    """HeadingChanged event's control property returns the SectionEditor."""
    app = SectionApp()
    async with app.run_test() as pilot:
        section = app.query_one(SectionEditor)
        heading = section.query_one(".section-heading", EditableText)
        heading.focus()
        await pilot.pause()

        text_area = heading.query_one("#edit")
        text_area.text = "Comments"

        await pilot.press("enter")
        await pilot.pause()

        assert app.heading_control is section
