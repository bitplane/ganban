"""Load a ganban board from git tree."""

import re

from git import Repo
from git.objects import Blob, Tree

from ganban.models import Board, Column, MarkdownDoc, Ticket, TicketLink
from ganban.parser import parse_markdown

BRANCH_NAME = "ganban"


def load_board(repo_path: str, branch: str = BRANCH_NAME) -> Board:
    """Load a complete board from a git branch."""
    repo = Repo(repo_path)

    # Get the branch commit
    try:
        commit = repo.commit(branch)
    except Exception:
        raise ValueError(f"Branch '{branch}' not found in repository")

    tree = commit.tree

    board = Board(repo_path=repo_path, commit=commit.hexsha)

    # Load root index.md if present
    if "index.md" in tree:
        board.content = _load_markdown_doc(tree["index.md"])

    # Load all tickets from .all/
    if ".all" in tree:
        all_tree = tree[".all"]
        if isinstance(all_tree, Tree):
            board.tickets = _load_tickets(all_tree)

    # Load columns
    board.columns = _load_columns(tree, board.tickets)

    return board


def _load_markdown_doc(blob: Blob) -> MarkdownDoc:
    """Load and parse a markdown file from a git blob."""
    text = blob.data_stream.read().decode("utf-8")
    return parse_markdown(text)


def _load_tickets(all_tree: Tree) -> dict[str, Ticket]:
    """Load all tickets from the .all/ tree."""
    tickets = {}

    for item in all_tree:
        if not isinstance(item, Blob):
            continue
        if not item.name.endswith(".md"):
            continue

        ticket_id = item.name[:-3]  # Remove .md
        ticket = Ticket(
            id=ticket_id,
            path=f".all/{item.name}",
            content=_load_markdown_doc(item),
        )
        tickets[ticket_id] = ticket

    return tickets


def _load_columns(tree: Tree, tickets: dict[str, Ticket]) -> list[Column]:
    """Load all column directories from the tree."""
    columns = []

    for item in tree:
        if not isinstance(item, Tree):
            continue

        # Parse directory name for order and name
        order, name, hidden = _parse_dirname(item.name)
        if order is None:
            continue  # Not a column directory

        column = Column(
            order=order,
            name=name,
            path=item.name,
            hidden=hidden,
            content=MarkdownDoc(),
        )

        # Load index.md if present
        if "index.md" in item:
            column.content = _load_markdown_doc(item["index.md"])
            if column.content.title:
                column.name = column.content.title

        # Load ticket links (symlinks in git are blobs with mode 120000)
        column.links = _load_ticket_links(item, tickets)

        columns.append(column)

    columns.sort(key=lambda c: c.order)
    return columns


def _load_ticket_links(column_tree: Tree, tickets: dict[str, Ticket]) -> list[TicketLink]:
    """Load ticket symlinks from a column tree."""
    links = []

    for item in column_tree:
        # In git, symlinks are blobs with mode 120000 (0o120000)
        if item.type != "blob":
            continue
        if item.mode != 0o120000:
            continue
        if not item.name.endswith(".md"):
            continue

        position, slug = _parse_link_name(item.name)
        if position is None:
            continue

        # Symlink target is the blob content
        target = item.data_stream.read().decode("utf-8")
        # Extract ticket ID from target path like "../.all/001.md"
        ticket_id = target.split("/")[-1]
        if ticket_id.endswith(".md"):
            ticket_id = ticket_id[:-3]

        broken = ticket_id not in tickets

        link = TicketLink(
            position=position,
            slug=slug,
            ticket_id=ticket_id,
            path=f"{column_tree.name}/{item.name}",
            broken=broken,
        )
        links.append(link)

    links.sort(key=lambda link: link.position)
    return links


def _parse_dirname(name: str) -> tuple[str | None, str, bool]:
    """Parse a directory name into (order, name, hidden).

    Examples:
        "1.backlog" -> ("1", "Backlog", False)
        ".all" -> (None, "all", True)  # Hidden but not a column
        "2.in-progress" -> ("2", "In progress", False)
    """
    hidden = name.startswith(".")
    if hidden:
        name = name[1:]

    match = re.match(r"^([^.]+)\.(.+)$", name)
    if not match:
        return None, name, hidden

    order = match.group(1)
    slug = match.group(2)

    normalized = slug.replace("-", " ").replace("_", " ")
    normalized = normalized[0].upper() + normalized[1:] if normalized else ""

    return order, normalized, hidden


def _parse_link_name(name: str) -> tuple[str | None, str]:
    """Parse a symlink filename into (position, slug).

    Examples:
        "01.fix-login-bug.md" -> ("01", "fix-login-bug")
        "readme.md" -> (None, "readme")
    """
    stem = name[:-3] if name.endswith(".md") else name

    match = re.match(r"^([^.]+)\.(.+)$", stem)
    if not match:
        return None, stem

    return match.group(1), match.group(2)
