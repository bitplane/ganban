"""Fixtures for UI tests."""

import pytest

from ganban.ui.menu import MenuItem, MenuSeparator


@pytest.fixture
def menu_items():
    """A menu tree with disabled items and multiple levels of depth.

    Structure:
    - Open
    - Save (disabled)
    - ---
    - Edit >
      - Cut
      - Copy
      - Paste (disabled)
      - ---
      - Special >
        - Format
        - Transform
    - View >
      - Zoom In
      - Zoom Out
    - ---
    - Quit
    """
    return [
        MenuItem("Open", item_id="open"),
        MenuItem("Save", item_id="save", disabled=True),
        MenuSeparator(),
        MenuItem(
            "Edit",
            item_id="edit",
            submenu=[
                MenuItem("Cut", item_id="cut"),
                MenuItem("Copy", item_id="copy"),
                MenuItem("Paste", item_id="paste", disabled=True),
                MenuSeparator(),
                MenuItem(
                    "Special",
                    item_id="special",
                    submenu=[
                        MenuItem("Format", item_id="format"),
                        MenuItem("Transform", item_id="transform"),
                    ],
                ),
            ],
        ),
        MenuItem(
            "View",
            item_id="view",
            submenu=[
                MenuItem("Zoom In", item_id="zoom_in"),
                MenuItem("Zoom Out", item_id="zoom_out"),
            ],
        ),
        MenuSeparator(),
        MenuItem("Quit", item_id="quit"),
    ]


@pytest.fixture
def all_disabled_menu():
    """A menu where all items are disabled."""
    return [
        MenuItem("One", item_id="one", disabled=True),
        MenuItem("Two", item_id="two", disabled=True),
        MenuItem("Three", item_id="three", disabled=True),
    ]
