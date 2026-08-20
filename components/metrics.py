
import streamlit as st

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
    top_symbol = top_performer['symbol'] if top_performer else "-"
    worst_symbol = worst_performer['symbol'] if worst_performer else "-"
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

    st.markdown(f"""
    <div class="bento-container">
        <!-- Main Hero Card -->
        <div class="hero-main-card">
            <div>
                <div class="hero-label">Total Portfolio Value</div>
                <div class="hero-amount">
                    <span class="curr-sym">{currency_symbol}</span>{formatted_total}
                </div>
            </div>
            <div class="hero-badges-row">
                <div class="metric-pill {pl_class}">
                    <span class="metric-pill-label">P/L</span>
                    <span class="metric-pill-value">{pl_icon}{abs(total_pl_percent):.1f}% ({formatted_pl_amt})</span>
                </div>
                <div class="metric-pill {change_class}">
                    <span class="metric-pill-label">24h</span>
                    <span class="metric-pill-value">{change_icon}{abs(portfolio_24h_percent):.2f}% ({formatted_24h_amt})</span>
                </div>
            </div>
        </div>

        <!-- Sub Grid (2x2) -->
        <div class="bento-sub-grid">
            <div class="bento-sub-card">
                <div class="bento-sub-label">Top Performer</div>
                <div class="bento-sub-value" style="color: var(--accent-success);">{top_symbol}</div>
                <div class="bento-sub-meta" style="color: var(--accent-success);">{top_change_sign}{top_change:.1f}% (24h)</div>
            </div>
            <div class="bento-sub-card">
                <div class="bento-sub-label">Worst Performer</div>
                <div class="bento-sub-value" style="color: var(--accent-danger);">{worst_symbol}</div>
                <div class="bento-sub-meta" style="color: var(--accent-danger);">{worst_change_sign}{worst_change:.1f}% (24h)</div>
            </div>
            <div class="bento-sub-card">
                <div class="bento-sub-label">Holdings</div>
                <div class="bento-sub-value">{portfolio_data_len}</div>
                <div class="bento-sub-meta">Tracked Assets</div>
            </div>
            <div class="bento-sub-card">
                <div class="bento-sub-label">Currency</div>
                <div class="bento-sub-value">{vs_currency.upper()}</div>
                <div class="bento-sub-meta">Base Valuation</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
