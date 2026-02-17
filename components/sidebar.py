
import streamlit as st

def render_sidebar():
    """
    Renders the sidebar content and returns the selected currency.
    """
    st.sidebar.markdown("### 設定")
    
    # Data refresh button
    if st.sidebar.button("データ更新", width='stretch'):
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
