"""Tests for the viewer widgets."""

import pytest
from textual.app import App, ComposeResult

from ganban.ui.edit import TextViewer


class ViewerApp(App):
    """Minimal app for testing viewers."""

    def compose(self) -> ComposeResult:
        yield TextViewer("initial")


@pytest.mark.asyncio
async def test_text_viewer_update():
    """TextViewer.update() changes the displayed text."""
    app = ViewerApp()
    async with app.run_test():
        viewer = app.query_one(TextViewer)
        assert viewer.content == "initial"
        viewer.update("new")
        assert viewer.content == "new"
