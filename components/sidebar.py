
import streamlit as st
from html import escape

from access_control import (
    is_public_read_only,
    is_snapshot_admin_unlocked,
    snapshot_admin_configuration_error,
    verify_snapshot_admin_pin,
)
from database_supabase import capture_portfolio_snapshot


def _record_snapshot() -> None:
    with st.sidebar:
        with st.spinner("現在の評価額を記録中..."):
            result = capture_portfolio_snapshot()

    st.session_state["snapshot_feedback"] = result


def _render_snapshot_action() -> None:
    """Render the PIN-protected snapshot action."""
    feedback = st.session_state.pop("snapshot_feedback", None)
    configuration_error = snapshot_admin_configuration_error()

    st.sidebar.markdown(
        "<div class='sidebar-section-label'>履歴</div>",
        unsafe_allow_html=True,
    )

    if feedback:
        if feedback.get("ok"):
            total_value = float(feedback.get("total_value_jpy") or 0)
            date_value = escape(str(feedback.get("date") or "本日"))
            message = f"{date_value} の記録を保存しました<br><strong>¥{total_value:,.0f}</strong>"
            status_class = "success"
        else:
            message = escape(str(feedback.get("message") or "保存できませんでした。"))
            status_class = "error"

        st.sidebar.markdown(
            f"<div class='snapshot-feedback {status_class}'>{message}</div>",
            unsafe_allow_html=True,
        )

    if configuration_error:
        st.sidebar.button(
            "スナップショットを追加",
            key="capture_portfolio_snapshot_unconfigured",
            type="primary",
            use_container_width=True,
            disabled=True,
        )
        st.sidebar.markdown(
            f"<div class='snapshot-note'>{escape(configuration_error)}</div>",
            unsafe_allow_html=True,
        )
        return

    if is_snapshot_admin_unlocked():
        if st.sidebar.button(
            "スナップショットを追加",
            key="capture_portfolio_snapshot_unlocked",
            type="primary",
            use_container_width=True,
            help="現在の評価額を今日の履歴として保存します。同日分は最新値に更新されます。",
        ):
            _record_snapshot()
            st.rerun()

        st.sidebar.markdown(
            "<div class='snapshot-note'><span class='snapshot-auth-dot'></span>"
            "本人確認済み。現在の評価額を今日の履歴へ保存します。</div>",
            unsafe_allow_html=True,
        )
        return

    if st.sidebar.button(
        "スナップショットを追加",
        key="open_snapshot_pin",
        type="primary",
        use_container_width=True,
        help="保存前に管理コードで本人確認します。",
    ):
        st.session_state["snapshot_pin_prompt_open"] = True
        st.rerun()

    if st.session_state.get("snapshot_pin_prompt_open", False):
        with st.sidebar.form("snapshot_pin_form", clear_on_submit=True):
            admin_pin = st.text_input(
                "管理コード",
                type="password",
                placeholder="管理コードを入力",
                label_visibility="collapsed",
            )
            submit_pin = st.form_submit_button(
                "確認して保存",
                type="primary",
                use_container_width=True,
            )

        if submit_pin:
            verified, message = verify_snapshot_admin_pin(admin_pin)
            if verified:
                st.session_state["snapshot_pin_prompt_open"] = False
                _record_snapshot()
            else:
                st.session_state["snapshot_feedback"] = {
                    "ok": False,
                    "message": message,
                }
            st.rerun()

    st.sidebar.markdown(
        "<div class='snapshot-note'>保存時のみ管理コードを確認します。"
        "同日分は最新値に更新されます。</div>",
        unsafe_allow_html=True,
    )


def render_sidebar():
    """
    Render the shared navigation and display controls.
    """
    public_mode = is_public_read_only()

    st.sidebar.markdown(
        "<div class='sidebar-brand'>"
        "<div class='brand-mark'><span></span><span></span><span></span></div>"
        "<div><div class='sidebar-brand-name'>CryptoFolio</div>"
        "<div class='sidebar-brand-tagline'>Portfolio</div></div>"
        "</div>",
        unsafe_allow_html=True,
    )

    if public_mode:
        st.sidebar.markdown(
            "<div class='readonly-badge'><span></span>公開ポートフォリオ</div>",
            unsafe_allow_html=True,
        )

    st.sidebar.markdown("<div class='sidebar-section-label'>ナビゲーション</div>", unsafe_allow_html=True)
    st.sidebar.page_link("app.py", label="ダッシュボード")
    st.sidebar.page_link("pages/1_assets.py", label="保有資産")

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
        _render_snapshot_action()

        st.sidebar.markdown(
            "<div class='sidebar-note'>"
            "公開画面では取引履歴・保管場所・編集機能を表示しません。"
            "</div>",
            unsafe_allow_html=True,
        )

    return currency, layout_mode
