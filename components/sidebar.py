
import streamlit as st

def render_sidebar():
    """
    Renders the sidebar content and returns the selected currency.
    """
    # Brand logo area
    st.sidebar.markdown("""
    <div class="sidebar-brand">
        <div class="sidebar-logo">💎</div>
        <div class="sidebar-brand-name">CryptoFolio</div>
        <div class="sidebar-brand-tagline">Portfolio Tracker</div>
    </div>
    """, unsafe_allow_html=True)
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 設定")
    
    # Data refresh button
    if st.sidebar.button("データ更新", use_container_width=True):
        with st.spinner('キャッシュをクリア中...'):
            st.cache_data.clear()
            st.session_state['force_price_refresh'] = True  # Force price refresh
        st.sidebar.success("データを更新しました")
        st.rerun()

    # Currency selector
    currency = st.sidebar.radio(
        "表示通貨",
        ["USD", "JPY"],
        key="currency_selector",
        index=0
    )
    
    return currency
