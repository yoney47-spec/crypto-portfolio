"""
暗号資産ポートフォリオアプリ - 設定ページ
"""

import streamlit as st
import sqlite3
from pathlib import Path
from database import DB_PATH
from datetime import datetime
import shutil

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

# データベース情報
with sqlite3.connect(DB_PATH) as conn:
    cursor = conn.cursor()
    
    # 統計情報取得
    cursor.execute("SELECT COUNT(*) FROM assets")
    asset_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM transactions")
    transaction_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM portfolio_snapshots")
    snapshot_count = cursor.fetchone()[0]

# データベース概要
st.markdown("## 📊 データベース概要")

col1, col2, col3, col4 = st.columns(4)

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

with col4:
    # DBファイルサイズ
    db_size = Path(DB_PATH).stat().st_size / 1024  # KB
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">DBサイズ</div>
        <div class="metric-value">{db_size:.1f}</div>
        <div class="metric-label">KB</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# バックアップ/リストアセクション
st.markdown("## 💾 バックアップ/リストア")

tab1, tab2 = st.tabs(["📥 バックアップ（ダウンロード）", "📤 リストア（復元）"])

with tab1:
    st.markdown("### データベースのバックアップ")
    st.markdown("現在のデータベースをファイルとしてダウンロードします。定期的なバックアップを推奨します。")
    
    col_a, col_b = st.columns([2, 1])
    
    with col_a:
        st.info("💡 バックアップファイルは安全な場所に保管してください。")
    
    with col_b:
        # バックアップファイル名生成
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"crypto_portfolio_backup_{timestamp}.db"
        
        # DBファイルを読み込み
        with open(DB_PATH, "rb") as f:
            db_data = f.read()
        
        st.download_button(
            label="📥 バックアップをダウンロード",
            data=db_data,
            file_name=backup_filename,
            mime="application/octet-stream",
            width='stretch',
            type="primary"
        )

with tab2:
    st.markdown("### データベースの復元")
    st.warning("⚠️ 復元すると**現在のデータは完全に上書き**されます。必ず事前にバックアップを取得してください。")
    
    uploaded_file = st.file_uploader(
        "バックアップファイルを選択",
        type=["db"],
        help="以前ダウンロードしたバックアップファイル（.db）を選択してください"
    )
    
    if uploaded_file is not None:
        st.info(f"📁 選択されたファイル: {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")
        
        col_c, col_d = st.columns([1, 1])
        
        with col_c:
            if st.button("🔄 復元を実行", type="primary", width='stretch'):
                try:
                    with st.spinner("復元中..."):
                        # 現在のDBのバックアップを作成（安全のため）
                        backup_path = DB_PATH.parent / f"backup_before_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
                        shutil.copy2(DB_PATH, backup_path)
                        
                        # アップロードされたファイルで上書き
                        with open(DB_PATH, "wb") as f:
                            f.write(uploaded_file.getvalue())
                        
                        st.success(f"✅ 復元が完了しました！\n\n元のデータは `{backup_path.name}` に保存されています。")
                        st.info("🔄 ページをリロードして変更を確認してください。")
                        
                except Exception as e:
                    st.error(f"❌ 復元エラー: {str(e)}")
        
        with col_d:
            if st.button("キャンセル", width='stretch'):
                st.rerun()

st.markdown("---")

# スナップショットセクション
st.markdown("## 📸 ポートフォリオスナップショット")
st.markdown("現在の総資産額を記録して、資産推移を追跡します。")

# スナップショット管理のインポート
from snapshot_manager import save_portfolio_snapshot, get_latest_snapshot, get_snapshot_count
import requests

# 最新のスナップショット情報を表示
latest = get_latest_snapshot()
if latest:
    st.info(f"📅 最新のスナップショット: {latest['date']} (¥{latest['total_value_jpy']:,.0f})")
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
                # 現在のポートフォリオ価値を計算(JPY)
                with sqlite3.connect(DB_PATH) as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT 
                            a.api_id,
                            COALESCE(SUM(CASE WHEN t.type = 'Buy' THEN t.quantity ELSE -t.quantity END), 0) as holdings
                        FROM assets a
                        LEFT JOIN transactions t ON a.id = t.asset_id
                        GROUP BY a.api_id
                        HAVING holdings > 0
                    """)
                    holdings_data = cursor.fetchall()
                
                # CoinGecko APIから現在価格を取得(JPY) - バッチ処理でレート制限回避
                api_ids = [item[0] for item in holdings_data if item[0]]
                
                if api_ids:
                    import time
                    prices = {}
                    batch_size = 250  # 1回のAPI呼び出しで250件まで取得可能
                    max_retries = 3
                    
                    for i in range(0, len(api_ids), batch_size):
                        batch = api_ids[i:i + batch_size]
                        
                        for attempt in range(max_retries):
                            try:
                                # リクエスト間に待機時間を設ける
                                if i > 0 or attempt > 0:
                                    time.sleep(2)  # 2秒待機
                                
                                url = "https://api.coingecko.com/api/v3/simple/price"
                                params = {
                                    "ids": ",".join(batch),
                                    "vs_currencies": "jpy"
                                }
                                response = requests.get(url, params=params, timeout=15)
                                
                                if response.status_code == 429:
                                    # レート制限: 指数バックオフで待機
                                    wait_time = 2 ** (attempt + 1)  # 2, 4, 8秒
                                    st.info(f"⏳ APIレート制限中... {wait_time}秒後に再試行します")
                                    time.sleep(wait_time)
                                    continue
                                
                                response.raise_for_status()
                                batch_prices = response.json()
                                prices.update(batch_prices)
                                break  # 成功したらループを抜ける
                                
                            except requests.exceptions.RequestException as e:
                                if attempt == max_retries - 1:
                                    st.warning(f"⚠️ 一部の価格取得に失敗: {batch}")
                    
                    if not prices:
                        st.error("❌ 価格データを取得できませんでした。しばらく待ってから再試行してください。")
                    else:
                        # 総資産額を計算
                        total_value_jpy = 0
                        for api_id, holdings in holdings_data:
                            if api_id and api_id in prices:
                                price_jpy = prices[api_id].get("jpy", 0)
                                total_value_jpy += holdings * price_jpy
                        
                        # スナップショットを保存
                        if save_portfolio_snapshot(total_value_jpy):
                            st.success(f"✅ スナップショットを保存しました！ (¥{total_value_jpy:,.0f})")
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
        st.rerun()

st.markdown("<br><br>", unsafe_allow_html=True)

# フッター
st.markdown("---")
st.caption("💡 データは安全に管理されています。定期的なバックアップをお勧めします。")
