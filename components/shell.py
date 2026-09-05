from html import escape
import streamlit as st
from admin_auth import sign_out_admin
from portfolio_logic import money, percent, tone, JST

NAV = [("pages/0_dashboard.py", "概要", ":material/space_dashboard:"),
       ("pages/1_assets.py", "資産", ":material/account_balance_wallet:"),
       ("pages/4_goals.py", "目標", ":material/flag:"),
       ("pages/2_transactions.py", "取引", ":material/swap_horiz:"),
       ("pages/3_settings.py", "設定", ":material/tune:")]


def render_shell(admin, current_title="ダッシュボード"):
    with st.sidebar:
        st.markdown("<div class='brand'>◒ <span>CryptoFolio</span></div>", unsafe_allow_html=True)
        st.caption("管理モード" if admin else "公開ポートフォリオ · 閲覧のみ")
        for path, label, icon in NAV:
            if admin or label not in ("目標", "取引"):
                st.page_link(path, label={"概要": "ダッシュボード", "資産": "保有資産"}.get(label, label), icon=icon)
        st.divider()
        if admin:
            if st.button("ログアウト", width="stretch"):
                sign_out_admin()
                for key in list(st.session_state):
                    if key.startswith(("trade_", "goal_", "private_")):
                        del st.session_state[key]
                st.rerun()
        else:
            st.page_link("pages/3_settings.py", label="管理者ログイン", icon=":material/lock:")
        st.caption("価格は最大10分キャッシュされます。\n取引・目標の編集は管理者のみ。")
    st.session_state.setdefault("display_currency", "JPY")
    st.session_state.setdefault("mask_amounts", False)
    st.session_state.setdefault("display_density", "標準")
    with st.container(key="toolbar"):
        a, b = st.columns([3, 2])
        with a:
            selected = st.segmented_control("表示通貨", ["JPY", "USD"], key="currency_widget",
                                            default=st.session_state.display_currency, label_visibility="collapsed")
            if selected:
                st.session_state.display_currency = selected
        with b:
            st.toggle("金額を隠す", key="mask_amounts")
    with st.container(key="mobile-nav"):
        visible = [item for item in NAV if admin or item[1] not in ("目標", "取引")]
        current_label = {"ダッシュボード": "概要", "保有資産": "資産"}.get(current_title, current_title)
        for col, (path, label, icon) in zip(st.columns(len(visible)), visible):
            with col.container(key="mobile-nav-active" if label == current_label else f"mobile-nav-{label}"):
                st.page_link(path, label=label, icon=icon)


def preferences():
    return st.session_state.get("display_currency", "JPY"), st.session_state.get("mask_amounts", False)


def intro(title, description=""):
    st.markdown(f"<div class='page-intro'><h1>{escape(title)}</h1><p>{escape(description)}</p></div>", unsafe_allow_html=True)


def metric(label, value, detail="", semantic="neutral"):
    return f"<article class='metric-card'><div class='metric-label'>{escape(label)}</div><div class='metric-value {semantic}'>{escape(value)}</div><div class='metric-detail'>{escape(detail)}</div></article>"


def overview(data, currency, mask, ytd):
    total_label = "総資産" if data["complete"] else "総資産（取得できた分）"
    cards = metric(total_label, money(data["total"], currency, masked=mask), f"{len(data['rows'])}銘柄 · {currency}")
    cards += metric("24時間の価格影響" + ("（一部）" if not data["change_complete"] else ""), money(data["change_amount"], currency, masked=mask, signed=True), percent(data["change_percent"]), tone(data["change_amount"]))
    cards += metric("年初来損益", money(ytd["amount"], currency, masked=mask, signed=True), "データ不足" if ytd["amount"] is None else "手数料を除く参考値", tone(ytd["amount"]))
    top = data["rows"][0] if data["rows"] else {}
    cards += metric("最大の構成比", percent(top.get("weight"), signed=False), top.get("symbol", "—"))
    st.markdown(f"<div class='metric-grid'>{cards}</div>", unsafe_allow_html=True)


def freshness(data):
    updated = data.get("updated_at")
    if updated:
        if updated.tzinfo is None:
            from datetime import timezone
            updated = updated.replace(tzinfo=timezone.utc)
        stamp = updated.astimezone(JST).strftime("%m月%d日 %H:%M JST")
        source = "保存価格" if data.get("stale") else "市場価格"
        st.caption(f"{source}の取得時刻：{stamp} · CoinGecko")
    elif data.get("rows"):
        st.caption("価格の取得時刻：確認できません")
    if data.get("price_error"):
        st.warning(data["price_error"])
    if data.get("stale"):
        st.warning("現在価格を取得できないため、直近に取得した価格を表示しています。")
    if data.get("missing"):
        st.warning("価格が未取得の銘柄：" + "、".join(data["missing"]) + "。合計と構成比は取得できた分です。")
