"""Explicit spot-market mapping, keyed by coin identity rather than ticker text."""
from dataclasses import dataclass
from html import escape
import json

from components.design_tokens import COLOR_SURFACE_1, COLOR_GRID


@dataclass(frozen=True)
class Market:
    symbol: str
    exchange: str
    base: str
    quote: str = 'USDT'

    @property
    def url(self):
        exchange, ticker = self.symbol.split(':')
        return f'https://www.tradingview.com/symbols/{ticker}/?exchange={exchange}'


# Spot markets verified through TradingView's widget symbol selector.
# Do not guess symbols for small tokens: ticker collisions can show another asset.
MARKETS = {
    'bitcoin': Market('BINANCE:BTCUSDT', 'Binance', 'BTC'),
    'ripple': Market('BINANCE:XRPUSDT', 'Binance', 'XRP'),
    'kaspa': Market('KUCOIN:KASUSDT', 'KuCoin', 'KAS'),
    'hyperliquid': Market('KUCOIN:HYPEUSDT', 'KuCoin', 'HYPE'),
    'sosovalue': Market('BYBIT:SOSOUSDT', 'Bybit', 'SOSO'),
    'solana': Market('BINANCE:SOLUSDT', 'Binance', 'SOL'),
}


def market_for(api_id):
    return MARKETS.get(str(api_id or '').strip().lower())


def widget_html(market):
    if market not in MARKETS.values():
        raise ValueError('Unverified TradingView market')
    options = dict(
        autosize=True, symbol=market.symbol, interval='60', timezone='Asia/Tokyo',
        theme='light', style='1', locale='ja', allow_symbol_change=False,
        hide_side_toolbar=True, hide_top_toolbar=False, hide_legend=False,
        hide_volume=False, save_image=False, calendar=False, details=False,
        hotlist=False, withdateranges=True, studies=[], watchlist=[], compareSymbols=[],
        backgroundColor=COLOR_SURFACE_1, gridColor=COLOR_GRID,
        support_host='https://www.tradingview.com',
    )
    # Only public market identifiers are sent to TradingView, never row data.
    config = json.dumps(options, ensure_ascii=True).replace('<', '\\u003c')
    return f'''<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>html,body{{margin:0;width:100%;height:100%;background:{COLOR_SURFACE_1};}}
.tradingview-widget-copyright{{font:12px/32px -apple-system,BlinkMacSystemFont,sans-serif;text-align:center;}}</style>
</head><body><div class="tradingview-widget-container" style="height:100%;width:100%">
<div class="tradingview-widget-container__widget" style="height:calc(100% - 32px);width:100%"></div>
<div class="tradingview-widget-copyright"><a href="{escape(market.url, quote=True)}" rel="noopener nofollow" target="_blank"><span class="blue-text">{market.base}/{market.quote} チャート</span></a><span class="trademark"> by TradingView</span></div>
<script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" async>{config}</script>
</div></body></html>'''
