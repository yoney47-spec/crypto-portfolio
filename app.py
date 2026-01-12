"""
暗号資産ポートフォリオアプリ - ダッシュボード
"""

import streamlit as st
import requests
import time
from pathlib import Path
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, timedelta
# Import from new Supabase adapter
from database_supabase import (
    get_portfolio_data, 
    calculate_cost_basis, 
    get_current_year_investment_sales,
    get_portfolio_history
)

# ページ設定
st.set_page_config(
    page_title="Crypto Portfolio Dashboard",
    page_icon="C",
    layout="wide",
    initial_sidebar_state="collapsed"  # Mobile-first: sidebar collapsed by default
)

# カスタムCSSの読み込み
def load_css():
    css_file = Path(__file__).parent / "styles" / "main.css"
    with open(css_file) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css()

# Mobile viewport meta tag for proper iPhone scaling
st.markdown("""
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
""", unsafe_allow_html=True)

# --- サイドバー設定 ---
st.sidebar.markdown("### 設定")
if st.sidebar.button("データ更新", width='stretch'):
    with st.spinner('キャッシュをクリア中...'):
        st.cache_data.clear()
    st.sidebar.success("データを更新しました")
    st.rerun()

currency = st.sidebar.radio(
    "表示通貨",
    ["USD", "JPY"],
    key="currency_selector",
    index=0
)
currency_symbol = "$" if currency == "USD" else "¥"
vs_currency = currency.lower()

# --- データ取得ロジック ---
# Note: get_portfolio_data and calculate_cost_basis are now imported from database_supabase

# 現在価格の取得 (USD/JPY) - キャッシュ有効化 (TTL: 60秒)
@st.cache_data(ttl=1800)  # 30分キャッシュ（APIレート制限対策）
def fetch_current_prices(api_ids, vs_curr="usd"):
    """CoinGecko APIから現在価格を取得"""
    if not api_ids:
        return {}
    
    # 常にUSDも含める（P/L計算に必要）
    currencies = f"usd,{vs_curr}" if vs_curr != "usd" else "usd"
        
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": ",".join(api_ids),
        "vs_currencies": currencies,
        "include_24hr_change": "true"
    }
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 429:
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # 1s, 2s, 4s wait
                    continue
                return None
                
            response.raise_for_status()
            return response.json()
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            return None
    return None

# 過去の価格チャートデータを取得 (キャッシュ無効化: エラー時のNoneキャッシュを防ぐため)
def fetch_market_chart(api_id, vs_curr="usd", days=7):
    """CoinGecko APIから過去の価格データを取得"""
    if not api_id:
        return None

    url = f"https://api.coingecko.com/api/v3/coins/{api_id}/market_chart"
    params = {
        "vs_currency": vs_curr,
        "days": days
    }
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # 少し待機 (連打防止)
            if attempt == 0:
                time.sleep(0.5)
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 429:
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt + 1)
                    continue
                return None
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            print(f"[ERROR] API呼び出し失敗 (fetch_market_chart): {str(e)}")
            return None
        except Exception as e:
            print(f"[ERROR] 予期しないエラー (fetch_market_chart): {str(e)}")
            return None
    return None


# 為替レート(USDT/JPY)の履歴を取得 - キャッシュ有効化 (TTL: 1時間)
@st.cache_data(ttl=3600)
def fetch_exchange_rate_history(days=30):
    """CoinGecko APIからUSDT/JPYの履歴を取得してドル円レートの代用とする"""
    url = "https://api.coingecko.com/api/v3/coins/tether/market_chart"
    params = {
        "vs_currency": "jpy",
        "days": days
    }
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            time.sleep(1)
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 429:
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return None
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            print(f"[ERROR] 為替レート取得失敗: {str(e)}")
            return None
        except Exception as e:
            print(f"[ERROR] 予期しないエラー (exchange_rate): {str(e)}")
            return None
    return None

# データを取得
portfolio_data, asset_count, transaction_count = get_portfolio_data()

# API IDリスト作成
api_ids = [item[3] for item in portfolio_data if item[3]]

# 価格取得 (選択された通貨で) - スピナー表示
with st.spinner('最新価格を取得中...'):
    current_prices = fetch_current_prices(api_ids, vs_curr=vs_currency)

if current_prices is None:
    st.warning("APIレート制限により、最新価格が取得できませんでした。しばらく待ってから「データ更新」ボタンを押してください。")
    current_prices = {}

# 為替レート取得（JPY表示時の損益計算用）
exchange_rate = 1.0  # デフォルトはUSD
if vs_currency == "jpy":
    with st.spinner('為替レートを取得中...'):
        # 最新の為替レートを取得
        exchange_data = fetch_exchange_rate_history(days=1)
        if exchange_data and 'prices' in exchange_data and exchange_data['prices']:
            exchange_rate = exchange_data['prices'][-1][1]  # 最新のレート
        else:
            exchange_rate = 150.0  # フォールバック値


# 総資産額の計算とチャート用データ作成
total_portfolio_value = 0
portfolio_display_data = []

# コストベースデータを取得
cost_basis_data = calculate_cost_basis()

for item in portfolio_data:
    p_id, symbol, name, api_id, icon_url, location, holdings = item
    
    # 価格データの抽出
    price_data = current_prices.get(api_id, {})
    price = price_data.get(vs_currency, 0)
    
    # 評価額計算
    value = holdings * price
    total_portfolio_value += value
    
    # コストベース情報の取得
    cb = cost_basis_data.get(p_id, {})
    avg_cost = cb.get('avg_cost', 0)
    total_cost = cb.get('total_cost', 0)
    
    # 損益率と未実現損益の計算 (USDベース)
    if avg_cost > 0:
        # 現在価格をUSDで取得（損益計算は常にUSDベース）
        price_usd = current_prices.get(api_id, {}).get('usd', 0)
        value_usd = holdings * price_usd
        unrealized_pl = value_usd - total_cost
        pl_percent = ((price_usd - avg_cost) / avg_cost) * 100
    else:
        unrealized_pl = 0
        pl_percent = 0
    
    portfolio_display_data.append({
        "id": p_id,
        "symbol": symbol,
        "name": name,
        "api_id": api_id,
        "icon_url": icon_url,
        "location": location,
        "holdings": holdings,
        "price": price,
        "value": value,
        "avg_cost": avg_cost,
        "pl_percent": pl_percent,
        "unrealized_pl": unrealized_pl
    })

# 今年の取引のみの投資額と売却額を計算（含み益計算用）
from datetime import datetime
current_year = datetime.now().year

# Use helper from database_supabase
total_investment_this_year, total_sales_this_year = get_current_year_investment_sales()

# 価格フォーマット用ヘルパー関数
def format_price(val, currency="USD"):
    """通貨に応じて価格をフォーマット"""
    if val is None:
        return "-"
    
    if currency == "USD":
        if val < 0.01 and val > 0:
            return f"${val:.6f}".rstrip("0").rstrip(".")
        elif val < 1.0:
            return f"${val:.4f}"
        elif val < 1000:
            return f"${val:,.2f}"
        else:
            return f"${val:,.0f}"
    else:  # JPY
        if val < 1.0 and val > 0:
            return f"¥{val:.2f}"
        else:
            return f"¥{val:,.0f}"

# ヘッダー
st.markdown("# Crypto Portfolio Dashboard")
st.markdown("---")

# 総損益の計算（含み益のみ、今年の取引ベース）
# まず、現在のポートフォリオ価値をUSDで計算
total_portfolio_value_usd = 0
for item in portfolio_display_data:
    api_id = item['api_id']
    holdings = item['holdings']
    price_data = current_prices.get(api_id, {})
    price_usd = price_data.get('usd', 0)  # 常にUSD価格を使用
    total_portfolio_value_usd += holdings * price_usd

# 含み益（USD）= 現在の保有資産価値 - (今年の投資額 - 今年の売却額)
net_investment_this_year = total_investment_this_year - total_sales_this_year
total_pl_usd = total_portfolio_value_usd - net_investment_this_year
total_pl_percent = (total_pl_usd / net_investment_this_year * 100) if net_investment_this_year > 0 else 0

# 表示用に選択された通貨に換算
if vs_currency == "jpy":
    total_pl_display = total_pl_usd * exchange_rate
else:
    total_pl_display = total_pl_usd

# 24時間変動の計算（全資産の24h変動を合計）
portfolio_24h_change = 0
for item in portfolio_display_data:
    value = item['value']
    api_id = item['api_id']
    price_data = current_prices.get(api_id, {})
    change_key = f"{vs_currency}_24h_change"
    change_percent = price_data.get(change_key, 0) or 0
    portfolio_24h_change += value * (change_percent / 100)

portfolio_24h_percent = (portfolio_24h_change / total_portfolio_value * 100) if total_portfolio_value > 0 else 0

# 最高値・最安値の資産を特定
top_performer = max(portfolio_display_data, key=lambda x: current_prices.get(x['api_id'], {}).get(f'{vs_currency}_24h_change', 0) or 0) if portfolio_display_data else None
worst_performer = min(portfolio_display_data, key=lambda x: current_prices.get(x['api_id'], {}).get(f'{vs_currency}_24h_change', 0) or 0) if portfolio_display_data else None

st.markdown("<br>", unsafe_allow_html=True)

# メトリクスエリア（上部）- 6カラムに拡張
col1, col2, col3, col4, col5, col6 = st.columns(6)

with col1:
    st.markdown(f"""
    <div class="metric-card" style="border-color: var(--accent-primary); box-shadow: 0 0 15px rgba(0, 217, 255, 0.1);">
        <div class="metric-label">総資産額 ({currency})</div>
        <div class="metric-value">{currency_symbol}{total_portfolio_value:,.0f}</div>
        <div class="metric-label">Total Value</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    pl_color = "var(--accent-success)" if total_pl_usd >= 0 else "var(--accent-danger)"
    pl_icon = "▲" if total_pl_usd >= 0 else "▼"
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">総損益 (P/L)</div>
        <div class="metric-value" style="color: {pl_color};">{pl_icon} {abs(total_pl_percent):.1f}%</div>
        <div class="metric-label" style="font-size: 0.7rem;">{currency_symbol}{abs(total_pl_display):,.0f}</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    change_color = "var(--accent-success)" if portfolio_24h_change >= 0 else "var(--accent-danger)"
    change_icon = "▲" if portfolio_24h_change >= 0 else "▼"
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">24h 変動</div>
        <div class="metric-value" style="color: {change_color};">{change_icon} {abs(portfolio_24h_percent):.2f}%</div>
        <div class="metric-label" style="font-size: 0.7rem;">{currency_symbol}{abs(portfolio_24h_change):,.0f}</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">保有銘柄数</div>
        <div class="metric-value">{len(portfolio_data)}</div>
        <div class="metric-label">Assets</div>
    </div>
    """, unsafe_allow_html=True)

with col5:
    if top_performer:
        top_change = current_prices.get(top_performer['api_id'], {}).get(f"{vs_currency}_24h_change", 0) or 0
        st.markdown(f"""
        <div class="metric-card" style="border-color: var(--accent-success);">
            <div class="metric-label">最高値 (24h)</div>
            <div class="metric-value" style="font-size: 1.2rem; color: var(--accent-success);">{top_performer['symbol']}</div>
            <div class="metric-label" style="color: var(--accent-success);">▲ {top_change:.1f}%</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("<div class='metric-card'><div class='metric-label'>-</div></div>", unsafe_allow_html=True)

with col6:
    if worst_performer:
        worst_change = current_prices.get(worst_performer['api_id'], {}).get(f"{vs_currency}_24h_change", 0) or 0
        st.markdown(f"""
        <div class="metric-card" style="border-color: var(--accent-danger);">
            <div class="metric-label">最安値 (24h)</div>
            <div class="metric-value" style="font-size: 1.2rem; color: var(--accent-danger);">{worst_performer['symbol']}</div>
            <div class="metric-label" style="color: var(--accent-danger);">▼ {abs(worst_change):.1f}%</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("<div class='metric-card'><div class='metric-label'>-</div></div>", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# --- チャートセクション ---
if portfolio_display_data:
    st.markdown("### Portfolio Analysis")
    
    chart_col1, chart_col2, chart_col3 = st.columns(3)
    
    # 暗号資産のブランドカラーマッピング
    CRYPTO_COLORS = {
        'BTC': '#F7931A',      # Bitcoin - Orange
        'ETH': '#627EEA',      # Ethereum - Purple
        'XRP': '#00AAE4',      # Ripple - Blue
        'ADA': '#0033AD',      # Cardano - Blue
        'SOL': '#14F195',      # Solana - Green/Cyan
        'DOT': '#E6007A',      # Polkadot - Pink
        'DOGE': '#C2A633',     # Dogecoin - Gold
        'MATIC': '#8247E5',    # Polygon - Purple
        'AVAX': '#E84142',     # Avalanche - Red
        'LINK': '#2A5ADA',     # Chainlink - Blue
        'UNI': '#FF007A',      # Uniswap - Pink
        'LTC': '#345D9D',      # Litecoin - Blue
        'BCH': '#8DC351',      # Bitcoin Cash - Green
        'ATOM': '#2E3148',     # Cosmos - Dark Blue
        'XLM': '#000000',      # Stellar - Black
        'TRX': '#FF060A',      # Tron - Red
        'ETC': '#669073',      # Ethereum Classic - Green
        'VET': '#15BDFF',      # VeChain - Blue
        'FIL': '#0090FF',      # Filecoin - Blue
        'ALGO': '#000000',     # Algorand - Black
        'HBAR': '#000000',     # Hedera - Black
        'SHIB': '#FFA409',     # Shiba Inu - Orange
        'NEAR': '#000000',     # NEAR - Black
        'AAVE': '#B6509E',     # Aave - Purple
        'SAND': '#00ADEF',     # Sandbox - Blue
        'MANA': '#FF2D55',     # Decentraland - Red
        'AXS': '#0055D5',      # Axie Infinity - Blue
        'CAKE': '#633001',     # PancakeSwap - Brown
        'RUNE': '#00CCAB',     # THORChain - Teal
        'FTM': '#13B5EC',      # Fantom - Blue
        'KAS': '#49D9B3',      # Kaspa - Teal/Green
        'QUBIC': '#00D9FF',    # Qubic - Cyan
        'PEPU': '#4CAF50',     # Pepe Unchained - Green
        'SP': '#FFB800',       # Smart Pocket - Yellow
        'TGT': '#E84142',      # Tokyo Games Token - Red
        'PKM': '#FFA726',      # Pocketmy - Orange
        'HOLY': '#9C27B0',     # Holy Coin - Purple
        'AMATO': '#FF4B6E',    # AMATO - Pink/Red
        'MON': '#7B68EE',      # Monad - Purple
        'SOSO': '#FF6B6B',     # SosoValue - Red
        'HYPE': '#00D9FF',     # Hyperliquid - Cyan
    }
    
    # フォールバックカラーパレット
    fallback_colors = [
        '#00d9ff', '#7000ff', '#ff00aa', '#00ff9d', '#ffcc00', 
        '#ff4b4b', '#2e2e2e', '#575757', '#888888', '#aaaaaa'
    ]
    
    # データを価値順にソート (全体で使用)
    sorted_data = sorted(portfolio_display_data, key=lambda x: x['value'], reverse=True)
    
    # 色の割り当て (シンボル -> 色)
    color_map = {}
    for i, item in enumerate(sorted_data):
        symbol = item['symbol']
        # ブランドカラーがあればそれを使用、なければフォールバックカラー
        color = CRYPTO_COLORS.get(symbol, fallback_colors[i % len(fallback_colors)])
        color_map[symbol] = color

    # 1. ポートフォリオ構成比（ドーナツチャート）
    with chart_col1:
        # 総ポートフォリオ価値を計算
        total_value = sum(item['value'] for item in sorted_data)
        
        # 1%未満の資産を「その他」にまとめる
        threshold = total_value * 0.01  # 1%の閾値
        main_assets = []
        others_value = 0
        
        for item in sorted_data:
            if item['value'] >= threshold:
                main_assets.append(item)
            else:
                others_value += item['value']
        
        # ラベルと値を準備
        labels = [item['symbol'] for item in main_assets]
        values = [item['value'] for item in main_assets]
        colors = [color_map[s] for s in labels]
        
        # 「その他」を追加（存在する場合）
        if others_value > 0:
            labels.append('その他')
            values.append(others_value)
            colors.append('#666666')  # グレー色
        
        # Plotlyチャート作成
        fig_donut = go.Figure(data=[go.Pie(
            labels=labels, 
            values=values, 
            hole=.6,
            textinfo='none',
            sort=False, # 既にソート済みなので自動ソート無効化
            direction='clockwise',
            rotation=0, # 12時方向 (Plotlyの0度は12時)
            marker=dict(colors=colors)
        )])
        
        fig_donut.update_layout(
            title=dict(
                text="Allocation",
                font=dict(color="#ffffff", size=14),
                y=0.98,
                x=0.5,
                xanchor='center',
                yanchor='top'
            ),
            showlegend=True,
            legend=dict(
                font=dict(color="#ffffff", size=10),
                orientation="h",
                yanchor="top",
                y=-0.1,
                xanchor="center",
                x=0.5
            ),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(t=40, b=50, l=20, r=20),
            height=300
        )
        
        fig_donut.update_traces(
            hoverinfo='label+value+percent', 
            textfont_size=12,
            marker=dict(line=dict(color='#0E1117', width=2))
        )
        
        st.plotly_chart(fig_donut, width='stretch')

    # 2. トップ保有資産比較 (棒グラフ)
    with chart_col2:
        # 保有資産数に応じて表示数を動的調整（最大10件、最小3件）
        total_assets = len(sorted_data)
        display_count = min(10, max(3, total_assets))  # 3-10の範囲で調整
        
        top_n = sorted_data[:display_count]
        top_symbols = [item['symbol'] for item in top_n][::-1] # 逆順にして上から多い順に
        top_values = [item['value'] for item in top_n][::-1]
        top_colors = [color_map.get(s, '#666666') for s in top_symbols]  # 「その他」対応
        
        fig_bar = go.Figure(go.Bar(
            x=top_values,
            y=top_symbols,
            orientation='h',
            marker=dict(
                color=top_colors,
                showscale=False
            ),
            hoverinfo='x+y',
            textposition='none' 
        ))
        
        fig_bar.update_layout(
            title=dict(
                text="Top Assets by Value",
                font=dict(color="#ffffff", size=14),
                y=0.98,
                x=0.5,
                xanchor='center',
                yanchor='top'
            ),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(showgrid=False, showticklabels=False),
            yaxis=dict(showgrid=False, tickfont=dict(color='#ffffff')),
            margin=dict(t=40, b=10, l=10, r=10),
            height=300
        )
        
        st.plotly_chart(fig_bar, width='stretch')

    # 3. ポートフォリオ履歴チャート（簡略版）
    with chart_col3:
        # get_portfolio_history is imported at top
        
        snapshot_data = get_portfolio_history(days=365)
        if snapshot_data:
            hist_dates = [datetime.fromisoformat(s[0]) for s in snapshot_data]
            hist_values = [s[1] for s in snapshot_data]
            
            # 変化率の計算
            if len(hist_values) >= 2:
                first_val = hist_values[0]
                last_val = hist_values[-1]
                change_pct = ((last_val - first_val) / first_val) * 100 if first_val > 0 else 0
                change_color = "#00ff9d" if change_pct >= 0 else "#ff4b4b"
                change_sign = "+" if change_pct >= 0 else ""
            else:
                change_pct = 0
                change_color = "#888"
                change_sign = ""
            
            fig_hist = go.Figure()
            
            fig_hist.add_trace(go.Scatter(
                x=hist_dates, 
                y=hist_values,
                mode='lines+markers',
                name='Portfolio Value',
                line=dict(color='#00d9ff', width=2),
                marker=dict(size=4, color='#00d9ff'),
                fill='tozeroy',
                fillcolor='rgba(0, 217, 255, 0.1)'
            ))
            
            fig_hist.update_layout(
                title=dict(
                    text=f"Portfolio History ({change_sign}{change_pct:.1f}%)",
                    font=dict(color="#ffffff", size=14),
                    y=0.98,
                    x=0.5,
                    xanchor='center',
                    yanchor='top'
                ),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(
                    showgrid=False, 
                    tickfont=dict(color='#888', size=8),
                    linecolor='#333'
                ),
                yaxis=dict(
                    showgrid=True, 
                    gridcolor='#333', 
                    tickfont=dict(color='#888', size=8),
                    tickprefix="$"
                ),
                margin=dict(t=40, b=10, l=10, r=10),
                height=300,
                showlegend=False
            )
            
            st.plotly_chart(fig_hist, width='stretch')
        else:
            st.info("No history data available.")




    st.markdown("<br>", unsafe_allow_html=True)
    
    # 3. 価格推移チャート（フルワイド版 - Price Trend）
    st.markdown(f"""
    <div style="margin-bottom: 10px;">
        <span style="font-size: 1.2rem; font-weight: bold;">Asset Price Trend</span>
        <span style="font-size: 0.9rem; color: var(--text-muted); margin-left: 10px;">Historical price movement</span>
    </div>
    """, unsafe_allow_html=True)
    
    # 資産選択と期間選択を横並びに
    select_col1, select_col2 = st.columns([3, 1])
    
    with select_col1:
        # 資産選択 (シングル選択)
        asset_options = {item['symbol']: item['api_id'] for item in sorted_data}
        default_selection = list(asset_options.keys())[0] if asset_options else None
        selected_symbol = st.selectbox(
            "Select Asset", 
            options=list(asset_options.keys()), 
            index=0 if asset_options else None,
            key="price_trend_asset"
        )
    
    with select_col2:
        # 期間選択
        timeframe = st.select_slider(
            "Timeframe", 
            options=["1h", "4h", "1d", "7d", "1m", "3m", "1y"], 
            value="1m",
            key="price_trend_timeframe"
        )
    
    # 期間に応じたパラメータ設定
    days_param = 7
    if timeframe == "1y": days_param = 365
    elif timeframe == "3m": days_param = 90
    elif timeframe == "1m": days_param = 30
    elif timeframe == "7d": days_param = 7
    elif timeframe == "1d": days_param = 1
    elif timeframe == "4h": days_param = 1
    elif timeframe == "1h": days_param = 1
    
    if selected_symbol:
        selected_api_id = asset_options[selected_symbol]
        
        if selected_api_id:
            with st.spinner(f'Loading {selected_symbol} price data...'):
                market_data = fetch_market_chart(selected_api_id, vs_curr=vs_currency, days=days_param)
            
            if market_data and 'prices' in market_data:
                prices = market_data['prices']
                
                # データのフィルタリング (1h, 4hの場合)
                if timeframe in ["1h", "4h"]:
                    cutoff_time = datetime.now().timestamp() * 1000
                    if timeframe == "1h":
                        cutoff_time -= 3600 * 1000
                    elif timeframe == "4h":
                        cutoff_time -= 4 * 3600 * 1000
                    
                    prices = [p for p in prices if p[0] >= cutoff_time]

                dates = [datetime.fromtimestamp(p[0]/1000) for p in prices]
                price_values = [p[1] for p in prices]
                
                # Y軸範囲を動的に調整（変化を見やすくする）
                if price_values:
                    min_price = min(price_values)
                    max_price = max(price_values)
                    price_range = max_price - min_price
                    
                    # マージンを追加（価格レンジの5%）
                    margin = price_range * 0.05 if price_range > 0 else max_price * 0.05
                    y_min = min_price - margin
                    y_max = max_price + margin
                    
                    # 最小値は0を下回らないようにする
                    y_min = max(0, y_min)
                else:
                    y_min = None
                    y_max = None
                
                # チャート色 (選択された資産の色を使用)
                line_color = color_map.get(selected_symbol, '#00ff9d')
                
                fig_line = go.Figure()
                fig_line.add_trace(go.Scatter(
                    x=dates, 
                    y=price_values,
                    mode='lines',
                    name=selected_symbol,
                    line=dict(color=line_color, width=2.5),
                    fill='tozeroy',
                    fillcolor=f'rgba({int(line_color[1:3], 16)}, {int(line_color[3:5], 16)}, {int(line_color[5:7], 16)}, 0.1)'
                ))
                
                fig_line.update_layout(
                    title=dict(
                        text=f"{selected_symbol} - {timeframe.upper()} Chart",
                        font=dict(color="#ffffff", size=16),
                        y=0.98,
                        x=0.5,
                        xanchor='center',
                        yanchor='top'
                    ),
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    xaxis=dict(
                        showgrid=False, 
                        tickfont=dict(color='#888'),
                        linecolor='#333'
                    ),
                    yaxis=dict(
                        showgrid=True, 
                        gridcolor='#333', 
                        tickfont=dict(color='#888'),
                        tickprefix=currency_symbol,
                        range=[y_min, y_max]
                    ),
                    margin=dict(t=40, b=0, l=0, r=0),
                    height=350,
                    showlegend=False
                )
                
                st.plotly_chart(fig_line, use_container_width=True)
            else:
                st.warning(f"Price data for {selected_symbol} is currently unavailable. Please try again later.")
        else:
            st.info("No API ID available for selected asset.")
    else:
        st.info("Select an asset above to view price trend.")

    st.markdown("<br>", unsafe_allow_html=True)
    
    # 4. 為替レートチャート (USD/JPY Analysis)
    
    exchange_data = fetch_exchange_rate_history(days=30)
    
    if exchange_data and 'prices' in exchange_data:
        ex_prices = exchange_data['prices']
        ex_dates = [datetime.fromtimestamp(p[0]/1000) for p in ex_prices]
        ex_values = [p[1] for p in ex_prices]
        
        # 直近のレートを表示
        latest_rate = ex_values[-1] if ex_values else 0
        rate_diff = ex_values[-1] - ex_values[0] if len(ex_values) > 1 else 0
        diff_color = "#00ff9d" if rate_diff >= 0 else "#ff4b4b"
        diff_sign = "+" if rate_diff >= 0 else ""
        
        st.markdown(f"""
        <div style="margin-bottom: 10px;">
            <span style="font-size: 1.2rem; font-weight: bold;">USD/JPY Analysis</span>
            <span style="font-size: 1rem; color: var(--text-muted); margin-left: 10px;">1 USD ≒ {latest_rate:,.2f} JPY</span>
            <span style="color: {diff_color}; font-size: 0.9rem; margin-left: 5px;">({diff_sign}{rate_diff:.2f} / 30days)</span>
        </div>
        """, unsafe_allow_html=True)
        
        fig_ex = go.Figure()
        
        fig_ex.add_trace(go.Scatter(
            x=ex_dates, 
            y=ex_values,
            mode='lines',
            name='USD/JPY',
            line=dict(color='#FFD700', width=2), # Gold
            fill='tozeroy',
            fillcolor='rgba(255, 215, 0, 0.1)'
        ))
        
        fig_ex.update_layout(
            title_text="USD/JPY Exchange Rate (Last 30 Days)",
            title_font_color="#ffffff",
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(
                showgrid=False, 
                tickfont=dict(color='#888'),
                linecolor='#333'
            ),
            yaxis=dict(
                showgrid=True, 
                gridcolor='#333', 
                tickfont=dict(color='#888'),
                tickprefix="¥",
                range=[min(ex_values) * 0.99, max(ex_values) * 1.01]  # Y軸の範囲を動的に設定
            ),
            margin=dict(t=40, b=0, l=0, r=0),
            height=300,
            showlegend=False
        )
        
        st.plotly_chart(fig_ex, width='stretch')

    st.markdown("<br>", unsafe_allow_html=True)

# --------------------------

# 保有資産リスト
if portfolio_display_data:
    st.markdown("### 保有資産リスト")

    # データフレームの作成
    df_holdings = pd.DataFrame(portfolio_display_data)
    
    # 評価額（value）でソート（降順）
    df_holdings = df_holdings.sort_values(by='value', ascending=False)
    
    # 表示用にデータを整形
    display_df = df_holdings.copy()
    
    # カラム設定
    column_config = {
        "icon_url": st.column_config.ImageColumn(
            "Icon",
            help="Asset Icon",
            width="small"
        ),
        "symbol": st.column_config.TextColumn(
            "Symbol",
            width="small"
        ),
        "name": st.column_config.TextColumn(
            "Name",
            width="medium"
        ),
        "location": st.column_config.TextColumn(
            "Storage",
            width="small" 
        ),
        "holdings": st.column_config.NumberColumn(
            "Qty",
            format="%.8f",
            width="small"
        ),
        "price": st.column_config.NumberColumn(
            f"Price ({currency_symbol})",
            format="%.6f" if currency == "USD" else "%.2f",
            width="small"
        ),
        "value": st.column_config.NumberColumn(
            f"Value ({currency_symbol})",
            format="%.2f" if currency == "USD" else "%.0f",
            width="small"
        ),
        "avg_cost": st.column_config.NumberColumn(
            "Avg Cost ($)",
            format="%.6f",
            width="small",
            help="平均取得単価 (USD)"
        ),
        "pl_percent": st.column_config.NumberColumn(
            "P/L %",
            format="%.1f%%",
            width="small",
            help="損益率（現在価格 vs 平均取得単価）"
        ),
        "unrealized_pl": st.column_config.NumberColumn(
            "Unrealized P/L ($)",
            format="%.2f",
            width="small",
            help="未実現損益 (USD)"
        )
    }

    # 表示するカラムの順序
    display_cols = ["icon_url", "symbol", "name", "location", "holdings", "price", "value", "avg_cost", "pl_percent", "unrealized_pl"]

    # 行数に応じて高さを動的に計算（1行あたり35px + ヘッダー40px）
    table_height = max(500, len(display_df) * 35 + 40)
    
    st.dataframe(
        display_df[display_cols],
        column_config=column_config,
        use_container_width=True,
        hide_index=True,
        height=table_height
    )

else:
    st.info("保有している資産はありません。")

st.markdown("<br><br>", unsafe_allow_html=True)

# クイックアクセスセクション
st.markdown("### Quick Access")
st.markdown("<br>", unsafe_allow_html=True)

qa_col1, qa_col2 = st.columns(2)

with qa_col1:
    st.markdown("""
    <div class="crypto-card" style="padding: 20px;">
        <div style="text-align: center;">
            <div style="font-size: 2rem; margin-bottom: 0.5rem;">Assets</div>
            <h3 style="margin-bottom: 0.5rem; font-size: 1.2rem;">資産管理</h3>
            <p style="color: var(--text-muted); font-size: 0.8rem;">登録・編集・削除</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("資産管理ページへ", key="goto_assets", width='stretch'):
        st.switch_page("pages/1_assets.py")

with qa_col2:
    st.markdown("""
    <div class="crypto-card" style="padding: 20px;">
        <div style="text-align: center;">
            <div style="font-size: 2rem; margin-bottom: 0.5rem;">Transactions</div>
            <h3 style="margin-bottom: 0.5rem; font-size: 1.2rem;">取引記録</h3>
            <p style="color: var(--text-muted); font-size: 0.8rem;">売買履歴の確認</p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("取引記録ページへ", key="goto_transactions", width='stretch'):
        st.switch_page("pages/2_transactions.py")

# フッター
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: var(--text-muted); font-size: 0.8rem;">
    <p>Powered by CoinGecko API</p>
</div>
""", unsafe_allow_html=True)
