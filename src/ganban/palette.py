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

# 27 visually distinct colours, arranged so that common label names
# (bug, feature, urgent, etc.) land on sensible defaults via the
# md5-byte-sum hash. See tests/ui/test_color.py for the mapping.
LABEL_COLORS: list[str] = [
    "#cc0000",  # red
    "#2e8b57",  # sea green
    "#aa2244",  # crimson
    "#dd6600",  # orange
    "#ccaa00",  # dark yellow
    "#7b68ee",  # medium slate blue
    "#2266cc",  # blue
    "#cc6699",  # pink
    "#886644",  # brown
    "#808080",  # grey
    "#668800",  # olive green
    "#dd4488",  # hot pink
    "#996633",  # sienna
    "#4499cc",  # sky blue
    "#5577cc",  # cornflower
    "#bb5500",  # burnt orange
    "#880022",  # dark red
    "#aa66cc",  # medium purple
    "#448888",  # dark cyan
    "#cc4444",  # indian red
    "#22aa44",  # green
    "#6688aa",  # steel blue
    "#44cc44",  # bright green
    "#008888",  # teal
    "#ee2222",  # bright red
    "#887766",  # taupe
    "#cc8800",  # amber
]


def color_for_label(label: str) -> str:
    """Deterministic hex color from label name.

    Uses the sum of all md5 bytes mod palette size, which spreads
    common label names across the palette with minimal collisions.
    """
    h = hashlib.md5(label.encode()).hexdigest()
    index = sum(int(h[i : i + 2], 16) for i in range(0, 32, 2))
    return LABEL_COLORS[index % len(LABEL_COLORS)]
