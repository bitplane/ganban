"""Users editor for board meta."""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.message import Message
from textual.widgets import Static

from ganban.model.node import Node
from ganban.ui.confirm import ConfirmButton
from ganban.ui.edit.editable import EditableText
from ganban.ui.edit.editors import TextEditor
from ganban.ui.edit.viewers import TextViewer
from ganban.ui.emoji import EmojiButton
from ganban.ui.watcher import NodeWatcherMixin


class EmailTag(Container):
    """A single email address tag — clear to empty to delete."""

    class ValueChanged(Message):
        def __init__(self, index: int, value: str) -> None:
            super().__init__()
            self.index = index
            self.value = value

    DEFAULT_CSS = """
    EmailTag {
        width: 100%;
        height: auto;
    }
    EmailTag .email-value {
        width: 1fr;
        height: auto;
    }
    """

    def __init__(self, index: int, email: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.index = index
        self.email = email

    def compose(self) -> ComposeResult:
        yield EditableText(
            self.email,
            TextViewer(self.email or '""'),
            TextEditor(),
            classes="email-value",
        )

    def on_editable_text_changed(self, event: EditableText.Changed) -> None:
        event.stop()
        self.email = event.new_value
        self.post_message(self.ValueChanged(self.index, event.new_value))


class AddEmailButton(Static, can_focus=True):
    """EditableText with '+' to add a new email address."""

    BINDINGS = [
        ("space", "start_editing"),
        ("enter", "start_editing"),
    ]

    class EmailAdded(Message):
        def __init__(self, email: str) -> None:
            super().__init__()
            self.email = email

    DEFAULT_CSS = """
    AddEmailButton {
        width: 100%;
        height: auto;
        color: $text-muted;
    }
    AddEmailButton > EditableText > ContentSwitcher > Static {
        color: $text-muted;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

    def action_start_editing(self) -> None:
        self.query_one(EditableText)._start_edit()

    def compose(self) -> ComposeResult:
        yield EditableText("", Static("+"), TextEditor(), placeholder="+")

    def on_editable_text_changed(self, event: EditableText.Changed) -> None:
        event.stop()
        if event.new_value:
            self.post_message(self.EmailAdded(event.new_value))
        self.query_one(EditableText).value = ""
        self.focus()


class UserRow(Vertical):
    """A single user card with title bar and email list."""

    class NameRenamed(Message):
        def __init__(self, old: str, new: str) -> None:
            super().__init__()
            self.old = old
            self.new = new

    class EmojiChanged(Message):
        def __init__(self, name: str, emoji: str | None) -> None:
            super().__init__()
            self.name = name
            self.emoji = emoji

    class EmailsChanged(Message):
        def __init__(self, name: str, emails: list[str]) -> None:
            super().__init__()
            self.name = name
            self.emails = emails

    class DeleteRequested(Message):
        def __init__(self, name: str) -> None:
            super().__init__()
            self.name = name

    DEFAULT_CSS = """
    UserRow {
        width: 100%;
        height: auto;
        padding: 0 1;
        margin-bottom: 1;
        background: $surface;
    }
    UserRow > .user-title-bar {
        width: 100%;
        height: auto;
        background: $primary;
        padding: 0 1;
    }
    UserRow .user-emoji {
        width: 2;
        height: 1;
    }
    UserRow .user-name {
        width: 1fr;
        height: auto;
    }
    UserRow .user-delete {
        width: 2;
        height: 1;
        dock: right;
    }
    UserRow > .user-emails {
        width: 100%;
        height: auto;
        padding: 0 0 0 2;
    }
    """

    def __init__(self, user_name: str, user_node: Node, **kwargs) -> None:
        super().__init__(**kwargs)
        self.user_name = user_name
        self.user_node = user_node
        self._emails: list[str] = list(user_node.emails) if isinstance(user_node.emails, list) else []

    @property
    def _first_email(self) -> str | None:
        return self._emails[0] if self._emails else None

    def compose(self) -> ComposeResult:
        with Horizontal(classes="user-title-bar"):
            yield EmojiButton(self.user_node.emoji, email=self._first_email, classes="user-emoji")
            yield EditableText(
                self.user_name,
                TextViewer(self.user_name),
                TextEditor(),
                classes="user-name",
            )
            yield ConfirmButton(classes="user-delete")
        with Vertical(classes="user-emails"):
            for i, email in enumerate(self._emails):
                yield EmailTag(i, email)
            yield AddEmailButton()

    def _reindex_emails(self) -> None:
        for i, tag in enumerate(self.query(EmailTag)):
            tag.index = i

    def _update_emoji_default(self) -> None:
        self.query_one(EmojiButton).email = self._first_email

    def on_editable_text_changed(self, event: EditableText.Changed) -> None:
        event.stop()
        sender = event.control
        if "user-name" in sender.classes:
            old = self.user_name
            self.user_name = event.new_value
            self.post_message(self.NameRenamed(old, event.new_value))

    def on_emoji_button_emoji_selected(self, event: EmojiButton.EmojiSelected) -> None:
        event.stop()
        self.post_message(self.EmojiChanged(self.user_name, event.emoji))

    def on_confirm_button_confirmed(self, event: ConfirmButton.Confirmed) -> None:
        event.stop()
        self.post_message(self.DeleteRequested(self.user_name))

    def on_email_tag_value_changed(self, event: EmailTag.ValueChanged) -> None:
        event.stop()
        if event.value:
            self._emails[event.index] = event.value
        else:
            del self._emails[event.index]
            tags = list(self.query(EmailTag))
            tags[event.index].remove()
            self._reindex_emails()
        self._update_emoji_default()
        self.post_message(self.EmailsChanged(self.user_name, list(self._emails)))

    def on_add_email_button_email_added(self, event: AddEmailButton.EmailAdded) -> None:
        event.stop()
        self._emails.append(event.email)
        tag = EmailTag(len(self._emails) - 1, event.email)
        emails_container = self.query_one(".user-emails")
        self.app.call_later(emails_container.mount, tag, before=emails_container.query_one(AddEmailButton))
        self.post_message(self.EmailsChanged(self.user_name, list(self._emails)))


class AddUserRow(Static, can_focus=True):
    """EditableText with '+' to add a new user."""

    BINDINGS = [
        ("space", "start_editing"),
        ("enter", "start_editing"),
    ]

    class UserCreated(Message):
        def __init__(self, name: str) -> None:
            super().__init__()
            self.name = name

    DEFAULT_CSS = """
    AddUserRow {
        width: 100%;
        height: auto;
        padding: 0 1;
        margin-bottom: 1;
        border: dashed $surface-lighten-2;
    }
    AddUserRow:focus {
        background: $primary;
        color: $text;
    }
    AddUserRow > EditableText > ContentSwitcher > Static {
        text-align: center;
        color: $text-muted;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

    def action_start_editing(self) -> None:
        self.query_one(EditableText)._start_edit()

    def compose(self) -> ComposeResult:
        yield EditableText("", Static("+"), TextEditor(), placeholder="+")

    def on_editable_text_changed(self, event: EditableText.Changed) -> None:
        event.stop()
        if event.new_value:
            self.post_message(self.UserCreated(event.new_value))
        self.query_one(EditableText).value = ""
        self.focus()


class UsersEditor(NodeWatcherMixin, Container):
    """Editor for board.meta.users -- a dict of display name -> user info."""

    DEFAULT_CSS = """
    UsersEditor {
        width: 100%;
        height: 1fr;
        overflow-y: auto;
    }
    """

    def __init__(self, meta: Node, **kwargs) -> None:
        self._init_watcher()
        super().__init__(**kwargs)
        self.meta = meta

    def _ensure_users(self) -> Node:
        """Create meta.users = {} if missing, return the users node."""
        if self.meta.users is None:
            self.meta.users = {}
        return self.meta.users

    def compose(self) -> ComposeResult:
        users = self.meta.users
        if users is not None:
            for name, user_node in users.items():
                yield UserRow(name, user_node)
        yield AddUserRow()

    def on_mount(self) -> None:
        self.node_watch(self.meta, "users", self._on_users_changed)

    def _on_users_changed(self, source_node: Any, key: str, old: Any, new: Any) -> None:
        self.call_later(self.recompose)

    def on_user_row_name_renamed(self, event: UserRow.NameRenamed) -> None:
        event.stop()
        users = self._ensure_users()
        with self.suppressing():
            users.rename_key(event.old, event.new)

    def on_user_row_emoji_changed(self, event: UserRow.EmojiChanged) -> None:
        event.stop()
        users = self._ensure_users()
        user = getattr(users, event.name)
        with self.suppressing():
            user.emoji = event.emoji

    def on_user_row_emails_changed(self, event: UserRow.EmailsChanged) -> None:
        event.stop()
        users = self._ensure_users()
        user = getattr(users, event.name)
        with self.suppressing():
            user.emails = event.emails

    def on_user_row_delete_requested(self, event: UserRow.DeleteRequested) -> None:
        event.stop()
        users = self._ensure_users()
        with self.suppressing():
            setattr(users, event.name, None)
        for row in self.query(UserRow):
            if row.user_name == event.name:
                row.remove()
                break

    def on_add_user_row_user_created(self, event: AddUserRow.UserCreated) -> None:
        event.stop()
        users = self._ensure_users()
        name = event.name
        with self.suppressing():
            setattr(users, name, {"emails": []})
        user_node = getattr(users, name)
        row = UserRow(name, user_node)
        self.mount(row, before=self.query_one(AddUserRow))
