"""Card mutation operations for ganban boards."""

from ganban.ids import max_id, next_id
from ganban.model.node import ListNode, Node


def create_card(
    board: Node,
    title: str,
    body: str = "",
    column: Node | None = None,
    position: int | None = None,
) -> tuple[str, Node]:
    """Create a new card and add it to the board.

    Returns (card_id, card_node).
    """
    card_id = next_id(max_id(board.cards.keys()))

    sections = ListNode()
    sections[title] = body

    card = Node(
        sections=sections,
        meta={},
    )
    board.cards[card_id] = card

    # Add to column
    target_column = column
    if target_column is None:
        for col in board.columns:
            target_column = col
            break

    if target_column is not None:
        links = list(target_column.links)
        if position is not None:
            links.insert(position, card_id)
        else:
            links.append(card_id)
        target_column.links = links

    return card_id, card


def find_card_column(board: Node, card_id: str) -> Node | None:
    """Find the column containing a card."""
    for col in board.columns:
        if card_id in col.links:
            return col
    return None


def move_card(
    board: Node,
    card_id: str,
    target_column: Node,
    position: int | None = None,
) -> None:
    """Move a card to target_column at position.

    Handles same-column reorder atomically (single list assignment)
    to avoid watchers removing the card widget between operations.
    """
    source_column = find_card_column(board, card_id)

    if source_column is target_column:
        links = list(source_column.links)
        links.remove(card_id)
        insert_pos = min(position, len(links)) if position is not None else len(links)
        links.insert(insert_pos, card_id)
        source_column.links = links
        return

    if source_column is not None:
        links = list(source_column.links)
        links.remove(card_id)
        source_column.links = links

    links = list(target_column.links)
    insert_pos = min(position, len(links)) if position is not None else len(links)
    links.insert(insert_pos, card_id)
    target_column.links = links


def archive_card(board: Node, card_id: str) -> None:
    """Archive a card by removing it from its column's links."""
    col = find_card_column(board, card_id)
    if col is not None:
        links = list(col.links)
        links.remove(card_id)
        col.links = links
