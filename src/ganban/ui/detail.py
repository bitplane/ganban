"""Card detail modal for viewing and editing card content."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Collapsible, Markdown

from ganban.models import Card
from ganban.ui.widgets import EditableLabel


class CardDetailModal(ModalScreen[None]):
    """Modal screen showing full card details."""

    DEFAULT_CSS = """
    CardDetailModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.6);
    }

    #detail-container {
        width: 80%;
        height: 80%;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }

    #detail-left {
        width: 2fr;
        height: 100%;
        padding-right: 1;
    }

    #detail-right {
        width: 1fr;
        height: 100%;
        border-left: tall $surface-lighten-1;
        padding-left: 1;
    }

    #card-title {
        width: 100%;
        height: auto;
        text-style: bold;
        padding-bottom: 1;
    }

    #card-title > Static {
        text-style: bold;
    }

    #card-body {
        width: 100%;
        height: 1fr;
    }

    #card-body Markdown {
        padding: 0;
    }

    #sections-scroll {
        width: 100%;
        height: 100%;
    }

    .section-collapsible {
        width: 100%;
        margin-bottom: 1;
    }
    """

    BINDINGS = [
        ("escape", "close", "Close"),
        ("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self, card: Card) -> None:
        super().__init__()
        self.card = card

    def compose(self) -> ComposeResult:
        with Horizontal(id="detail-container"):
            with Vertical(id="detail-left"):
                yield EditableLabel(
                    self.card.content.title,
                    click_to_edit=True,
                    id="card-title",
                )
                with VerticalScroll(id="card-body"):
                    yield Markdown(self.card.content.body)

            with Vertical(id="detail-right"):
                with VerticalScroll(id="sections-scroll"):
                    for heading, content in self.card.content.sections.items():
                        with Collapsible(title=heading, classes="section-collapsible"):
                            yield Markdown(content)

    def on_editable_label_changed(self, event: EditableLabel.Changed) -> None:
        """Update card title when edited."""
        event.stop()
        if event.new_value:
            self.card.content.title = event.new_value

    def on_click(self, event) -> None:
        """Dismiss modal when clicking outside the detail container."""
        container = self.query_one("#detail-container")
        if not container.region.contains(event.screen_x, event.screen_y):
            self.dismiss()

    def action_close(self) -> None:
        """Close the modal."""
        self.dismiss()

    def action_quit(self) -> None:
        """Quit the app."""
        self.app.exit()
