"""Tests for the SearchInput widget."""

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Input, OptionList

from ganban.ui.search import SearchInput


SAMPLE_OPTIONS = [
    ("Alice", "alice@example.com"),
    ("Bob", "bob@example.com"),
    ("Charlie", "charlie@example.com"),
]


class SearchApp(App):
    """Minimal app for testing SearchInput."""

    CSS = """
    SearchInput > OptionList {
        max-height: 8;
        display: none;
    }
    SearchInput > OptionList.-visible {
        display: block;
    }
    """

    def __init__(self, options=None, **kwargs):
        super().__init__()
        self._options = options or SAMPLE_OPTIONS
        self._kwargs = kwargs
        self.submitted = []
        self.cancelled = False

    def compose(self) -> ComposeResult:
        yield SearchInput(self._options, **self._kwargs)
        yield Input(id="other")

    def on_search_input_submitted(self, event: SearchInput.Submitted) -> None:
        self.submitted.append((event.text, event.value))

    def on_search_input_cancelled(self, event: SearchInput.Cancelled) -> None:
        self.cancelled = True


@pytest.fixture
def app():
    return SearchApp()


def _option_list(app: App) -> OptionList:
    return app.query_one(SearchInput).query_one(OptionList)


def _input(app: App) -> Input:
    return app.query_one(SearchInput).query_one(Input)


@pytest.mark.asyncio
async def test_initial_state(app):
    """Input is empty and dropdown is hidden on mount."""
    async with app.run_test():
        assert _input(app).value == ""
        assert not _option_list(app).has_class("-visible")


@pytest.mark.asyncio
async def test_typing_shows_filtered_dropdown(app):
    """Typing filters and shows the dropdown."""
    async with app.run_test() as pilot:
        _input(app).focus()
        await pilot.press("a")
        ol = _option_list(app)
        assert ol.has_class("-visible")
        assert ol.option_count == 2  # Alice, Charlie


@pytest.mark.asyncio
async def test_case_insensitive_filtering(app):
    """Filtering is case-insensitive substring match."""
    async with app.run_test() as pilot:
        _input(app).focus()
        await pilot.press("B", "O", "B")
        ol = _option_list(app)
        assert ol.has_class("-visible")
        assert ol.option_count == 1


@pytest.mark.asyncio
async def test_arrow_down_navigates_highlight(app):
    """Arrow down moves the OptionList highlight."""
    async with app.run_test() as pilot:
        _input(app).focus()
        await pilot.press("a")  # show dropdown (Alice, Charlie)
        ol = _option_list(app)
        assert ol.highlighted is not None
        initial = ol.highlighted
        await pilot.press("down")
        assert ol.highlighted != initial


@pytest.mark.asyncio
async def test_arrow_up_navigates_highlight(app):
    """Arrow up moves the OptionList highlight."""
    async with app.run_test() as pilot:
        _input(app).focus()
        await pilot.press("a")
        ol = _option_list(app)
        await pilot.press("down")
        moved = ol.highlighted
        await pilot.press("up")
        assert ol.highlighted != moved


@pytest.mark.asyncio
async def test_enter_submits_highlighted_item(app):
    """Enter submits the highlighted option's text and value."""
    async with app.run_test() as pilot:
        _input(app).focus()
        await pilot.press("b", "o", "b")
        ol = _option_list(app)
        assert ol.option_count == 1
        await pilot.press("enter")
        assert len(app.submitted) == 1
        text, value = app.submitted[0]
        assert text == "Bob"
        assert value == "bob@example.com"


@pytest.mark.asyncio
async def test_enter_submits_free_text(app):
    """Enter with no highlight submits raw text with value=None."""
    async with app.run_test() as pilot:
        _input(app).focus()
        # Type something that matches nothing
        for ch in "zzz":
            await pilot.press(ch)
        await pilot.press("enter")
        assert len(app.submitted) == 1
        text, value = app.submitted[0]
        assert text == "zzz"
        assert value is None


@pytest.mark.asyncio
async def test_option_selected_submits(app):
    """OptionList selection (click/enter) submits the item."""
    async with app.run_test() as pilot:
        _input(app).focus()
        await pilot.press("b", "o", "b")
        ol = _option_list(app)
        assert ol.has_class("-visible")
        # Simulate what a click does: select the highlighted option
        ol.action_select()
        await pilot.pause()
        assert len(app.submitted) == 1
        assert app.submitted[0][1] == "bob@example.com"


@pytest.mark.asyncio
async def test_escape_closes_dropdown(app):
    """First escape closes the dropdown without cancelling."""
    async with app.run_test() as pilot:
        _input(app).focus()
        await pilot.press("a")
        assert _option_list(app).has_class("-visible")
        await pilot.press("escape")
        assert not _option_list(app).has_class("-visible")
        assert not app.cancelled


@pytest.mark.asyncio
async def test_escape_twice_posts_cancelled(app):
    """Second escape (dropdown already closed) posts Cancelled."""
    async with app.run_test() as pilot:
        _input(app).focus()
        await pilot.press("a")
        await pilot.press("escape")  # close dropdown
        await pilot.press("escape")  # cancel
        assert app.cancelled


@pytest.mark.asyncio
async def test_blur_closes_dropdown(app):
    """Losing focus closes the dropdown silently."""
    async with app.run_test() as pilot:
        inp = _input(app)
        inp.focus()
        await pilot.press("a")
        assert _option_list(app).has_class("-visible")
        # Focus something outside the SearchInput
        app.query_one("#other", Input).focus()
        await pilot.pause()
        await pilot.pause()
        assert not _option_list(app).has_class("-visible")
        assert not app.cancelled
        assert len(app.submitted) == 0


@pytest.mark.asyncio
async def test_no_matches_hides_dropdown(app):
    """When no options match, the dropdown is hidden."""
    async with app.run_test() as pilot:
        _input(app).focus()
        for ch in "zzz":
            await pilot.press(ch)
        assert not _option_list(app).has_class("-visible")


@pytest.mark.asyncio
async def test_empty_input_shows_all_options(app):
    """Empty query shows all options."""
    async with app.run_test() as pilot:
        _input(app).focus()
        await pilot.press("a")
        assert _option_list(app).has_class("-visible")
        await pilot.press("backspace")
        ol = _option_list(app)
        assert ol.has_class("-visible")
        assert ol.option_count == len(SAMPLE_OPTIONS)


@pytest.mark.asyncio
async def test_set_options_updates_list(app):
    """set_options() replaces options and re-filters."""
    async with app.run_test() as pilot:
        _input(app).focus()
        await pilot.press("a")
        search = app.query_one(SearchInput)
        search.set_options([("Zara", "zara@example.com")])
        ol = _option_list(app)
        # "a" matches "Zara"
        assert ol.option_count == 1
        opt = ol.get_option_at_index(0)
        assert str(opt.prompt) == "Zara"
        assert opt.id == "zara@example.com"


@pytest.mark.asyncio
async def test_placeholder():
    """Placeholder text is passed through to Input."""
    app = SearchApp(placeholder="Search...")
    async with app.run_test():
        assert _input(app).placeholder == "Search..."


@pytest.mark.asyncio
async def test_initial_value():
    """Initial value is passed through to Input."""
    app = SearchApp(value="Bob")
    async with app.run_test():
        assert _input(app).value == "Bob"
