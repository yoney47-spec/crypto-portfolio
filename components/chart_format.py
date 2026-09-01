"""Pure formatting helpers shared by portfolio charts."""


def format_chart_currency(value, currency_symbol):
    """Format a whole-number chart value in the selected display currency."""
    return f"{currency_symbol}{value:,.0f}"
