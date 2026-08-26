"""
暗号資産ポートフォリオアプリ - 取引記録ページ
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from pathlib import Path
from constants import TRANSACTION_TYPES, is_cost_free_transaction
import requests
import time
from access_control import stop_on_private_page

# Import from Supabase adapter
from database_supabase import (
    get_all_transactions, 
    add_transaction, 
    update_transaction, 
    delete_transaction, 
    check_duplicate_transactions,
    get_statistics,
    get_assets_list
)

# ページ設定
st.set_page_config(
    page_title="取引記録 - Crypto Portfolio",
    page_icon="T",
    layout="wide",
    initial_sidebar_state="expanded"
)

stop_on_private_page()

# カスタムCSSの読み込み
def load_css():
    css_file = Path(__file__).parent.parent / "styles" / "main.css"
    with open(css_file, encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css()

# --- サイドバー設定 ---
st.sidebar.markdown("### 設定")

# 取引タイプフィルター
st.sidebar.markdown("---")
st.sidebar.markdown("### 取引フィルター")
transaction_filter = st.sidebar.radio(
    "表示する取引タイプ",
    ["すべて", "コストあり (Buy/Sell)", "コストなし (報酬等)"],
    index=0,
    help="取引履歴に表示する取引タイプをフィルタリング"
)

st.sidebar.markdown("---")
currency = st.sidebar.radio(
    "表示通貨",
    ["USD", "JPY"],
    key="currency_selector",
    index=0
)
currency_symbol = "$" if currency == "USD" else "¥"

# 為替レートを取得(USD -> JPY)
@st.cache_data(ttl=1800)  # 30分キャッシュ（APIレート制限対策）
def get_exchange_rate():
    """現在の為替レートを取得(1 USD = ? JPY)"""
    try:
        # Tetherの価格で代用するのが安定(1 USDT ≒ 1 USD)
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            "ids": "tether",
            "vs_currencies": "jpy"
        }
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        rate = data.get("tether", {}).get("jpy", 150.0) # フォールバック値
        return rate
    except:
        return 150.0 # 取得失敗時のフォールバック

# 現在価格の取得(USD/JPY) - キャッシュ有効化(TTL: 60秒)
@st.cache_data(ttl=1800)  # 30分キャッシュ（APIレート制限対策）
def fetch_current_prices(api_ids, vs_curr="usd"):
    """CoinGecko APIから現在価格を取得"""
    if not api_ids:
        return {}
        
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": ",".join(api_ids),
        "vs_currencies": vs_curr
    }
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 429:
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return None
            response.raise_for_status()
            return response.json()
        except:
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            return None
    return None

# レート取得
exchange_rate = 1.0
if currency == "JPY":
    exchange_rate = get_exchange_rate()

# Note: Database functions (get_all_transactions, etc.) are now imported from database_supabase

@st.dialog("取引の編集")
def edit_transaction_dialog(transaction_id, current_date, current_type, current_asset_id, current_quantity, current_price, current_notes):
    """取引編集用ダイアログ"""
    assets = get_assets_list()
    if not assets:
        st.error("資産が見つかりません")
        return

    asset_options = {f"{symbol} - {name}": asset_id for asset_id, name, symbol in assets}
    # 現在のAsset IDからキー（表示名）を探す
    current_asset_key = next((k for k, v in asset_options.items() if v == current_asset_id), list(asset_options.keys())[0])

    with st.form(key=f"edit_trans_form_{transaction_id}"):
        st.caption("※ 入力は常にUSDベースで行われます")
        col1, col2 = st.columns(2)
        with col1:
            # 日付と時間に分離
            try:
                if isinstance(current_date, str):
                    dt_obj = datetime.strptime(current_date, "%Y-%m-%d %H:%M:%S")
                else:
                    dt_obj = current_date # 既にdatetimeの場合
            except ValueError:
                dt_obj = datetime.now()

            edit_date = st.date_input("取引日", value=dt_obj.date())
            edit_time = st.time_input("取引時刻", value=dt_obj.time())
            
            # 取引種類の選択（全タイプ対応）
            type_options = []
            for t_type, t_info in TRANSACTION_TYPES.items():
                type_options.append(f"{t_info['icon']} {t_info['label']}")
            
            type_keys = list(TRANSACTION_TYPES.keys())
            
            # 現在のタイプのインデックスを取得
            try:
                current_type_idx = type_keys.index(current_type)
            except ValueError:
                current_type_idx = 0
            
            selected_type_display = st.selectbox(
                "取引種類",
                options=type_options,
                index=current_type_idx
            )
            
            # 選択された取引タイプを取得
            selected_type_idx = type_options.index(selected_type_display)
            edit_type = type_keys[selected_type_idx]
            
            # コストゼロ取引かどうかを判定
            is_zero_cost = is_cost_free_transaction(edit_type)
        
        with col2:
            edit_asset_key = st.selectbox("通貨", options=list(asset_options.keys()), index=list(asset_options.keys()).index(current_asset_key))
            edit_asset_id = asset_options[edit_asset_key]
            
            edit_quantity = st.number_input("数量", value=float(current_quantity), min_value=0.0, step=0.00000001, format="%.8f")
            
            # コストゼロ取引の場合は価格入力を無効化
            if is_zero_cost:
                st.text_input(
                    "単価 ($)",
                    value="0.00 (コストゼロ取引)",
                    disabled=True
                )
                edit_price = 0.0
            else:
                edit_price = st.number_input("単価 ($)", value=float(current_price), min_value=0.0, step=0.00000001, format="%.8f")
        
        edit_total = edit_quantity * edit_price
        st.markdown(f"### 合計金額: **${edit_total:,.2f}**")
        
        edit_notes = st.text_area("メモ", value=current_notes or "")
        
        col_save, col_cancel = st.columns(2)
        with col_save:
            if st.form_submit_button("更新する", width='stretch'):
                new_datetime = datetime.combine(edit_date, edit_time)
                if update_transaction(transaction_id, new_datetime, edit_type, edit_asset_id, edit_quantity, edit_price, edit_total, edit_notes):
                    st.success("更新しました")
                    st.rerun()
        
        with col_cancel:
            if st.form_submit_button("キャンセル", width='stretch'):
                st.rerun()

# ヘッダー
st.markdown("# 取引記録")
st.markdown("売買履歴の記録と一覧表示を行います")
st.markdown("---")

# 期間フィルター
st.markdown("### 📊 統計サマリー")

# 期間選択UI
st.markdown("**期間を選択して統計をフィルタリング:**")

filter_col1, filter_col2, filter_col3 = st.columns([2, 1, 1])

with filter_col1:
    # フィルタータイプ選択
    filter_mode = st.radio(
        "フィルター方法",
        ["全期間", "年指定", "年月指定"],
        horizontal=True,
        key="filter_mode"
    )

with filter_col2:
    if filter_mode in ["年指定", "年月指定"]:
        # 現在の年から過去10年分の選択肢を作成
        current_year = datetime.now().year
        year_options = list(range(current_year, current_year - 10, -1))
        selected_year = st.selectbox("年", year_options, key="selected_year")
    else:
        selected_year = None

with filter_col3:
    if filter_mode == "年月指定":
        month_options = list(range(1, 13))
        selected_month = st.selectbox("月", month_options, key="selected_month")
    else:
        selected_month = None

# 期間に応じた日付範囲を計算
from datetime import timedelta
from calendar import monthrange

end_date = datetime.now()
start_date = None
period_label = "全期間"

if filter_mode == "年指定" and selected_year:
    # 指定された年の1/1 00:00 から 12/31 23:59:59
    start_date = datetime(selected_year, 1, 1, 0, 0, 0)
    end_date = datetime(selected_year, 12, 31, 23, 59, 59)
    period_label = f"{selected_year}年"
elif filter_mode == "年月指定" and selected_year and selected_month:
    # 指定された年月の1日 00:00 から 最終日 23:59:59
    start_date = datetime(selected_year, selected_month, 1, 0, 0, 0)
    last_day = monthrange(selected_year, selected_month)[1]
    end_date = datetime(selected_year, selected_month, last_day, 23, 59, 59)
    period_label = f"{selected_year}年{selected_month}月"

# 統計情報の表示（期間フィルター適用）
if start_date:
    stats = get_statistics(start_date.strftime("%Y-%m-%d %H:%M:%S"), end_date.strftime("%Y-%m-%d %H:%M:%S"))
else:
    stats = get_statistics()

# 現在のポートフォリオ価値を計算(USDベース)
current_holdings_value_usd = 0.0
holdings_data = stats['holdings']

if holdings_data:
    # API IDリスト作成
    api_ids = [item[2] for item in holdings_data if item[2]] # item[2] is api_id
    
    # 現在価格取得(USD)
    prices = fetch_current_prices(api_ids, vs_curr="usd")
    
    if prices is None:
        st.warning("⚠️ APIレート制限中。現在価格の一部が取得できませんでした。", icon="⚠️")
        prices = {}
    
    for item in holdings_data:
        symbol, name, api_id, icon_url, qty = item  # 5つの値にアンパック
        price_data = prices.get(api_id, {})
        price_usd = price_data.get("usd", 0.0)
        current_holdings_value_usd += qty * price_usd

# Total P/L 計算(USDベース)
# Total P/L = (現在の資産価値 + 売却額) - 投資額
total_pl_usd = (current_holdings_value_usd + stats['total_sales']) - stats['total_investment']

# 表示用に変換
disp_total_investment = stats['total_investment'] * exchange_rate
disp_total_sales = stats['total_sales'] * exchange_rate
disp_total_pl = total_pl_usd * exchange_rate

col1, col2, col3, col4 = st.columns(4)

with col1:
    val_str = f"¥{disp_total_investment:,.0f}" if currency == "JPY" else f"${disp_total_investment:,.2f}"
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">投資額 ({period_label})</div>
        <div class="metric-value">{val_str}</div>
        <div class="metric-label">Buy</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    val_str = f"¥{disp_total_sales:,.0f}" if currency == "JPY" else f"${disp_total_sales:,.2f}"
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">売却額 ({period_label})</div>
        <div class="metric-value">{val_str}</div>
        <div class="metric-label">Sell</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    pl_color = "var(--accent-success)" if disp_total_pl >= 0 else "var(--accent-danger)"
    val_str = f"¥{disp_total_pl:,.0f}" if currency == "JPY" else f"${disp_total_pl:,.2f}"
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">損益 ({period_label})</div>
        <div class="metric-value" style="color: {pl_color};">{val_str}</div>
        <div class="metric-label">P/L</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">取引数 ({period_label})</div>
        <div class="metric-value">{stats['transaction_count']}</div>
        <div class="metric-label">Txns</div>
    </div>
    """, unsafe_allow_html=True)


# タブで機能を分ける
tab1, tab2, tab3 = st.tabs(["取引履歴", "新規取引", "保有状況"])

# タブ1: 取引履歴
with tab1:
    st.markdown("## 取引履歴一覧")
    st.markdown("<br>", unsafe_allow_html=True)
    
    # フィルターを適用して取引履歴を取得
    transactions = get_all_transactions(transaction_filter)
    
    if not transactions:
        st.info("取引が記録されていません。「新規取引」タブから追加してください。")
    else:
        # データフレームに変換
        df_trans = pd.DataFrame(transactions, columns=['id', 'date', 'type', 'symbol', 'name', 'quantity', 'price', 'total', 'notes', 'asset_id'])
        
        # ページネーション設定
        ITEMS_PER_PAGE = 50
        total_items = len(df_trans)
        total_pages = (total_items - 1) // ITEMS_PER_PAGE + 1 if total_items > 0 else 1
        
        # ページ選択（一番上に配置）
        if total_items > ITEMS_PER_PAGE:
            st.markdown(f"**全{total_items}件** （ページあたり{ITEMS_PER_PAGE}件表示）")
            col_page1, col_page2, col_page3 = st.columns([1, 2, 1])
            with col_page2:
                page = st.number_input(
                    f"ページ (1-{total_pages})", 
                    min_value=1, 
                    max_value=total_pages,
                    value=1,
                    key="transaction_page",
                    help=f"全{total_pages}ページ"
                )
            
            # ページに応じたデータを抽出
            start_idx = (page - 1) * ITEMS_PER_PAGE
            end_idx = min(start_idx + ITEMS_PER_PAGE, total_items)
            df_trans = df_trans.iloc[start_idx:end_idx].copy()  # ページ分のみ
            
            st.caption(f"表示中: {start_idx + 1}〜{end_idx}件目")
        else:
            st.markdown(f"**全{total_items}件**")
        
        # 表示用データ作成
        df_display = df_trans.copy()
        
        # 日時整形
        try:
            df_display['date'] = pd.to_datetime(df_display['date'])
        except:
            pass
            
        # 取引タイプにアイコンを追加
        df_display['type_display'] = df_display['type'].apply(
            lambda t: f"{TRANSACTION_TYPES[t]['icon']} {t}" if t in TRANSACTION_TYPES else t
        )
            
        # 通貨換算（表示用カラムに追加）
        df_display['display_price'] = df_display['price'] * exchange_rate
        df_display['display_total'] = df_display['total'] * exchange_rate

        # カラム設定
        column_config = {
            "date": st.column_config.DatetimeColumn(
                "Date",
                format="YYYY-MM-DD HH:mm",
                width="medium"
            ),
            "type_display": st.column_config.TextColumn(
                "Type",
                width="medium"
            ),
            "symbol": st.column_config.TextColumn(
                "Symbol",
                width="small"
            ),
            "quantity": st.column_config.NumberColumn(
                "Qty",
                format="%.8f",
                width="medium"
            ),
            "display_price": st.column_config.NumberColumn(
                f"Price ({currency_symbol})",
                format="%.8g" if currency == "USD" else "%.2f",
                width="medium"
            ),
            "display_total": st.column_config.NumberColumn(
                f"Total ({currency_symbol})",
                format="%.2f" if currency == "USD" else "%.0f",
                width="medium"
            ),
            "notes": st.column_config.TextColumn(
                "Notes",
                width="large"
            )
        }

        # セレクションモード有効化
        event = st.dataframe(
            df_display[['date', 'type_display', 'symbol', 'quantity', 'display_price', 'display_total', 'notes']],
            column_config=column_config,
            width='stretch',
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            height=500
        )

        # 選択された行の処理
        if event.selection.rows:
            selected_index = event.selection.rows[0]
            # df_displayから直接データを取得（ページネーション後のインデックス）
            selected_row = df_display.iloc[selected_index]
            # 元のトランザクションIDを取得
            s_id = int(selected_row['id'])
            s_date = selected_row['date']
            s_type = selected_row['type']
            s_asset_id = int(selected_row['asset_id'])
            s_quantity = selected_row['quantity']
            s_price = selected_row['price'] # 元のUSD価格
            s_notes = selected_row['notes'] if pd.notna(selected_row['notes']) else ""
            
            st.info(f"選択中: {s_type} {selected_row['symbol']} ({s_date})")
            
            col_edit, col_del = st.columns(2)
            with col_edit:
                 if st.button("選択した取引を編集", key=f"edit_sel_{s_id}", width='stretch'):
                     edit_transaction_dialog(s_id, s_date, s_type, s_asset_id, s_quantity, s_price, s_notes)
            with col_del:
                 if st.button("選択した取引を削除", key=f"del_sel_{s_id}", type="primary", width='stretch'):
                     st.session_state[f"confirm_del_trans_{s_id}"] = True
                     st.rerun()

            # 削除確認
            if st.session_state.get(f"confirm_del_trans_{s_id}"):
                st.warning(f"以下の取引を削除しますか？\n\n**{s_type} {selected_row['symbol']} - {s_quantity} units (ID: {s_id})**")
                cy, cn = st.columns([1, 4])
                with cy:
                    if st.button("はい", key=f"del_yes_{s_id}", type="primary"):
                        if delete_transaction(s_id):
                            st.success("削除しました")
                            del st.session_state[f"confirm_del_trans_{s_id}"]
                            time.sleep(0.5)  # 削除完了を確認
                            st.rerun()
                        else:
                            st.error("削除に失敗しました")
                with cn:
                    if st.button("キャンセル", key=f"del_no_{s_id}"):
                        del st.session_state[f"confirm_del_trans_{s_id}"]
                        st.rerun()
        else:
            st.write("👆 行をクリックすると編集・削除ができます")
        
        # CSVエクスポートボタン
        st.markdown("<br>", unsafe_allow_html=True)
        
        # 全トランザクションを取得してエクスポート
        all_trans = get_all_transactions("すべて")
        if all_trans:
            df_export = pd.DataFrame(all_trans, columns=['id', 'date', 'type', 'symbol', 'name', 'quantity', 'price_usd', 'total_usd', 'notes', 'asset_id'])
            csv = df_export.to_csv(index=False).encode('utf-8-sig')
            
            st.download_button(
                label="📥 CSVエクスポート",
                data=csv,
                file_name=f"transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                width='stretch',
            )
        else:
            st.button("📥 CSVエクスポート", disabled=True, width='stretch', help="取引データがありません")



# タブ2: 新規取引
# 注: 新規取引は常にUSD入力で固定（変換ロジックが複雑になるため）
with tab2:
    st.markdown("## 新しい取引を記録")
    st.caption("※ 取引の記録は常にUSDベースで行ってください。")
    st.markdown("<br>", unsafe_allow_html=True)
    
    assets = get_assets_list()
    
    if not assets:
        st.warning("⚠️ まず「資産管理」ページで暗号資産を登録してください。")
    else:
        with st.form("add_transaction_form"):
            st.markdown("### 取引情報")
            
            col1, col2 = st.columns(2)
            
            with col1:
                trans_date = st.date_input("取引日 *", value=datetime.now())
                trans_time = st.time_input("取引時刻 *", value=datetime.now().time())
                
                # 取引種類の選択（セレクトボックスに変更）
                type_options = []
                for t_type, t_info in TRANSACTION_TYPES.items():
                    type_options.append(f"{t_info['icon']} {t_info['label']}")
                
                type_keys = list(TRANSACTION_TYPES.keys())
                
                selected_type_display = st.selectbox(
                    "取引種類 *",
                    options=type_options,
                    help="取引の種類を選択してください"
                )
                
                # 選択された取引タイプを取得
                selected_type_idx = type_options.index(selected_type_display)
                trans_type = type_keys[selected_type_idx]
                
                # コストゼロ取引かどうかを判定
                is_zero_cost = is_cost_free_transaction(trans_type)
                
                if is_zero_cost:
                    st.info(f"💡 {TRANSACTION_TYPES[trans_type]['description']}")
            
            with col2:
                # 資産選択
                asset_options = {f"{symbol} - {name}": asset_id for asset_id, name, symbol in assets}
                selected_asset = st.selectbox("通貨 *", options=list(asset_options.keys()))
                asset_id = asset_options[selected_asset]
                
                quantity = st.number_input("数量 *", min_value=0.0, step=0.00000001, format="%.8f")
                
                # コストゼロ取引の場合は価格入力を無効化
                if is_zero_cost:
                    st.text_input(
                        "取得時単価 ($) *",
                        value="0.00 (コストゼロ取引)",
                        disabled=True,
                        help="この取引タイプでは価格は自動的に0になります"
                    )
                    price_per_unit = 0.0
                else:
                    price_per_unit = st.number_input(
                        "取得時単価 ($) *",
                        min_value=0.0,
                        step=0.00000001,
                        format="%.8f",
                        help="購入時の1通貨あたりのUSD価格"
                    )
            
            # 合計金額を自動計算
            total_amount = quantity * price_per_unit
            st.markdown(f"### 合計金額 (邦貨換算前): **${total_amount:,.2f}**")
            
            notes = st.text_area("メモ (任意)", placeholder="取引に関するメモを入力..")
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            submitted = st.form_submit_button("記録する", width='stretch')
            
            
            if submitted:
                # バリデーション（ゼロコスト取引の場合は価格チェックをスキップ）
                if quantity <= 0:
                    st.error("数量は0より大きい値を入力してください")
                elif not is_zero_cost and price_per_unit <= 0:
                    st.error("単価は0より大きい値を入力してください")
                else:
                    # 日時を結合
                    trans_datetime = datetime.combine(trans_date, trans_time)
                    
                    if add_transaction(trans_datetime, trans_type, asset_id, quantity, price_per_unit, total_amount, notes):
                        st.success(f"✅ {trans_type}取引を記録しました！")
                        st.balloons()
                    else:
                        st.error("記録に失敗しました")

# タブ3: 保有状況
with tab3:
    st.markdown("## 現在の保有状況")
    st.markdown("<br>", unsafe_allow_html=True)
    
    holdings = stats['holdings']
    
    if not holdings:
        st.info("現在保有している資産はありません。")
    else:
        # 保有状況をカード形式で表示
        cols_per_row = 4
        for i in range(0, len(holdings), cols_per_row):
            cols = st.columns(cols_per_row)
            for j, col in enumerate(cols):
                if i + j < len(holdings):
                    symbol, name, api_id, icon_url, quantity = holdings[i + j]
                    
                    with col:
                        st.markdown(f"""
                        <div class="crypto-card">
                            <div style="text-align: center;">
                                <img src="{icon_url}" 
                                     style="width: 64px; height: 64px; margin-bottom: 1rem; border-radius: 50%;" 
                                     onerror="this.style.display='none'; this.nextElementSibling.style.display='block';"
                                     alt="{symbol}">
                                <div style="font-size: 3rem; margin-bottom: 1rem; display:none;">{symbol[0]}</div>
                                <h3 style="margin-bottom: 0.5rem;">{symbol}</h3>
                                <p style="color: var(--text-muted); margin-bottom: 1rem;">{name}</p>
                                <div style="font-size: 2rem; font-weight: 700; color: var(--accent-primary);">
                                    {quantity:,.8f}
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

# フッター
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: var(--text-muted); font-size: 0.875rem;">
    <p>💡 取引はUSDベースで記録されます。表示通貨の切り替えは自動換算されます。</p>
</div>
""", unsafe_allow_html=True)
