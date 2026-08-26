
from html import escape

import streamlit as st


def _single_line_html(markup: str) -> str:
    """Keep Markdown from interpreting indented HTML fragments as code blocks."""
    return "".join(line.strip() for line in markup.splitlines())


def render_metrics(total_portfolio_value, total_pl_percent, total_pl_display, portfolio_24h_percent, portfolio_24h_change, currency_symbol, portfolio_data_len, top_performer, top_change, worst_performer, worst_change, vs_currency):
    """
    Renders the Bento Grid Hero metrics section of the dashboard.
    """
    # Styling classes
    pl_class = "success" if total_pl_display >= 0 else "danger"
    pl_icon = "▲ +" if total_pl_display >= 0 else "▼ -"
    change_class = "success" if portfolio_24h_change >= 0 else "danger"
    change_icon = "▲ +" if portfolio_24h_change >= 0 else "▼ -"

    # Top & Worst Movers
    top_symbol = escape(str(top_performer['symbol'])) if top_performer else "-"
    worst_symbol = escape(str(worst_performer['symbol'])) if worst_performer else "-"
    top_change_sign = "+" if top_change >= 0 else ""
    worst_change_sign = "+" if worst_change >= 0 else ""

    # Amount formatting
    if currency_symbol == "$":
        formatted_total = f"{total_portfolio_value:,.2f}"
        formatted_pl_amt = f"${abs(total_pl_display):,.2f}"
        formatted_24h_amt = f"${abs(portfolio_24h_change):,.2f}"
    else:
        formatted_total = f"{total_portfolio_value:,.0f}"
        formatted_pl_amt = f"¥{abs(total_pl_display):,.0f}"
        formatted_24h_amt = f"¥{abs(portfolio_24h_change):,.0f}"

    metric_html = f"""
    <div class="bento-container">
        <div class="hero-main-card">
            <div>
                <div class="hero-label">総評価額</div>
                <div class="hero-amount">
                    <span class="curr-sym">{currency_symbol}</span>{formatted_total}
                </div>
            </div>
            <div class="hero-badges-row">
                <div class="metric-pill {pl_class}">
                    <span class="metric-pill-label">今年の損益</span>
                    <span class="metric-pill-value">{pl_icon}{abs(total_pl_percent):.1f}% ({formatted_pl_amt})</span>
                </div>
                <div class="metric-pill {change_class}">
                    <span class="metric-pill-label">24時間</span>
                    <span class="metric-pill-value">{change_icon}{abs(portfolio_24h_percent):.2f}% ({formatted_24h_amt})</span>
                </div>
            </div>
        </div>
        <div class="bento-sub-grid">
            <div class="bento-sub-card">
                <div class="bento-sub-label">上昇率 1位</div>
                <div class="bento-sub-value" style="color: var(--accent-success);">{top_symbol}</div>
                <div class="bento-sub-meta" style="color: var(--accent-success);">{top_change_sign}{top_change:.1f}% / 24時間</div>
            </div>
            <div class="bento-sub-card">
                <div class="bento-sub-label">下落率 1位</div>
                <div class="bento-sub-value" style="color: var(--accent-danger);">{worst_symbol}</div>
                <div class="bento-sub-meta" style="color: var(--accent-danger);">{worst_change_sign}{worst_change:.1f}% / 24時間</div>
            </div>
            <div class="bento-sub-card">
                <div class="bento-sub-label">保有銘柄</div>
                <div class="bento-sub-value">{portfolio_data_len}</div>
                <div class="bento-sub-meta">公開中の銘柄数</div>
            </div>
            <div class="bento-sub-card">
                <div class="bento-sub-label">表示通貨</div>
                <div class="bento-sub-value">{vs_currency.upper()}</div>
                <div class="bento-sub-meta">評価額の基準通貨</div>
            </div>
        </div>
    </div>
    """
    st.markdown(_single_line_html(metric_html), unsafe_allow_html=True)
