"""Card detail modal for viewing and editing card content."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.events import Click
from textual.screen import ModalScreen

from ganban.models import Card
from ganban.ui.widgets import SectionEditor


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
        padding: 1 1;
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

    #main-section {
        height: 100%;
    }

    #sections-scroll {
        width: 100%;
        height: 100%;
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
                yield SectionEditor(
                    self.card.content.title,
                    self.card.content.body,
                    id="main-section",
                )

            with Vertical(id="detail-right"):
                with VerticalScroll(id="sections-scroll"):
                    for heading in self.card.content.sections:
                        yield SectionEditor(
                            heading,
                            self.card.content.sections[heading],
                            classes="subsection",
                        )

    def on_section_editor_heading_changed(self, event: SectionEditor.HeadingChanged) -> None:
        """Update card when a heading changes."""
        event.stop()
        editor = event.control
        if editor.id == "main-section":
            self.card.content.title = event.new_value
        else:
            # Rename section key
            content = self.card.content.sections.pop(event.old_value, "")
            self.card.content.sections[event.new_value] = content

    def on_section_editor_body_changed(self, event: SectionEditor.BodyChanged) -> None:
        """Update card when a body changes."""
        event.stop()
        editor = event.control
        if editor.id == "main-section":
            self.card.content.body = event.new_value
        else:
            self.card.content.sections[editor.heading] = event.new_value

    def on_click(self, event: Click) -> None:
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
