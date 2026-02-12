"""Card ID comparison and generation."""


def normalize_id(s: str) -> str:
    """Strip leading zeros from an ID, preserving at least one digit.

    "001" → "1", "0" → "0", "010" → "10"
    """
    stripped = s.lstrip("0")
    return stripped or "0"


def pad_id(s: str, width: int) -> str:
    """Zero-pad an ID to the given width.

    "1" with width=3 → "001", "10" with width=3 → "010"
    """
    return s.zfill(width)


def compare_ids(left: str, right: str) -> int:
    """Compare two IDs, padding with leading zeros.

    Returns -1 if left < right, 0 if equal, 1 if left > right.
    """
    max_len = max(len(left), len(right))
    left_padded = left.zfill(max_len)
    right_padded = right.zfill(max_len)

    if left_padded < right_padded:
        return -1
    if left_padded > right_padded:
        return 1
    return 0


def max_id(ids: list[str]) -> str | None:
    """Find the highest ID from a list, or None if empty."""
    if not ids:
        return None

    highest = ids[0]
    for id_ in ids[1:]:
        if compare_ids(id_, highest) > 0:
            highest = id_
    return highest


def next_id(current_max: str | None) -> str:
    """Generate the next ID after current_max.

    - If None, returns "1"
    - If numeric (e.g., "9"), returns str(int + 1) (e.g., "10")
    - If non-numeric (e.g., "fish"), returns "1" + "0" * len (e.g., "10000")
    """
    if current_max is None:
        return "1"

    try:
        return str(int(current_max) + 1)
    except ValueError:
        return "1" + "0" * len(current_max)
