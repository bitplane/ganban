"""Tests for the inline autocomplete completion system."""

import pytest
from textual.app import App, ComposeResult

from ganban.ui.edit.completion import CompletionDropdown, CompletionSource
from ganban.ui.edit.editors import MarkdownEditor


SAMPLE_USERS = [
    ("Alice <alice@x.com>", "[Alice](mailto:alice@x.com)"),
    ("Bob <bob@x.com>", "[Bob](mailto:bob@x.com)"),
]

SAMPLE_CARDS = [
    ("001 Fix login", "001"),
    ("002 Add tests", "002"),
    ("003 User profile", "003"),
]


class CompletionApp(App):
    """Minimal app for testing inline completion."""

    CSS = """
    CompletionDropdown {
        display: none;
        overlay: screen;
        max-height: 8;
        width: 30;
    }
    CompletionDropdown.-visible {
        display: block;
    }
    """

    def __init__(self, sources=None):
        super().__init__()
        self._sources = sources

    def compose(self) -> ComposeResult:
        yield MarkdownEditor(completion_sources=self._sources)


def _default_sources():
    return [
        CompletionSource("@", lambda: SAMPLE_USERS, replace_trigger=True),
        CompletionSource("#", lambda: SAMPLE_CARDS),
    ]


@pytest.fixture
def app():
    return CompletionApp(sources=_default_sources())


def _editor(app: App) -> MarkdownEditor:
    return app.query_one(MarkdownEditor)


def _dropdown(app: App) -> CompletionDropdown | None:
    results = app.query(CompletionDropdown)
    return results.first() if results else None


@pytest.mark.asyncio
async def test_trigger_at_start_of_line(app):
    """Typing @ at start of line opens the dropdown."""
    async with app.run_test() as pilot:
        _editor(app).focus()
        await pilot.press("@")
        await pilot.pause()
        dd = _dropdown(app)
        assert dd is not None
        assert dd.has_class("-visible")
        assert dd.option_count == len(SAMPLE_USERS)


@pytest.mark.asyncio
async def test_trigger_after_space(app):
    """Typing @ after a space opens the dropdown."""
    async with app.run_test() as pilot:
        ed = _editor(app)
        ed.focus()
        await pilot.press("h", "i", " ", "@")
        await pilot.pause()
        dd = _dropdown(app)
        assert dd is not None
        assert dd.has_class("-visible")


@pytest.mark.asyncio
async def test_trigger_mid_word_does_not_open(app):
    """Typing @ mid-word should NOT open the dropdown."""
    async with app.run_test() as pilot:
        ed = _editor(app)
        ed.focus()
        await pilot.press("h", "i", "@")
        await pilot.pause()
        dd = _dropdown(app)
        # Dropdown should not exist or not be visible
        assert dd is None or not dd.has_class("-visible")


@pytest.mark.asyncio
async def test_typing_filters_dropdown(app):
    """Typing after trigger filters the dropdown options."""
    async with app.run_test() as pilot:
        ed = _editor(app)
        ed.focus()
        await pilot.press("@")
        await pilot.pause()
        dd = _dropdown(app)
        assert dd.option_count == 2
        await pilot.press("a", "l")
        await pilot.pause()
        assert dd.option_count == 1  # Only "Alice"


@pytest.mark.asyncio
async def test_enter_selects_top_match(app):
    """Enter selects the highlighted match and inserts it."""
    async with app.run_test() as pilot:
        ed = _editor(app)
        ed.focus()
        await pilot.press("@", "b", "o")
        await pilot.pause()
        dd = _dropdown(app)
        assert dd.option_count == 1  # Bob
        await pilot.press("enter")
        await pilot.pause()
        assert "[Bob](mailto:bob@x.com)" in ed.text
        assert dd is not None and not dd.has_class("-visible")


@pytest.mark.asyncio
async def test_tab_selects_top_match(app):
    """Tab also selects the highlighted match."""
    async with app.run_test() as pilot:
        ed = _editor(app)
        ed.focus()
        await pilot.press("@", "b", "o")
        await pilot.pause()
        await pilot.press("tab")
        await pilot.pause()
        assert "[Bob](mailto:bob@x.com)" in ed.text


@pytest.mark.asyncio
async def test_arrow_keys_navigate(app):
    """Arrow keys navigate the dropdown."""
    async with app.run_test() as pilot:
        ed = _editor(app)
        ed.focus()
        await pilot.press("@")
        await pilot.pause()
        dd = _dropdown(app)
        assert dd.highlighted == 0
        await pilot.press("down")
        assert dd.highlighted == 1
        await pilot.press("up")
        assert dd.highlighted == 0


@pytest.mark.asyncio
async def test_escape_cancels(app):
    """Escape closes the dropdown without replacing text."""
    async with app.run_test() as pilot:
        ed = _editor(app)
        ed.focus()
        await pilot.press("@", "b")
        await pilot.pause()
        dd = _dropdown(app)
        assert dd.has_class("-visible")
        await pilot.press("escape")
        await pilot.pause()
        assert not dd.has_class("-visible")
        assert ed.text == "@b"


@pytest.mark.asyncio
async def test_space_cancels(app):
    """Space deactivates completion and leaves text as-is."""
    async with app.run_test() as pilot:
        ed = _editor(app)
        ed.focus()
        await pilot.press("@", "b")
        await pilot.pause()
        dd = _dropdown(app)
        assert dd.has_class("-visible")
        await pilot.press("space")
        await pilot.pause()
        assert not dd.has_class("-visible")
        assert "@b " in ed.text


@pytest.mark.asyncio
async def test_backspace_past_trigger_cancels(app):
    """Backspacing past the trigger position cancels completion."""
    async with app.run_test() as pilot:
        ed = _editor(app)
        ed.focus()
        await pilot.press("@")
        await pilot.pause()
        dd = _dropdown(app)
        assert dd.has_class("-visible")
        await pilot.press("backspace")
        await pilot.pause()
        await pilot.pause()
        assert not dd.has_class("-visible")


@pytest.mark.asyncio
async def test_fast_path_filter_and_select(app):
    """#user<Enter> filters by 'user' and selects top card match."""
    async with app.run_test() as pilot:
        ed = _editor(app)
        ed.focus()
        await pilot.press("#", "u", "s", "e", "r")
        await pilot.pause()
        dd = _dropdown(app)
        # "003 User profile" matches "user"
        assert dd.option_count == 1
        await pilot.press("enter")
        await pilot.pause()
        assert "#003" in ed.text


@pytest.mark.asyncio
async def test_ctrl_space_shows_all_sources(app):
    """Ctrl+Space merges all sources and shows dropdown."""
    async with app.run_test() as pilot:
        ed = _editor(app)
        ed.focus()
        await pilot.press("ctrl+space")
        await pilot.pause()
        dd = _dropdown(app)
        assert dd is not None
        assert dd.has_class("-visible")
        expected_count = len(SAMPLE_USERS) + len(SAMPLE_CARDS)
        assert dd.option_count == expected_count


@pytest.mark.asyncio
async def test_no_sources_no_completion():
    """With no sources, trigger chars are just normal text."""
    app = CompletionApp(sources=None)
    async with app.run_test() as pilot:
        ed = _editor(app)
        ed.focus()
        await pilot.press("@")
        await pilot.pause()
        dd = _dropdown(app)
        assert dd is None or not dd.has_class("-visible")
        assert ed.text == "@"


@pytest.mark.asyncio
async def test_blur_deactivates(app):
    """Losing focus deactivates the dropdown."""
    async with app.run_test() as pilot:
        ed = _editor(app)
        ed.focus()
        await pilot.press("@")
        await pilot.pause()
        dd = _dropdown(app)
        assert dd.has_class("-visible")
        ed.blur()
        await pilot.pause()
        assert not dd.has_class("-visible")


@pytest.mark.asyncio
async def test_hash_trigger(app):
    """# trigger opens card options."""
    async with app.run_test() as pilot:
        ed = _editor(app)
        ed.focus()
        await pilot.press("#")
        await pilot.pause()
        dd = _dropdown(app)
        assert dd is not None
        assert dd.has_class("-visible")
        assert dd.option_count == len(SAMPLE_CARDS)


@pytest.mark.asyncio
async def test_enter_with_arrow_selects_navigated(app):
    """Arrow down then Enter selects the second option."""
    async with app.run_test() as pilot:
        ed = _editor(app)
        ed.focus()
        await pilot.press("@")
        await pilot.pause()
        dd = _dropdown(app)
        assert dd.highlighted == 0
        await pilot.press("down")
        assert dd.highlighted == 1
        await pilot.press("enter")
        await pilot.pause()
        # Second user is Bob
        assert "[Bob](mailto:bob@x.com)" in ed.text
