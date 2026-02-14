"""Section editor widget."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.events import Click
from textual.message import Message
from textual.widgets import Static

from ganban.ui.confirm import ConfirmButton
from ganban.ui.edit.editable import EditableText
from ganban.ui.edit.editors import MarkdownEditor, TextEditor
from ganban.ui.edit.viewers import MarkdownViewer
from ganban.ui.menu import ContextMenu, MenuItem

if TYPE_CHECKING:
    from ganban.ui.edit.document import EditorType


class EditorSelectButton(Static):
    """Button that shows a context menu of available editor types."""

    class Selected(Message):
        """Emitted when an editor type is selected."""

        def __init__(self, editor_type: EditorType) -> None:
            super().__init__()
            self.editor_type = editor_type

    def __init__(self, editor_types: list[EditorType], current: EditorType, **kwargs) -> None:
        super().__init__(current.icon, **kwargs)
        self._editor_types = editor_types
        self._current = current

    def on_click(self, event: Click) -> None:
        event.stop()
        items = [MenuItem(f"{et.icon} {et.name}", item_id=et.name) for et in self._editor_types]
        region = self.region
        menu = ContextMenu(items, region.x, region.y + region.height)
        self.app.push_screen(menu, self._on_menu_closed)

    def _on_menu_closed(self, item: MenuItem | None) -> None:
        if item is None:
            return
        for et in self._editor_types:
            if et.name == item.item_id:
                self._current = et
                self.update(et.icon)
                self.post_message(self.Selected(et))
                return


class SectionEditor(Container):
    """Editor for a section with heading and markdown body."""

    class HeadingChanged(Message):
        """Emitted when the section heading changes."""

        def __init__(self, old_value: str, new_value: str) -> None:
            super().__init__()
            self.old_value = old_value
            self.new_value = new_value

        @property
        def control(self) -> SectionEditor:
            return self._sender

    class BodyChanged(Message):
        """Emitted when the section body changes."""

        def __init__(self, old_value: str, new_value: str) -> None:
            super().__init__()
            self.old_value = old_value
            self.new_value = new_value

        @property
        def control(self) -> SectionEditor:
            return self._sender

    class DeleteRequested(Message):
        """Emitted when the section delete is confirmed."""

        @property
        def control(self) -> SectionEditor:
            return self._sender

    class EditorTypeSelected(Message):
        """Emitted when the editor type is changed."""

        def __init__(self, editor_type: EditorType) -> None:
            super().__init__()
            self.editor_type = editor_type

        @property
        def control(self) -> SectionEditor:
            return self._sender

    def __init__(
        self,
        heading: str | None,
        body: str = "",
        parser_factory=None,
        editor_types: list[EditorType] | None = None,
        current_editor_type: EditorType | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._heading = heading
        self._body = body
        self._parser_factory = parser_factory
        self._editor_types = editor_types
        self._current_editor_type = current_editor_type

    @property
    def heading(self) -> str | None:
        return self._heading

    @property
    def body(self) -> str:
        return self._body

    def focus_body(self) -> None:
        """Focus the body editor."""
        self.query_one(".section-body", EditableText).focus()

    def _match_editor_type(self) -> EditorType | None:
        if self._current_editor_type:
            return self._current_editor_type
        if not self._editor_types:
            return None
        for et in self._editor_types:
            if et.pattern.search(self._heading or ""):
                return et
        return self._editor_types[0]

    def compose(self) -> ComposeResult:
        if self._heading is not None:
            with Horizontal(classes="section-heading-row"):
                yield EditableText(
                    self._heading,
                    Static(self._heading),
                    TextEditor(),
                    classes="section-heading",
                )
                current = self._match_editor_type()
                if current and self._editor_types:
                    yield EditorSelectButton(self._editor_types, current, classes="section-editor-select")
                yield ConfirmButton(classes="section-delete")
        yield EditableText(
            self._body,
            MarkdownViewer(self._body, parser_factory=self._parser_factory),
            MarkdownEditor(),
            classes="section-body",
            clean=False,
        )

    def on_confirm_button_confirmed(self, event: ConfirmButton.Confirmed) -> None:
        event.stop()
        self.post_message(self.DeleteRequested())

    def on_editor_select_button_selected(self, event: EditorSelectButton.Selected) -> None:
        event.stop()
        self.post_message(self.EditorTypeSelected(event.editor_type))

    def on_editable_text_changed(self, event: EditableText.Changed) -> None:
        event.stop()
        if "section-heading" in event.control.classes:
            self._heading = event.new_value
            self.post_message(self.HeadingChanged(event.old_value, event.new_value))
        else:
            self._body = event.new_value
            self.post_message(self.BodyChanged(event.old_value, event.new_value))
