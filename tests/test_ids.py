"""Tests for card ID comparison and generation."""

from ganban.ids import compare_ids, max_id, next_id


def test_compare_ids_numeric():
    """Numeric IDs compare correctly."""
    assert compare_ids("9", "10") == -1
    assert compare_ids("10", "9") == 1
    assert compare_ids("99", "100") == -1
    assert compare_ids("001", "002") == -1


def test_compare_ids_equal():
    """Equal IDs return 0."""
    assert compare_ids("10", "10") == 0
    assert compare_ids("abc", "abc") == 0


def test_compare_ids_alpha():
    """Alphabetic IDs compare lexicographically after padding."""
    assert compare_ids("a", "b") == -1
    assert compare_ids("a", "10") == -1  # "0a" < "10"
    assert compare_ids("z", "10") == -1  # "0z" < "10" (0 < 1)


def test_compare_ids_mixed_length():
    """IDs of different lengths are padded for comparison."""
    assert compare_ids("9", "10") == -1  # "09" < "10"
    assert compare_ids("99", "100") == -1  # "099" < "100"
    assert compare_ids("999", "1000") == -1  # "0999" < "1000"


def test_max_id_empty():
    """Empty list returns None."""
    assert max_id([]) is None


def test_max_id_single():
    """Single element returns that element."""
    assert max_id(["001"]) == "001"


def test_max_id_numeric():
    """Finds highest numeric ID."""
    assert max_id(["001", "002", "010"]) == "010"
    assert max_id(["9", "10", "11"]) == "11"
    assert max_id(["99", "100", "101"]) == "101"


def test_max_id_mixed():
    """Handles mixed numeric and alpha IDs."""
    assert max_id(["001", "fish", "002"]) == "fish"  # "fish" > "0002"
    assert max_id(["10", "9", "a"]) == "10"  # "10" > "09" > "0a"


def test_next_id_none():
    """None returns starting ID."""
    assert next_id(None) == "001"


def test_next_id_numeric():
    """Numeric IDs increment."""
    assert next_id("001") == "002"
    assert next_id("99") == "100"
    assert next_id("999") == "1000"


def test_next_id_alpha():
    """Non-numeric IDs produce 1 followed by zeros."""
    assert next_id("fish") == "10000"  # 4 chars -> "1" + "0000"
    assert next_id("a") == "10"  # 1 char -> "1" + "0"
    assert next_id("abc") == "1000"  # 3 chars -> "1" + "000"


def test_next_id_padded_numeric():
    """Padded numeric IDs still parse as int."""
    assert next_id("007") == "008"
    assert next_id("0099") == "0100"
