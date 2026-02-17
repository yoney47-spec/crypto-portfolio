
import streamlit as st

def render_metrics(total_portfolio_value, total_pl_percent, total_pl_display, portfolio_24h_percent, portfolio_24h_change, currency_symbol, portfolio_data_len, top_performer, top_change, worst_performer, worst_change, vs_currency):
    """
    Renders the metrics section of the dashboard.
    """
    pl_color = "var(--accent-success)" if total_pl_display >= 0 else "var(--accent-danger)"
    pl_icon = "▲" if total_pl_display >= 0 else "▼"
    change_color = "var(--accent-success)" if portfolio_24h_change >= 0 else "var(--accent-danger)"
    change_icon = "▲" if portfolio_24h_change >= 0 else "▼"

    # Top Performer Info
    top_symbol = top_performer['symbol'] if top_performer else "-"
    
    # Worst Performer Info
    worst_symbol = worst_performer['symbol'] if worst_performer else "-"

    st.markdown(f"""
    <div class="metrics-grid">
        <div class="metric-card" style="border-color: var(--accent-primary); box-shadow: 0 0 15px rgba(0, 217, 255, 0.1);">
            <div class="metric-label">総資産 ({'USD' if currency_symbol == '$' else 'JPY'})</div>
            <div class="metric-value">{currency_symbol}{total_portfolio_value:,.0f}</div>
            <div class="metric-label">{portfolio_data_len} Assets</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">総損益 (P/L)</div>
            <div class="metric-value" style="color: {pl_color};">{pl_icon} {abs(total_pl_percent):.1f}%</div>
            <div class="metric-label">{currency_symbol}{abs(total_pl_display):,.0f}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">24h変動</div>
            <div class="metric-value" style="color: {change_color};">{change_icon} {abs(portfolio_24h_percent):.2f}%</div>
            <div class="metric-label">{currency_symbol}{abs(portfolio_24h_change):,.0f}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">保有銘柄</div>
            <div class="metric-value">{portfolio_data_len}</div>
            <div class="metric-label">Assets</div>
        </div>
        <div class="metric-card" style="border-color: var(--accent-success);">
            <div class="metric-label">🔥 急上昇</div>
            <div class="metric-value" style="color: var(--accent-success);">{top_symbol}</div>
            <div class="metric-label" style="color: var(--accent-success);">▲ {top_change:.1f}%</div>
        </div>
        <div class="metric-card" style="border-color: var(--accent-danger);">
            <div class="metric-label">📉 急下落</div>
            <div class="metric-value" style="color: var(--accent-danger);">{worst_symbol}</div>
            <div class="metric-label" style="color: var(--accent-danger);">▼ {abs(worst_change):.1f}%</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
