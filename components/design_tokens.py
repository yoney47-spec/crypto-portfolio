"""Shared visual tokens for Python-rendered charts.

Browser-facing equivalents live in ``styles/main.css``. Update both implementations
when a shared design token changes and keep ``DESIGN.md`` as the source of intent.
"""

# Surfaces and structure
COLOR_CANVAS = "#0f0f10"
COLOR_SURFACE_1 = "#1c1c1e"
COLOR_SURFACE_2 = "#242426"
COLOR_BORDER = "rgba(255, 255, 255, 0.08)"
COLOR_GRID = "rgba(255, 255, 255, 0.03)"
COLOR_TRANSPARENT = "rgba(0, 0, 0, 0)"

# Text
COLOR_TEXT_PRIMARY = "#f5f5f7"
COLOR_TEXT_SECONDARY = "#aeaeb2"
COLOR_TEXT_MUTED = "#8e8e93"
COLOR_TEXT_DIM = "#636366"

# Interaction and financial semantics
COLOR_ACTION = "#0a84ff"
COLOR_ACTION_FILL = "rgba(10, 132, 255, 0.06)"
COLOR_POSITIVE = "#30d158"
COLOR_NEGATIVE = "#ff453a"
COLOR_WARNING = "#ffd60a"
COLOR_FX = "#ff9f0a"
COLOR_FX_FILL = "rgba(255, 159, 10, 0.06)"
COLOR_OTHER = "#636366"

# Plotly accepts CSS-like font stacks.
FONT_UI = "-apple-system, BlinkMacSystemFont, Helvetica Neue, Noto Sans JP, sans-serif"
FONT_DATA = "SFMono-Regular, Menlo, Monaco, Consolas, monospace"

