
import streamlit as st

from access_control import is_public_read_only


def render_sidebar():
    """
    Render the shared navigation and display controls.
    """
    public_mode = is_public_read_only()

    st.sidebar.markdown(
        "<div class='sidebar-brand'>"
        "<div class='sidebar-logo'>◆</div>"
        "<div><div class='sidebar-brand-name'>CryptoFolio</div>"
        "<div class='sidebar-brand-tagline'>PORTFOLIO TRACKER</div></div>"
        "</div>",
        unsafe_allow_html=True,
    )

    if public_mode:
        st.sidebar.markdown(
            "<div class='readonly-badge'><span></span>公開ビュー・閲覧専用</div>",
            unsafe_allow_html=True,
        )

    st.sidebar.markdown("<div class='sidebar-section-label'>ナビゲーション</div>", unsafe_allow_html=True)
    st.sidebar.page_link("app.py", label="ダッシュボード", icon="📊")
    st.sidebar.page_link("pages/1_assets.py", label="保有資産", icon="💼")

    st.sidebar.markdown("<div class='sidebar-section-label'>表示設定</div>", unsafe_allow_html=True)

    if not public_mode:
        if st.sidebar.button("データ更新", use_container_width=True):
            with st.spinner("キャッシュをクリア中..."):
                st.cache_data.clear()
                st.session_state["force_price_refresh"] = True
            st.sidebar.success("データを更新しました")
            st.rerun()

    currency = st.sidebar.radio(
        "表示通貨",
        ["USD", "JPY"],
        key="currency_selector",
        index=0,
        horizontal=True,
    )

    layout_mode = st.sidebar.radio(
        "一覧表示",
        ["標準", "コンパクト"],
        key="layout_mode_selector",
        index=0,
        horizontal=True,
    )

    if public_mode:
        st.sidebar.markdown(
            "<div class='sidebar-note'>"
            "公開画面では取引履歴・保管場所・編集機能を表示しません。"
            "</div>",
            unsafe_allow_html=True,
        )

    return currency, layout_mode
