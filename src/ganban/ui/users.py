"""Users editor for board meta."""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.events import Click
from textual.message import Message
from textual.widgets import Static

from ganban.model.node import Node
from ganban.ui.confirm import ConfirmButton
from ganban.ui.edit.editable import EditableText
from ganban.ui.edit.editors import TextEditor
from ganban.ui.edit.meta import rename_node_key
from ganban.ui.edit.viewers import TextViewer
from ganban.ui.emoji import EmojiButton
from ganban.ui.watcher import NodeWatcherMixin


class EmailTag(Horizontal):
    """A single email address row with edit and delete."""

    class ValueChanged(Message):
        def __init__(self, index: int, value: str) -> None:
            super().__init__()
            self.index = index
            self.value = value

    class DeleteRequested(Message):
        def __init__(self, index: int) -> None:
            super().__init__()
            self.index = index

    DEFAULT_CSS = """
    EmailTag {
        width: 100%;
        height: auto;
    }
    EmailTag .email-value {
        width: 1fr;
        height: auto;
    }
    EmailTag .email-delete {
        width: 2;
        height: 1;
        dock: right;
    }
    EmailTag .email-delete:hover {
        background: $primary-darken-2;
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
        yield Static("x", classes="email-delete")

    def on_editable_text_changed(self, event: EditableText.Changed) -> None:
        event.stop()
        self.email = event.new_value
        self.post_message(self.ValueChanged(self.index, event.new_value))

    def on_click(self, event: Click) -> None:
        widget, _ = self.app.get_widget_at(event.screen_x, event.screen_y)
        if isinstance(widget, Static) and "email-delete" in widget.classes:
            event.stop()
            self.post_message(self.DeleteRequested(self.index))


class AddEmailButton(Static):
    """Clickable '+' to add a new email address."""

    class EmailAdded(Message):
        pass

    DEFAULT_CSS = """
    AddEmailButton {
        width: 100%;
        height: 1;
        color: $text-muted;
    }
    AddEmailButton:hover {
        background: $primary-darken-2;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__("+", **kwargs)

    def on_click(self, event: Click) -> None:
        event.stop()
        self.post_message(self.EmailAdded())


class UserRow(Vertical):
    """A single user row with emoji, name, delete, and email list."""

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
        padding: 0 0 0 2;
    }
    UserRow > .user-header {
        width: 100%;
        height: auto;
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
        with Horizontal(classes="user-header"):
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
        self._emails[event.index] = event.value
        if event.index == 0:
            self._update_emoji_default()
        self.post_message(self.EmailsChanged(self.user_name, list(self._emails)))

    def on_email_tag_delete_requested(self, event: EmailTag.DeleteRequested) -> None:
        event.stop()
        del self._emails[event.index]
        tags = list(self.query(EmailTag))
        tags[event.index].remove()
        self._reindex_emails()
        self._update_emoji_default()
        self.post_message(self.EmailsChanged(self.user_name, list(self._emails)))

    def on_add_email_button_email_added(self, event: AddEmailButton.EmailAdded) -> None:
        event.stop()
        self._emails.append("")
        tag = EmailTag(len(self._emails) - 1, "")
        emails_container = self.query_one(".user-emails")
        self.app.call_later(emails_container.mount, tag, before=emails_container.query_one(AddEmailButton))
        self.post_message(self.EmailsChanged(self.user_name, list(self._emails)))


class AddUserRow(Static):
    """Clickable row to add a new user."""

    class UserAdded(Message):
        pass

    DEFAULT_CSS = """
    AddUserRow {
        width: 100%;
        height: 1;
        text-align: center;
        color: $text-muted;
        border: dashed $surface-lighten-2;
    }
    AddUserRow:hover {
        background: $primary-darken-2;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__("+ Add user", **kwargs)

    def on_click(self, event: Click) -> None:
        event.stop()
        self.post_message(self.UserAdded())


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

    def _unique_name(self, base: str = "New User") -> str:
        """Return a unique user name, appending ' 2', ' 3' etc if needed."""
        users = self.meta.users
        if users is None:
            return base
        existing = set(users.keys())
        if base not in existing:
            return base
        n = 2
        while f"{base} {n}" in existing:
            n += 1
        return f"{base} {n}"

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
            rename_node_key(users, event.old, event.new)

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

    def on_add_user_row_user_added(self, event: AddUserRow.UserAdded) -> None:
        event.stop()
        users = self._ensure_users()
        name = self._unique_name()
        with self.suppressing():
            setattr(users, name, {"emails": []})
        user_node = getattr(users, name)
        row = UserRow(name, user_node)
        self.mount(row, before=self.query_one(AddUserRow))
