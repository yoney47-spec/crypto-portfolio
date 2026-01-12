"""
暗号資産ポートフォリオアプリ - 設定ページ
"""

import streamlit as st
import requests
from pathlib import Path
from datetime import datetime
import time

# Import from Supabase adapter
from database_supabase import (
    get_portfolio_data,
    get_all_transactions, 
    get_latest_snapshot, 
    get_snapshot_count,
    save_portfolio_snapshot
)

# ページ設定
st.set_page_config(
    page_title="設定 - Crypto Portfolio",
    page_icon="S",
    layout="wide",
    initial_sidebar_state="expanded"
)

# カスタムCSSの読み込み
def load_css():
    css_file = Path(__file__).parent.parent / "styles" / "main.css"
    with open(css_file, encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css()

# ヘッダー
st.markdown("# ⚙️ 設定")
st.markdown("---")

# 統計情報取得（Supabase経由）
# get_portfolio_data returns (portfolio, asset_count, transaction_count)
_, asset_count, transaction_count = get_portfolio_data()
snapshot_count = get_snapshot_count()

# データベース概要
st.markdown("## 📊 データベース概要 (Cloud)")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">登録資産数</div>
        <div class="metric-value">{asset_count}</div>
        <div class="metric-label">Assets</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">取引記録数</div>
        <div class="metric-value">{transaction_count}</div>
        <div class="metric-label">Transactions</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">スナップショット</div>
        <div class="metric-value">{snapshot_count}</div>
        <div class="metric-label">Snapshots</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# バックアップセクション (Cloud版ではローカルダウンロード不可のため案内のみ)
st.markdown("## ☁️ データ管理")
st.info("データは Supabase (クラウドデータベース) に安全に保存されています。iPhoneやPCなど、どのデバイスからでも同じデータにアクセスできます。")

st.markdown("---")

# スナップショットセクション
st.markdown("## 📸 ポートフォリオスナップショット")
st.markdown("現在の総資産額を記録して、資産推移を追跡します。")

# 最新のスナップショット情報を表示
latest = get_latest_snapshot()
if latest:
    date_str = latest['date']
    val = latest['total_value_jpy']
    st.info(f"📅 最新のスナップショット: {date_str} (¥{val:,.0f})")
else:
    st.info("📅 まだスナップショットがありません")

col_snap1, col_snap2 = st.columns([2, 1])

with col_snap1:
    st.markdown("""
    💡 スナップショットを取得すると、現在の総資産額（JPY換算）がデータベースに保存されます。
    同じ日に複数回取得した場合は、最新の値で上書きされます。
    """)

with col_snap2:
    if st.button("📸 スナップショットを取得", width='stretch', type="primary"):
        with st.spinner("現在の資産額を計算中..."):
            try:
                # 現在のポートフォリオ価値を計算 (Supabaseから取得)
                portfolio, _, _ = get_portfolio_data() 
                # portfolio item: (id, symbol, name, api_id, icon_url, location, holdings)
                
                # 保有資産データを作成 {api_id: holdings}
                holdings_map = {}
                for item in portfolio:
                    api_id = item[3]
                    holdings = item[6]
                    if api_id:
                        holdings_map[api_id] = holdings_map.get(api_id, 0) + holdings
                
                if holdings_map:
                    # CoinGecko APIから現在価格を取得(JPY)
                    api_ids = list(holdings_map.keys())
                    
                    prices = {}
                    batch_size = 250
                    max_retries = 3
                    
                    for i in range(0, len(api_ids), batch_size):
                        batch = api_ids[i:i + batch_size]
                        
                        for attempt in range(max_retries):
                            try:
                                if i > 0 or attempt > 0:
                                    time.sleep(2)
                                
                                url = "https://api.coingecko.com/api/v3/simple/price"
                                params = {
                                    "ids": ",".join(batch),
                                    "vs_currencies": "jpy"
                                }
                                response = requests.get(url, params=params, timeout=15)
                                
                                if response.status_code == 429:
                                    wait_time = 2 ** (attempt + 1)
                                    st.info(f"⏳ APIレート制限中... {wait_time}秒後に再試行します")
                                    time.sleep(wait_time)
                                    continue
                                
                                response.raise_for_status()
                                batch_prices = response.json()
                                prices.update(batch_prices)
                                break
                                
                            except requests.exceptions.RequestException as e:
                                if attempt == max_retries - 1:
                                    st.warning(f"⚠️ 一部の価格取得に失敗: {batch}")
                    
                    if not prices:
                        st.error("❌ 価格データを取得できませんでした。しばらく待ってから再試行してください。")
                    else:
                        # 総資産額を計算
                        total_value_jpy = 0
                        for api_id, holdings in holdings_map.items():
                            if api_id in prices:
                                price_jpy = prices[api_id].get("jpy", 0)
                                total_value_jpy += holdings * price_jpy
                        
                        # スナップショットを保存
                        if save_portfolio_snapshot(total_value_jpy):
                            st.success(f"✅ スナップショットを保存しました！ (¥{total_value_jpy:,.0f})")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("❌ スナップショットの保存に失敗しました")
                else:
                    st.warning("⚠️ 保有資産がありません")
                    
            except Exception as e:
                st.error(f"❌ エラー: {str(e)}")

st.markdown("---")

# その他の設定
st.markdown("## 🔧 その他の設定")

st.markdown("### キャッシュ管理")
col_e, col_f = st.columns([2, 1])

with col_e:
    st.markdown("API価格データのキャッシュをクリアして、最新データを強制的に取得します。")

with col_f:
    if st.button("🗑️ キャッシュをクリア", width='stretch'):
        st.cache_data.clear()
        st.success("✅ キャッシュをクリアしました")
        time.sleep(0.5)
        st.rerun()

st.markdown("<br><br>", unsafe_allow_html=True)

# フッター
st.markdown("---")
st.caption("💡 データは Supabase Cloud に安全に保存されています。")
