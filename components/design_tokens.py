"""Shared visual tokens for Python-rendered charts.

Browser-facing equivalents live in ``styles/main.css``. Update both implementations
when a shared design token changes and keep ``DESIGN.md`` as the source of intent.
"""

# Surfaces and structure
COLOR_CANVAS = "#fafafb"
COLOR_SURFACE_1 = "#ffffff"
COLOR_SURFACE_2 = "#f2f2f3"
COLOR_BORDER = "rgba(23, 25, 28, 0.08)"
COLOR_GRID = "rgba(23, 25, 28, 0.06)"
COLOR_TRANSPARENT = "rgba(0, 0, 0, 0)"

# Text
COLOR_TEXT_PRIMARY = "#17191c"
COLOR_TEXT_SECONDARY = "#5f626b"
COLOR_TEXT_MUTED = "#636773"
COLOR_TEXT_DIM = "#72747d"

# Interaction and financial semantics
COLOR_ACTION = "#006bd6"
COLOR_ACTION_FILL = "rgba(0, 107, 214, 0.06)"
COLOR_POSITIVE = "#15803d"
COLOR_NEGATIVE = "#c53030"
COLOR_WARNING = "#a16207"
COLOR_FX = "#a16207"
COLOR_FX_FILL = "rgba(161, 98, 7, 0.06)"
COLOR_OTHER = "#72747d"

# Plotly accepts CSS-like font stacks.
FONT_UI = "-apple-system, BlinkMacSystemFont, Helvetica Neue, Noto Sans JP, sans-serif"
FONT_DATA = "SFMono-Regular, Menlo, Monaco, Consolas, monospace"
