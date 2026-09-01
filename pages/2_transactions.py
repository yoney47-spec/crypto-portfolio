"""Administrator-only transaction entry and history."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd
import streamlit as st

from access_control import stop_on_private_page
from components.sidebar import render_sidebar
from database_supabase import (
    add_transaction,
    check_duplicate_transactions,
    delete_transaction,
    get_assets_list,
    get_transaction_records,
    update_transaction,
)


JST = timezone(timedelta(hours=9))
TYPE_LABELS = {
    "Buy": "購入",
    "Sell": "売却",
    "Transfer": "出庫・移動",
    "Airdrop": "エアドロップ",
    "Staking Reward": "ステーキング報酬",
    "Interest": "利息",
    "Gift": "受贈",
}
TYPE_KEYS = list(TYPE_LABELS)


st.set_page_config(
    page_title="取引管理 | CryptoFolio",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
)


def load_css() -> None:
    css_file = Path(__file__).parent.parent / "styles" / "main.css"
    with open(css_file, encoding="utf-8") as css:
        st.markdown(f"<style>{css.read()}</style>", unsafe_allow_html=True)


def _asset_options() -> Tuple[List[Tuple], Dict[str, int]]:
    assets = get_assets_list()
    options = {f"{symbol} · {name}": asset_id for asset_id, name, symbol in assets}
    return assets, options


def _as_jst(value: Any) -> datetime:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return datetime.now(JST)
    result = parsed.to_pydatetime()
    if result.tzinfo is None:
        return result.replace(tzinfo=JST)
    return result.astimezone(JST)


def _type_index(transaction_type: str) -> int:
    try:
        return TYPE_KEYS.index(transaction_type)
    except ValueError:
        return 0


def _save_transaction(
    *,
    date_value,
    time_value,
    transaction_type: str,
    asset_id: int,
    quantity: float,
    price: float,
    fee: float,
    fee_currency: str,
    source: str,
    notes: str,
    accept_duplicate: bool,
) -> None:
    transaction_at = datetime.combine(date_value, time_value).replace(tzinfo=JST)
    duplicate, _ = check_duplicate_transactions(transaction_at, asset_id, quantity)
    if duplicate and not accept_duplicate:
        st.warning("同じ時刻付近に同一数量の取引があります。重複でない場合は確認欄をオンにしてください。")
        return

    saved = add_transaction(
        transaction_at,
        transaction_type,
        asset_id,
        quantity,
        price,
        quantity * price,
        notes.strip(),
        skip_duplicate_check=True,
        fee_amount=fee,
        fee_currency=fee_currency,
        source=source,
    )
    if saved:
        st.session_state["transaction_feedback"] = "取引を保存しました。"
        st.rerun()
    st.error("取引を保存できませんでした。入力内容と権限を確認してください。")


@st.dialog("取引を編集")
def edit_transaction_dialog(row: Dict[str, Any]) -> None:
    _, options = _asset_options()
    if not options:
        st.error("先に資産を登録してください。")
        return

    current_dt = _as_jst(row.get("date"))
    current_asset = next(
        (label for label, asset_id in options.items() if asset_id == row.get("asset_id")),
        next(iter(options)),
    )

    with st.form(f"edit_transaction_{row['id']}"):
        date_col, time_col = st.columns(2)
        with date_col:
            edit_date = st.date_input("取引日", value=current_dt.date())
        with time_col:
            edit_time = st.time_input("取引時刻", value=current_dt.time().replace(tzinfo=None))

        type_col, asset_col = st.columns(2)
        with type_col:
            edit_type = st.selectbox(
                "取引種別",
                TYPE_KEYS,
                index=_type_index(str(row.get("type") or "")),
                format_func=lambda value: TYPE_LABELS[value],
            )
        with asset_col:
            edit_asset_label = st.selectbox(
                "銘柄", list(options), index=list(options).index(current_asset)
            )

        quantity_col, price_col = st.columns(2)
        with quantity_col:
            edit_quantity = st.number_input(
                "数量",
                min_value=0.00000001,
                value=float(row.get("quantity") or 0.00000001),
                step=0.00000001,
                format="%.8f",
            )
        with price_col:
            edit_price = st.number_input(
                "取引時の単価（USD）",
                min_value=0.0,
                value=float(row.get("price_per_unit") or 0),
                step=0.01,
                format="%.8f",
            )

        fee_col, currency_col = st.columns(2)
        with fee_col:
            edit_fee = st.number_input(
                "手数料",
                min_value=0.0,
                value=float(row.get("fee_amount") or 0),
                step=0.01,
                format="%.8f",
            )
        with currency_col:
            edit_fee_currency = st.text_input(
                "手数料通貨",
                value=str(row.get("fee_currency") or "USD"),
                max_chars=12,
            )

        edit_source = st.text_input(
            "取引所・ウォレット",
            value=str(row.get("source") or ""),
            placeholder="例: GMOコイン",
        )
        edit_notes = st.text_area("メモ", value=str(row.get("notes") or ""))
        st.markdown(
            f"<div class='transaction-total'><span>取引総額</span>"
            f"<strong>${edit_quantity * edit_price:,.2f}</strong></div>",
            unsafe_allow_html=True,
        )
        submitted = st.form_submit_button(
            "変更を保存", type="primary", use_container_width=True
        )

    if submitted:
        if not edit_fee_currency.strip():
            st.error("手数料通貨を入力してください。")
            return
        success = update_transaction(
            row["id"],
            datetime.combine(edit_date, edit_time).replace(tzinfo=JST),
            edit_type,
            options[edit_asset_label],
            edit_quantity,
            edit_price,
            edit_quantity * edit_price,
            edit_notes.strip(),
            fee_amount=edit_fee,
            fee_currency=edit_fee_currency,
            source=edit_source,
        )
        if success:
            st.session_state["transaction_feedback"] = "取引を更新しました。"
            st.rerun()
        st.error("取引を更新できませんでした。")


@st.dialog("取引を削除")
def delete_transaction_dialog(row: Dict[str, Any]) -> None:
    st.write(
        f"{_as_jst(row.get('date')).strftime('%Y/%m/%d %H:%M')} の "
        f"{row.get('symbol', '')} {TYPE_LABELS.get(row.get('type'), row.get('type', ''))}を削除します。"
    )
    st.caption("削除すると保有数量も再計算されます。この操作は元に戻せません。")
    confirmed = st.checkbox("この取引を削除することを確認しました")
    if st.button(
        "削除する",
        type="primary",
        use_container_width=True,
        disabled=not confirmed,
    ):
        if delete_transaction(row["id"]):
            st.session_state["transaction_feedback"] = "取引を削除しました。"
            st.rerun()
        st.error("取引を削除できませんでした。")


def _render_summary(rows: List[Dict[str, Any]]) -> None:
    invested = sum(
        float(row.get("total_amount") or 0) for row in rows if row.get("type") == "Buy"
    )
    sold = sum(
        float(row.get("total_amount") or 0) for row in rows if row.get("type") == "Sell"
    )
    fees = sum(
        float(row.get("fee_amount") or 0)
        for row in rows
        if row.get("fee_currency") == "USD"
    )
    summary_html = f"""
    <div class="summary-grid transaction-summary">
      <div class="summary-card"><div class="summary-label">累計購入額</div><div class="summary-value">${invested:,.2f}</div></div>
      <div class="summary-card"><div class="summary-label">累計売却額</div><div class="summary-value">${sold:,.2f}</div></div>
      <div class="summary-card"><div class="summary-label">取引件数</div><div class="summary-value">{len(rows):,}</div><div class="summary-meta">USD手数料 ${fees:,.2f}</div></div>
    </div>
    """
    st.markdown(
        "".join(line.strip() for line in summary_html.splitlines()),
        unsafe_allow_html=True,
    )


load_css()
render_sidebar()
stop_on_private_page()

feedback = st.session_state.pop("transaction_feedback", None)
if feedback:
    st.toast(feedback)

st.markdown(
    "<div class='page-intro'><div><div class='page-title'>取引管理</div>"
    "<div class='page-description'>購入・売却・報酬などを記録し、保有数量へ即時反映します。</div>"
    "</div><span class='admin-chip'>管理者のみ</span></div>",
    unsafe_allow_html=True,
)

all_rows = get_transaction_records()
_render_summary(all_rows)

entry_tab, history_tab = st.tabs(["取引を追加", "取引履歴"])

with entry_tab:
    _, asset_options = _asset_options()
    if not asset_options:
        st.info("取引を追加する前に、サイドバーの「資産管理」から銘柄を登録してください。")
    else:
        with st.form("add_transaction_form", clear_on_submit=True):
            st.markdown("<div class='form-section-title'>基本情報</div>", unsafe_allow_html=True)
            date_col, time_col = st.columns(2)
            with date_col:
                transaction_date = st.date_input("取引日", value=datetime.now(JST).date())
            with time_col:
                transaction_time = st.time_input(
                    "取引時刻",
                    value=datetime.now(JST).time().replace(microsecond=0, tzinfo=None),
                )

            type_col, asset_col = st.columns(2)
            with type_col:
                transaction_type = st.selectbox(
                    "取引種別", TYPE_KEYS, format_func=lambda value: TYPE_LABELS[value]
                )
            with asset_col:
                asset_label = st.selectbox("銘柄", list(asset_options))

            quantity_col, price_col = st.columns(2)
            with quantity_col:
                quantity = st.number_input(
                    "数量",
                    min_value=0.00000001,
                    step=0.00000001,
                    format="%.8f",
                )
            with price_col:
                price = st.number_input(
                    "取引時の単価（USD）",
                    min_value=0.0,
                    step=0.01,
                    format="%.8f",
                    help="報酬・受贈も取得時の時価を残せます。不明な場合は0のまま保存できます。",
                )

            fee_col, currency_col = st.columns(2)
            with fee_col:
                fee = st.number_input(
                    "手数料", min_value=0.0, step=0.01, format="%.8f"
                )
            with currency_col:
                fee_currency = st.text_input("手数料通貨", value="USD", max_chars=12)

            source = st.text_input(
                "取引所・ウォレット",
                placeholder="例: GMOコイン / Tangem Wallet",
            )
            notes = st.text_area("メモ", placeholder="任意")
            accept_duplicate = st.checkbox("重複警告が出ても別取引として保存する")
            st.markdown(
                f"<div class='transaction-total'><span>取引総額</span>"
                f"<strong>${quantity * price:,.2f}</strong></div>",
                unsafe_allow_html=True,
            )
            submitted = st.form_submit_button(
                "取引を保存", type="primary", use_container_width=True
            )

        if submitted:
            if not fee_currency.strip():
                st.error("手数料通貨を入力してください。")
            else:
                _save_transaction(
                    date_value=transaction_date,
                    time_value=transaction_time,
                    transaction_type=transaction_type,
                    asset_id=asset_options[asset_label],
                    quantity=quantity,
                    price=price,
                    fee=fee,
                    fee_currency=fee_currency,
                    source=source,
                    notes=notes,
                    accept_duplicate=accept_duplicate,
                )

with history_tab:
    filter_col, export_col = st.columns([2, 1])
    with filter_col:
        history_filter = st.segmented_control(
            "表示範囲",
            ["すべて", "コストあり", "報酬・その他"],
            default="すべて",
            label_visibility="collapsed",
        )

    rows = get_transaction_records(history_filter or "すべて")
    export_rows = []
    for row in rows:
        export_rows.append(
            {
                "日時": _as_jst(row.get("date")).strftime("%Y-%m-%d %H:%M"),
                "種別": TYPE_LABELS.get(row.get("type"), row.get("type")),
                "銘柄": row.get("symbol"),
                "数量": float(row.get("quantity") or 0),
                "単価_USD": float(row.get("price_per_unit") or 0),
                "総額_USD": float(row.get("total_amount") or 0),
                "手数料": float(row.get("fee_amount") or 0),
                "手数料通貨": row.get("fee_currency"),
                "取引所・ウォレット": row.get("source"),
                "メモ": row.get("notes"),
            }
        )

    with export_col:
        csv_data = pd.DataFrame(export_rows).to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "CSVを書き出す",
            data=csv_data,
            file_name=f"cryptofolio_transactions_{datetime.now(JST):%Y%m%d}.csv",
            mime="text/csv",
            use_container_width=True,
            disabled=not rows,
        )

    if not rows:
        st.info("該当する取引はありません。")
    else:
        display_df = pd.DataFrame(export_rows)
        st.dataframe(
            display_df[
                ["日時", "種別", "銘柄", "数量", "単価_USD", "総額_USD", "取引所・ウォレット"]
            ],
            use_container_width=True,
            hide_index=True,
            height=min(560, max(180, len(rows) * 35 + 42)),
        )

        selected_label = st.selectbox(
            "編集する取引",
            range(len(rows)),
            format_func=lambda index: (
                f"{_as_jst(rows[index].get('date')).strftime('%Y/%m/%d %H:%M')} · "
                f"{rows[index].get('symbol', '')} · "
                f"{TYPE_LABELS.get(rows[index].get('type'), rows[index].get('type', ''))} · "
                f"{float(rows[index].get('quantity') or 0):,.8f}".rstrip("0").rstrip(".")
            ),
        )
        selected_row = rows[selected_label]
        edit_col, delete_col = st.columns(2)
        with edit_col:
            if st.button("選択した取引を編集", use_container_width=True):
                edit_transaction_dialog(selected_row)
        with delete_col:
            if st.button("選択した取引を削除", use_container_width=True):
                delete_transaction_dialog(selected_row)
