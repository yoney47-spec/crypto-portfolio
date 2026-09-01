"""HTML builder for administrator asset cards."""

from html import escape
from typing import Optional


def _safe_text(value: object) -> str:
    return escape(str(value or ""), quote=True).replace("\n", " ").replace("\r", " ")


def build_admin_asset_card(
    *,
    name: str,
    symbol: str,
    icon_url: str,
    price_text: Optional[str],
    change_value: Optional[float],
) -> str:
    """Return compact, balanced HTML that Streamlit cannot parse as a code block."""
    safe_name = _safe_text(name)
    safe_symbol = _safe_text(symbol)

    if icon_url and str(icon_url).strip():
        safe_icon_url = _safe_text(str(icon_url).strip())
        icon_html = (
            '<div class="asset-icon-shell">'
            f'<img src="{safe_icon_url}" alt="{safe_symbol}" class="asset-icon-image" '
            'onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'flex\';">'
            f'<div class="asset-icon asset-icon-fallback">{safe_symbol}</div>'
            '</div>'
        )
    else:
        icon_html = (
            '<div class="asset-icon-shell">'
            f'<div class="asset-icon asset-icon-fallback visible">{safe_symbol}</div>'
            '</div>'
        )

    if price_text is None:
        market_html = (
            '<div class="asset-price muted">価格データなし</div>'
            '<div class="asset-change muted">24時間データなし</div>'
        )
    else:
        safe_price = _safe_text(price_text)
        price_html = f'<div class="asset-price">{safe_price}</div>'
        if change_value is None:
            change_html = '<div class="asset-change muted">24時間データなし</div>'
        else:
            change = float(change_value)
            direction = "positive" if change >= 0 else "negative"
            marker = "▲" if change >= 0 else "▼"
            change_html = (
                f'<div class="asset-change {direction}">'
                f'{marker} {abs(change):.2f}% (24h)</div>'
            )
        market_html = price_html + change_html

    return (
        '<div class="asset-card admin-asset-card">'
        '<div class="asset-card-content">'
        f'{icon_html}'
        f'<div class="asset-symbol">{safe_symbol}</div>'
        f'<div class="asset-name">{safe_name}</div>'
        f'{market_html}'
        '</div>'
        '</div>'
    )
