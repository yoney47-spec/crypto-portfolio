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
    get_portfolio_history,
    save_price_cache,
    load_price_cache,
    load_price_cache_if_valid,
    get_latest_ai_comment,
    save_ai_comment,
    save_portfolio_snapshot
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
    with open(css_file, encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css()

# Mobile viewport meta tag for proper iPhone scaling
st.markdown("""
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
""", unsafe_allow_html=True)

# --- サイドバー設定 ---
# --- サイドバー設定 ---
from components.sidebar import render_sidebar
from components.metrics import render_metrics
from components.charts import render_charts, render_price_analysis_chart

currency = render_sidebar()
currency_symbol = "$" if currency == "USD" else "¥"
vs_currency = currency.lower()

# --- データ取得ロジック ---
# Note: get_portfolio_data and calculate_cost_basis are now imported from database_supabase

# USD/JPY為替レートを取得（CoinGecko以外のAPIを使用）
@st.cache_data(ttl=3600)  # 1時間キャッシュ
def fetch_usd_jpy_rate():
    """USD/JPY為替レートを取得（CoinGecko以外のAPI）"""
    
    # 方法1: exchangerate.host API (無料、APIキー不要)
    try:
        response = requests.get(
            "https://api.exchangerate.host/latest",
            params={"base": "USD", "symbols": "JPY"},
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("success") and "rates" in data:
                return data["rates"].get("JPY", 155.0)
    except:
        pass
    
    # 方法2: Open Exchange Rates API (無料プラン)
    try:
        response = requests.get(
            "https://open.er-api.com/v6/latest/USD",
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            if "rates" in data:
                return data["rates"].get("JPY", 155.0)
    except:
        pass
    
    # フォールバック: 固定レート
    return 155.0

# 現在価格の取得 (USDのみ) - キャッシュ有効化
@st.cache_data(ttl=1800)  # 30分キャッシュ（APIレート制限対策）
def fetch_current_prices_usd(api_ids):
    """CoinGecko APIからUSD価格のみを取得（レート制限対策）"""
    if not api_ids:
        return {}
    
    # USDのみ取得（JPYはレート換算で対応）
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": ",".join(api_ids),
        "vs_currencies": "usd",
        "include_24hr_change": "true"
    }
    
    max_retries = 3
    last_error = None
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, timeout=15)
            
            # レート制限エラー
            if response.status_code == 429:
                last_error = "rate_limit"
                if attempt < max_retries - 1:
                    wait_time = 2 ** (attempt + 1)  # 2s, 4s, 8s wait
                    print(f"[API] レート制限検出。{wait_time}秒待機中... (試行 {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                print("[API] レート制限: 最大リトライ回数に達しました")
                return None
            
            # サーバーエラー
            if response.status_code >= 500:
                last_error = "server_error"
                if attempt < max_retries - 1:
                    print(f"[API] サーバーエラー ({response.status_code})。リトライ中...")
                    time.sleep(2)
                    continue
                print(f"[API] サーバーエラー: {response.status_code}")
                return None
                
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.Timeout:
            last_error = "timeout"
            print(f"[API] タイムアウト (試行 {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            return None
            
        except requests.exceptions.ConnectionError:
            last_error = "connection"
            print(f"[API] 接続エラー (試行 {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            return None
            
        except Exception as e:
            last_error = str(e)
            print(f"[API] 予期しないエラー: {e}")
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            return None
    
    return None

def get_prices_with_jpy(api_ids, usd_jpy_rate):
    """USD価格を取得し、JPY価格も計算して追加"""
    prices_usd = fetch_current_prices_usd(tuple(api_ids))  # tupleに変換してキャッシュ可能に
    if prices_usd is None:
        return None
    
    # JPY価格を追加
    result = {}
    for api_id, data in prices_usd.items():
        result[api_id] = {
            "usd": data.get("usd"),
            "jpy": data.get("usd", 0) * usd_jpy_rate if data.get("usd") else None,
            "usd_24h_change": data.get("usd_24h_change"),
            "jpy_24h_change": data.get("usd_24h_change"),  # 変動率はUSDと同じ
        }
    return result

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

# ポートフォリオデータをキャッシュ（60秒TTL）
@st.cache_data(ttl=60)
def get_cached_portfolio_data():
    """キャッシュされたポートフォリオデータを取得"""
    return get_portfolio_data()

# データを取得（キャッシュから）
portfolio_data, asset_count, transaction_count = get_cached_portfolio_data()

# API IDリスト作成
api_ids = [item[3] for item in portfolio_data if item[3]]

# 為替レートを先に取得（CoinGecko以外のAPIを使用）
with st.spinner('為替レートを取得中...'):
    exchange_rate = fetch_usd_jpy_rate()

# 価格取得の最適化: キャッシュが有効ならAPIを呼び出さない
force_refresh = st.session_state.get('force_price_refresh', False)
st.session_state['force_price_refresh'] = False  # フラグをリセット

# まずキャッシュをチェック（5分以内なら有効）
cached_prices = load_price_cache_if_valid(max_age_minutes=5)

if cached_prices and not force_refresh:
    # キャッシュが有効 - APIを呼び出さない
    current_prices = cached_prices
    # キャッシュ使用を示す小さなインジケーター（デバッグ用、本番では非表示可）
    # st.caption("📦 キャッシュデータ使用中")
else:
    # キャッシュが古いか無効 - APIから取得
    with st.spinner('最新価格を取得中...'):
        current_prices = get_prices_with_jpy(api_ids, exchange_rate)
    
    if current_prices is None or len(current_prices) == 0:
        # API制限時はキャッシュから読み込み（期限切れでも使用）
        cached_prices = load_price_cache()
        if cached_prices:
            st.info("📦 キャッシュされた価格データを表示しています（API制限により最新データを取得できませんでした）")
            current_prices = cached_prices
        else:
            st.warning("⚠️ 価格データを取得できませんでした。しばらく待ってから「データ更新」ボタンを押してください。")
            current_prices = {}
    else:
        # 成功時はキャッシュを更新
        save_price_cache(current_prices)


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

# ヘッダー（コンパクト版）
st.markdown("# Crypto Portfolio")


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

top_change = 0
worst_change = 0
top_symbol = "-"
worst_symbol = "-"

if top_performer:
    api_id = top_performer['api_id']
    change_key = f"{vs_currency}_24h_change"
    top_change = current_prices.get(api_id, {}).get(change_key, 0) or 0
    top_symbol = top_performer['symbol']

if worst_performer:
    api_id = worst_performer['api_id']
    change_key = f"{vs_currency}_24h_change"
    worst_change = current_prices.get(api_id, {}).get(change_key, 0) or 0
    worst_symbol = worst_performer['symbol']

# メトリクスエリア（コンポーネント使用）
render_metrics(
    total_portfolio_value, 
    total_pl_percent, 
    total_pl_display, 
    portfolio_24h_percent, 
    portfolio_24h_change, 
    currency_symbol, 
    len(portfolio_data), 
    top_performer, 
    top_change, 
    worst_performer, 
    worst_change, 
    vs_currency
)


# --- Gemini AI コメントセクション ---
def generate_and_save_ai_comment():
    """AIコメントを生成して保存"""
    try:
        from gemini_client import generate_portfolio_comment
        from datetime import datetime, timezone, timedelta
        
        JST = timezone(timedelta(hours=9))
        today = datetime.now(JST).date().isoformat()
        
        # ポートフォリオデータを収集
        top_assets_data = []
        for item in sorted(portfolio_display_data, key=lambda x: x['value'], reverse=True)[:5]:
            api_id = item['api_id']
            change_24h = current_prices.get(api_id, {}).get(f'{vs_currency}_24h_change', 0) or 0
            percent = (item['value'] / total_portfolio_value * 100) if total_portfolio_value > 0 else 0
            top_assets_data.append({
                'symbol': item['symbol'],
                'percent': percent,
                'change_24h': change_24h
            })
        
        portfolio_summary = {
            'total_value': total_portfolio_value_usd,
            'total_value_jpy': total_portfolio_value_usd * exchange_rate,
            'change_percent': portfolio_24h_percent,
            'change_amount': portfolio_24h_change,
            'asset_count': len(portfolio_display_data),
            'top_assets': top_assets_data,
            'top_performer': {
                'symbol': top_symbol,
                'change': top_change
            },
            'worst_performer': {
                'symbol': worst_symbol,
                'change': worst_change
            }
        }
        
        # Geminiでコメント生成
        comment = generate_portfolio_comment(portfolio_summary)
        
        if comment:
            save_ai_comment(today, comment, portfolio_summary)
            return comment
        return None
    except Exception as e:
        print(f"AI comment generation error: {e}")
        return None

# AIコメントの表示
ai_comment_data = get_latest_ai_comment()

# コメントがない場合、または古い場合は生成を試みる（1日1回）
from datetime import timezone, timedelta
JST = timezone(timedelta(hours=9))
today_str = datetime.now(JST).date().isoformat()

if ai_comment_data is None or ai_comment_data.get('date') != today_str:
    # Gemini API が設定されているかチェック
    gemini_configured = False
    try:
        gemini_api_key = st.secrets.get("gemini", {}).get("api_key")
        gemini_configured = bool(gemini_api_key)
    except:
        pass
    
    if gemini_configured and portfolio_display_data:
        with st.spinner('✨ AIコメントを生成中...'):
            new_comment = generate_and_save_ai_comment()
            if new_comment:
                ai_comment_data = {'date': today_str, 'comment': new_comment}

# 手動更新ボタン（Gemini APIが設定されている場合のみ）
gemini_configured = False
try:
    gemini_api_key = st.secrets.get("gemini", {}).get("api_key")
    gemini_configured = bool(gemini_api_key)
except:
    pass

if gemini_configured and portfolio_display_data:
    if st.button("✨ インサイトを更新", help="Geminiデイリーインサイトを最新のデータで再生成します"):
        with st.spinner('✨ AIコメントを生成中...'):
            new_comment = generate_and_save_ai_comment()
            if new_comment:
                ai_comment_data = {'date': today_str, 'comment': new_comment}
                st.success("インサイトを更新しました！")
                time.sleep(1)
                st.rerun()

# AIコメントカードを表示
if ai_comment_data and ai_comment_data.get('comment'):
    comment_date = ai_comment_data.get('date', '')
    comment_text = ai_comment_data.get('comment', '')
    
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, rgba(103, 58, 183, 0.1), rgba(0, 217, 255, 0.1));
        border: 1px solid rgba(103, 58, 183, 0.3);
        border-radius: 12px;
        padding: 1.25rem;
        margin: 1.5rem 0;
    ">
        <div style="
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.75rem;
        ">
            <span style="
                font-weight: 600;
                color: var(--text-primary);
                font-size: 1rem;
            ">✨ Gemini's Daily Insight</span>
            <span style="
                color: var(--text-muted);
                font-size: 0.8rem;
            ">{comment_date}</span>
        </div>
        <div style="
            color: var(--text-secondary);
            font-size: 0.9rem;
            line-height: 1.6;
        ">{comment_text}</div>
    </div>
    """, unsafe_allow_html=True)



# --- チャートセクション ---
# --- チャートセクション（コンポーネント使用） ---
render_charts(portfolio_display_data, get_portfolio_history)

# --- 価格分析チャート（コンポーネント使用） ---
render_price_analysis_chart(
    portfolio_display_data, 
    fetch_market_chart, 
    fetch_exchange_rate_history, 
    currency_symbol, 
    vs_currency
)

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
    
    # カラム設定 - widthを調整して見切れを防止
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
            width="medium"  # smallからmediumに変更（見切れ防止）
        ),
        "holdings": st.column_config.NumberColumn(
            "Qty",
            format="%.8f",
            width="medium"  # 桁が多いためmediumに変更
        ),
        "price": st.column_config.NumberColumn(
            f"Price ({currency_symbol})",
            format="%.6f" if currency == "USD" else "%.2f",
            width="medium"  # 桁が多いためmediumに変更
        ),
        "value": st.column_config.NumberColumn(
            f"Value ({currency_symbol})",
            format="%.2f" if currency == "USD" else "%.0f",
            width="medium"  # 桁が多いためmediumに変更
        ),
        "avg_cost": st.column_config.NumberColumn(
            "Avg Cost ($)",
            format="%.6f",
            width="medium",  # 桁が多いためmediumに変更
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
            width="medium",  # 桁が多いためmediumに変更
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
