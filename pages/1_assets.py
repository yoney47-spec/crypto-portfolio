"""
暗号資産ポートフォリオアプリ - 資産管理ページ
"""

import streamlit as st
import requests
from pathlib import Path
import base64
from io import BytesIO
from PIL import Image

# Import from Supabase adapter
from database_supabase import (
    get_all_assets, 
    add_asset, 
    delete_asset, 
    update_asset
)

# ページ設定
st.set_page_config(
    page_title="資産管理 - Crypto Portfolio",
    page_icon="A",
    layout="wide",
    initial_sidebar_state="expanded"
)

# カスタムCSSの読み込み
def load_css():
    css_file = Path(__file__).parent.parent / "styles" / "main.css"
    with open(css_file, encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css()

# --- サイドバー設定 ---
st.sidebar.markdown("### 設定")
currency = st.sidebar.radio(
    "表示通貨",
    ["USD", "JPY"],
    key="currency_selector",
    index=0
)
currency_symbol = "$" if currency == "USD" else "¥"
vs_currency = currency.lower()

# 画像を処理してBase64文字列に変換
def process_uploaded_image(uploaded_file):
    """アップロードされた画像をリサイズしてBase64文字列に変換"""
    try:
        image = Image.open(uploaded_file)
        
        # リサイズ (最大128x128)
        image.thumbnail((128, 128))
        
        # RGBモードに変換 (PNGの透過情報を保持する場合はRGBA)
        if image.mode != 'RGBA':
            image = image.convert('RGBA')
            
        # バッファに保存
        buffered = BytesIO()
        image.save(buffered, format="PNG")
        
        # Base64エンコード
        img_str = base64.b64encode(buffered.getvalue()).decode()
        return f"data:image/png;base64,{img_str}"
    except Exception as e:
        st.error(f"画像処理エラー: {e}")
        return None

# USD/JPY為替レート取得（CoinGecko以外のAPI）
def get_usd_jpy_rate():
    """USD/JPY為替レートを取得"""
    if "usd_jpy_rate" not in st.session_state:
        # 方法1: Open Exchange Rates API (無料)
        try:
            response = requests.get(
                "https://open.er-api.com/v6/latest/USD",
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if "rates" in data:
                    st.session_state.usd_jpy_rate = data["rates"].get("JPY", 155.0)
                    return st.session_state.usd_jpy_rate
        except:
            pass
        # フォールバック
        st.session_state.usd_jpy_rate = 155.0
    return st.session_state.usd_jpy_rate

# CoinGecko APIから価格を取得（バッチ処理 - USDのみ取得してJPYは計算）
def get_crypto_prices_batch(api_ids, force_refresh=False):
    """複数の暗号資産の価格を一度に取得してキャッシュ(USDのみ取得、JPYは計算)"""
    import time
    
    # セッションステートにキャッシュがあれば使用
    if "price_cache" not in st.session_state:
        st.session_state.price_cache = {}
    
    # 為替レートを取得
    usd_jpy_rate = get_usd_jpy_rate()
    
    # 強制更新の場合は全て再取得
    if force_refresh:
        ids_to_fetch = api_ids
    else:
        # まだ取得していないIDのみ取得
        ids_to_fetch = [id for id in api_ids if id not in st.session_state.price_cache]
    
    if ids_to_fetch:
        max_retries = 2
        retry_delay = 1  # 秒
        
        for attempt in range(max_retries):
            try:
                # USDのみ取得（JPYはレート計算で対応）
                url = "https://api.coingecko.com/api/v3/simple/price"
                params = {
                    "ids": ",".join(ids_to_fetch),
                    "vs_currencies": "usd",
                    "include_24hr_change": "true"
                }
                response = requests.get(url, params=params, timeout=10)
                
                # レート制限エラーの場合
                if response.status_code == 429:
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay * (attempt + 1))  # 指数バックオフ
                        continue
                    else:
                        st.warning("⚠️ CoinGecko APIのレート制限に達しました。数秒後に再度お試しください。")
                        # 既存のキャッシュがあればそれを使用
                        return st.session_state.price_cache
                
                response.raise_for_status()
                data = response.json()
                
                # キャッシュに保存(USDを取得し、JPYは計算)
                for api_id in ids_to_fetch:
                    if api_id in data:
                        usd_price = data[api_id].get("usd")
                        usd_change = data[api_id].get("usd_24h_change")
                        st.session_state.price_cache[api_id] = {
                            "usd": usd_price,
                            "jpy": usd_price * usd_jpy_rate if usd_price else None,
                            "usd_24h_change": usd_change,
                            "jpy_24h_change": usd_change  # 変動率はUSDと同じ
                        }
                    else:
                        st.session_state.price_cache[api_id] = {
                            "usd": None,
                            "jpy": None,
                            "usd_24h_change": None,
                            "jpy_24h_change": None
                        }
                
                # 成功したらループを抜ける
                if force_refresh:
                    st.success("✅ 価格を更新しました")
                break
                
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                else:
                    st.error(f"❌ 価格取得エラー: {str(e)}")
                    # エラー時は既存のキャッシュを保持
                    for api_id in ids_to_fetch:
                        if api_id not in st.session_state.price_cache:
                            st.session_state.price_cache[api_id] = {
                                "usd": None,
                                "jpy": None
                            }
            except Exception as e:
                st.error(f"❌ 予期しないエラー: {str(e)}")
                # エラー時は既存のキャッシュを保持
                for api_id in ids_to_fetch:
                    if api_id not in st.session_state.price_cache:
                        st.session_state.price_cache[api_id] = {
                            "usd": None,
                            "jpy": None,
                            "usd_24h_change": None,
                            "jpy_24h_change": None
                        }
                break
    
    return st.session_state.price_cache

def get_crypto_price(api_id):
    """単一の暗号資産価格を取得(キャッシュから) - USD & JPY"""
    if "price_cache" in st.session_state and api_id in st.session_state.price_cache:
        return st.session_state.price_cache[api_id]
    return {"usd": None, "jpy": None, "usd_24h_change": None, "jpy_24h_change": None}

# Note: create/update/delete functions are now imported

LOCATION_OPTIONS = [
    "未設定",
    "Tangem Wallet",
    "GMOコイン",
    "Metamask",
    "Phantom",
    "Bitget Wallet",
    "Qubic Wallet",
    "HashPort Wallet",
    "Other"
]

@st.dialog("資産の編集")
def edit_asset_dialog(asset_id, name, symbol, api_id, icon_url, location):
    """資産編集用ダイアログ"""
    with st.form(key=f"edit_form_{asset_id}"):
        edit_name = st.text_input("通貨名", value=name)
        edit_symbol = st.text_input("シンボル", value=symbol)
        edit_api_id = st.text_input("API ID", value=api_id)
        
        # 保管場所
        current_loc = location if location in LOCATION_OPTIONS else "Other"
        if location and location not in LOCATION_OPTIONS:
            LOCATION_OPTIONS.append(location) # 一時的に追加
            current_loc = location
            
        edit_location_select = st.selectbox("保管場所", options=LOCATION_OPTIONS, index=LOCATION_OPTIONS.index(current_loc) if current_loc in LOCATION_OPTIONS else 0)
        
        edit_location_input = ""
        if edit_location_select == "Other":
             edit_location_input = st.text_input("保管場所を入力", value=location if location not in LOCATION_OPTIONS else "")
        
        # 画像アップロード
        uploaded_file = st.file_uploader("アイコン画像 (任意)", type=['png', 'jpg', 'jpeg', 'webp'], key=f"uploader_{asset_id}")
        
        # URL入力（画像がない場合に使用）
        st.markdown("または")
        edit_icon_url = st.text_input("アイコンURL", value=icon_url or "", help="画像をアップロードしない場合はURLを使用します")
        
        col_save, col_cancel = st.columns(2)
        with col_save:
            if st.form_submit_button("保存", width='stretch'):
                # 画像がアップロードされた場合はそれを優先
                final_icon_url = edit_icon_url
                if uploaded_file is not None:
                    processed_image = process_uploaded_image(uploaded_file)
                    if processed_image:
                        final_icon_url = processed_image
                
                final_location = edit_location_input if edit_location_select == "Other" else edit_location_select
                if final_location == "未設定": final_location = ""

                if update_asset(asset_id, edit_name, edit_symbol, edit_api_id, final_icon_url, final_location):
                    st.success("更新しました")
                    st.rerun()
                else:
                    st.error("更新に失敗しました(シンボルが重複している可能性があります)")
        
        with col_cancel:
            if st.form_submit_button("キャンセル", width='stretch'):
                st.rerun()


# ヘッダー
st.markdown("# 資産管理")
st.markdown("保有している暗号資産の登録・編集・削除を行います")
st.markdown("---")

# タブで機能を分ける
tab1, tab2 = st.tabs(["資産一覧", "新規登録"])

# タブ1: 資産一覧
with tab1:
    st.markdown("## 登録済み資産")
    st.markdown("<br>", unsafe_allow_html=True)
    
    assets = get_all_assets()
    
    if not assets:
        st.info("まだ資産が登録されていません。「新規登録」タブから追加してください。")
    else:
        # 全資産のAPI IDを取得してバッチで価格を取得
        api_ids = [asset[3] for asset in assets]  # asset[3] is api_id
        get_crypto_prices_batch(api_ids)
        
        # 価格更新ボタン
        col_refresh, col_spacer = st.columns([1, 5])
        with col_refresh:
            if st.button("価格更新", width='stretch'):
                # 強制的に全ての価格を再取得
                with st.spinner("価格を更新中..."):
                    get_crypto_prices_batch(api_ids, force_refresh=True)
                st.rerun()
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # 資産をカード形式で表示
        cols_per_row = 4
        for i in range(0, len(assets), cols_per_row):
            cols = st.columns(cols_per_row)
            for j, col in enumerate(cols):
                if i + j < len(assets):
                    asset = assets[i + j]
                    # アンパック (location追加)
                    asset_id, name, symbol, api_id, icon_url, location, created_at = asset
                    
                    with col:
                        # 価格取得(USD & JPY)
                        prices = get_crypto_price(api_id)
                        
                        # 選択された通貨の価格を表示
                        target_price = prices.get(vs_currency)
                        
                        # 価格テキストの作成
                        if target_price:
                            if currency == "USD":
                                if target_price < 0.01 and target_price > 0:
                                    price_fmt = f"${target_price:.8f}".rstrip("0")
                                elif target_price < 1.0:
                                    price_fmt = f"${target_price:.4f}"
                                else:
                                    price_fmt = f"${target_price:,.2f}"
                            else:
                                if target_price < 1.0 and target_price > 0:
                                    price_fmt = f"¥{target_price:.4f}"
                                else:
                                    price_fmt = f"¥{target_price:,.0f}"
                            
                            # 24h変動の表示
                            change_key = f"{vs_currency}_24h_change"
                            change_val = prices.get(change_key)
                            
                            if change_val is not None:
                                change_color = "var(--accent-success)" if change_val >= 0 else "var(--accent-danger)"
                                change_icon = "▲" if change_val >= 0 else "▼"
                                change_fmt = f"""<div style="font-size: 0.85rem; color: {change_color}; font-weight: bold; text-align: center;">
    {change_icon} {abs(change_val):.2f}% (24h)
</div>"""
                            else:
                                change_fmt = ""

                            price_display = f"""<div style="font-size: 1.25rem; font-weight: 700; color: var(--accent-primary); margin-top: var(--spacing-sm); text-align: center;">
    {price_fmt}
</div>
{change_fmt}"""
                        else:
                            price_display = """<div style="font-size: 1rem; color: var(--text-muted); margin: var(--spacing-md) 0; text-align: center;">
    取得中...
</div>"""
                        
                        # アイコン表示の準備
                        if icon_url and icon_url.strip():
                            # アイコンURLがある場合は画像を表示（エラー時はシンボルにフォールバック）
                            icon_html = f'''<div style="width: 48px; height: 48px; margin: 0 auto; position: relative;">
                                <img src="{icon_url}" 
                                     style="width: 48px; height: 48px; border-radius: 50%; display: block; object-fit: cover;" 
                                     onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';" />
                                <div class="asset-icon" style="display: none; font-size: 1.1rem; font-weight: 700; position: absolute; top: 0; left: 0; width: 100%; height: 100%;">{symbol}</div>
                            </div>'''
                        else:
                            # アイコンURLがない場合はシンボルを表示
                            icon_html = f'<div class="asset-icon" style="font-size: 1.1rem; font-weight: 700;">{symbol}</div>'
                        
                        # カード表示
                        st.markdown(f"""
                        <div class="asset-card">
                            <div class="asset-card-content">
                                <div style="display: flex; justify-content: center; align-items: center; margin-bottom: var(--spacing-md);">
                                    {icon_html}
                                </div>
                                <div class="asset-symbol">{symbol}</div>
                                <div class="asset-name">{name}</div>
                                {price_display}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # 編集・削除ボタン
                        col_edit, col_delete = st.columns(2)
                        
                        with col_edit:
                            if st.button("編集", key=f"edit_{asset_id}", width='stretch'):
                                edit_asset_dialog(asset_id, name, symbol, api_id, icon_url, location)
                        
                        with col_delete:
                            if st.button("削除", key=f"delete_{asset_id}", width='stretch'):
                                st.session_state[f"confirm_delete_{asset_id}"] = True
                                st.rerun()
                        
                        # 削除確認ダイアログ
                        if st.session_state.get(f"confirm_delete_{asset_id}", False):
                            st.warning(f"本当に {name} ({symbol}) を削除しますか？")
                            col_yes, col_no = st.columns(2)
                            with col_yes:
                                if st.button("はい", key=f"confirm_yes_{asset_id}", width='stretch'):
                                    success, message = delete_asset(asset_id)
                                    if success:
                                        st.success(message)
                                        st.session_state[f"confirm_delete_{asset_id}"] = False
                                        st.rerun()
                                    else:
                                        st.error(message)
                            with col_no:
                                if st.button("いいえ", key=f"confirm_no_{asset_id}", width='stretch'):
                                    st.session_state[f"confirm_delete_{asset_id}"] = False
                                    st.rerun()

                        st.markdown("<br>", unsafe_allow_html=True)

# タブ2: 新規登録
with tab2:
    st.markdown("## 新しい資産を登録")
    st.markdown("<br>", unsafe_allow_html=True)
    
    # CoinGecko API IDの説明
    with st.expander("💡 CoinGecko API IDとは？", expanded=False):
        st.markdown("""
        **CoinGecko API ID**は、CoinGeckoが各暗号資産に割り当てた一意の識別子です。
        
        **よくある例**:
        - Bitcoin → `bitcoin`
        - Ethereum → `ethereum`
        - Ripple → `ripple`
        - Cardano → `cardano`
        - Solana → `solana`
        - Polygon → `matic-network`
        - Dogecoin → `dogecoin`
        
        **⚠️ 注意**: コントラクトアドレス（`0x...`）ではありません！
        
        **調べ方**:
        1. [CoinGecko](https://www.coingecko.com/)で通貨を検索
        2. 通貨ページのURLを確認: `https://www.coingecko.com/ja/coins/〈ここがAPI ID〉`
        
        例: Bitcoin のURL → `https://www.coingecko.com/ja/coins/bitcoin`  
        → API ID は `bitcoin`
        """)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    with st.form("add_asset_form"):
        st.markdown("### 基本情報")
        
        col1, col2 = st.columns(2)
        with col1:
            new_name = st.text_input(
                "通貨名 *", 
                placeholder="例: Bitcoin",
                help="暗号資産の正式名称を入力してください"
            )
            new_symbol = st.text_input(
                "シンボル *", 
                placeholder="例: BTC",
                help="通貨のティッカーシンボル（通常は大文字）"
            )
        
        with col2:
            new_api_id = st.text_input(
                "CoinGecko API ID *", 
                placeholder="例: bitcoin",
                help="CoinGeckoのAPI ID（通常は小文字、ハイフン区切り）。上の説明を参照してください。"
            )
            
            # 画像アップロード
            uploaded_file = st.file_uploader("アイコン画像 (任意)", type=['png', 'jpg', 'jpeg', 'webp'])
            
            # URL入力は折りたたみ
            with st.expander("または画像URLを入力"):
                new_icon_url = st.text_input(
                    "アイコンURL", 
                    placeholder="https://...",
                    help="画像をアップロードしない場合はこちらに入力"
                )
            
            # 保管場所
            LOCATION_OPTIONS = [
                "未設定",
                "Tangem Wallet",
                "GMOコイン",
                "Metamask",
                "Phantom",
                "Bitget Wallet",
                "Qubic Wallet",
                "HashPort Wallet",
                "Other"
            ]
            new_location_select = st.selectbox("保管場所", options=LOCATION_OPTIONS)
            new_location_input = ""
            if new_location_select == "Other":
                new_location_input = st.text_input("保管場所を入力")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # 検索リンク
        st.markdown("""
        <div style="text-align: center; padding: 1rem; background-color: var(--bg-secondary); border-radius: var(--radius-md); margin-bottom: 1rem;">
            <p style="margin: 0; color: var(--text-secondary);">
                🔍 <a href="https://www.coingecko.com/ja" target="_blank" style="color: var(--accent-primary); text-decoration: none;">
                    CoinGeckoで通貨を検索 →
                </a>
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        submitted = st.form_submit_button("登録する", width='stretch')
        
        if submitted:
            if not new_name or not new_symbol or not new_api_id:
                st.error("❌ 必須項目（*印）を全て入力してください")
            else:
                # 画像処理
                final_icon_url = new_icon_url
                if uploaded_file is not None:
                    processed_image = process_uploaded_image(uploaded_file)
                    if processed_image:
                        final_icon_url = processed_image
                
                final_location = new_location_input if new_location_select == "Other" else new_location_select
                if final_location == "未設定": final_location = ""

                if add_asset(new_name, new_symbol, new_api_id, final_icon_url, final_location):
                    st.success(f"✅ {new_name} ({new_symbol}) を登録しました！")
                    st.balloons()
                else:
                    st.error("❌ 登録に失敗しました。シンボルが既に登録されている可能性があります。")

# フッター
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: var(--text-muted); font-size: 0.875rem;">
    <p>💡 CoinGecko APIを使用してリアルタイム価格を取得しています</p>
</div>
""", unsafe_allow_html=True)
