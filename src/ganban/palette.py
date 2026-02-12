"""Color palette and label color hashing."""

import hashlib

COLORS: dict[str, str] = {
    "red": "#800000",
    "green": "#008000",
    "olive": "#808000",
    "blue": "#000080",
    "purple": "#800080",
    "teal": "#008080",
    "silver": "#c0c0c0",
    "grey": "#808080",
    "bright_red": "#ff0000",
    "lime": "#00ff00",
    "yellow": "#ffff00",
    "bright_blue": "#0000ff",
    "fuchsia": "#ff00ff",
    "aqua": "#00ffff",
    "white": "#ffffff",
}


def color_for_label(label: str) -> str:
    """Deterministic hex color from label name."""
    index = int(hashlib.md5(label.encode()).hexdigest()[-2:], 16)
    palette = list(COLORS.values())
    return palette[index % len(palette)]
