"""
暗号資産ポートフォリオアプリ - ダッシュボード
"""

import streamlit as st
import requests
import time
from pathlib import Path
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, timedelta, timezone
from html import escape
from access_control import is_public_read_only
# Import from new Supabase adapter
from database_supabase import (
    get_portfolio_data, 
    calculate_cost_basis, 
    get_current_year_investment_sales,
    get_portfolio_history,
    save_price_cache,
    load_price_cache,
    get_latest_ai_comment,
    save_ai_comment,
    save_portfolio_snapshot
)
from market_data import CoinGeckoError, coingecko_get_json, get_current_prices

# ページ設定
st.set_page_config(
    page_title="ポートフォリオ | CryptoFolio",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded"
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

currency, layout_mode = render_sidebar()
currency_symbol = "$" if currency == "USD" else "¥"
vs_currency = currency.lower()

# --- Fear & Greed Index ---
@st.cache_data(ttl=3600)
def fetch_fear_greed():
    """Fear & Greed Index を取得"""
    try:
        resp = requests.get("https://api.alternative.me/fng/?limit=1", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('data'):
                entry = data['data'][0]
                return {
                    'value': int(entry['value']),
                    'label': entry['value_classification'],
                    'timestamp': entry.get('timestamp', '')
                }
    except:
        pass
    return None

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

class CoinGeckoAPIError(Exception):
    """CoinGecko APIエラー用カスタム例外"""
    pass

# 過去の価格チャートデータを取得 - キャッシュ有効化 (TTL: 1時間)
@st.cache_data(ttl=3600)
def fetch_market_chart_cached(api_id, vs_curr="usd", days=7):
    """CoinGecko APIから過去の価格データを取得（キャッシュ対応）"""
    if not api_id:
        return None

    params = {
        "vs_currency": vs_curr,
        "days": days
    }

    try:
        data = coingecko_get_json(
            f"/coins/{api_id}/market_chart",
            params=params,
            timeout=10,
            max_attempts=1,
        )
        if not data or 'prices' not in data or len(data['prices']) == 0:
            raise CoinGeckoAPIError("Invalid or empty data received for market chart")
        return data
    except CoinGeckoError as e:
        raise CoinGeckoAPIError(str(e)) from e


def fetch_market_chart(api_id, vs_curr="usd", days=7):
    """キャッシュ対応のCoinGecko API呼び出しのラッパー。エラー時はセッションステートに保存された過去データを返す"""
    state_key = f"last_market_chart_{api_id}_{vs_curr}_{days}"
    if "market_chart_history" not in st.session_state:
        st.session_state["market_chart_history"] = {}
        
    try:
        data = fetch_market_chart_cached(api_id, vs_curr, days)
        st.session_state["market_chart_history"][state_key] = data
        return data
    except CoinGeckoAPIError as e:
        print(f"[CACHE INFO] {e}. Trying session fallback...")
        fallback_data = st.session_state["market_chart_history"].get(state_key)
        if fallback_data:
            return fallback_data
        return None


# 為替レート(USDT/JPY)の履歴を取得 - キャッシュ有効化 (TTL: 6時間)
@st.cache_data(ttl=21600)
def fetch_exchange_rate_history_cached(days=30):
    """CoinGecko APIからUSDT/JPYの履歴を取得してドル円レートの代用とする（キャッシュ対応）"""
    params = {
        "vs_currency": "jpy",
        "days": days
    }

    try:
        data = coingecko_get_json(
            "/coins/tether/market_chart",
            params=params,
            timeout=10,
            max_attempts=1,
        )
        if not data or 'prices' not in data or len(data['prices']) == 0:
            raise CoinGeckoAPIError("Invalid or empty data received for exchange rate")
        return data
    except CoinGeckoError as e:
        raise CoinGeckoAPIError(str(e)) from e


def fetch_exchange_rate_history(days=30):
    """キャッシュ対応の為替レート履歴取得のラッパー。エラー時はセッションステートに保存された過去データを返す"""
    state_key = f"last_exchange_rate_history_{days}"
    if "exchange_rate_history" not in st.session_state:
        st.session_state["exchange_rate_history"] = {}
        
    try:
        data = fetch_exchange_rate_history_cached(days)
        st.session_state["exchange_rate_history"][state_key] = data
        return data
    except CoinGeckoAPIError as e:
        print(f"[CACHE INFO] {e}. Trying session fallback...")
        fallback_data = st.session_state["exchange_rate_history"].get(state_key)
        if fallback_data:
            return fallback_data
        return None


def handle_auto_snapshot(total_value, vs_currency, exchange_rate):
    """今日（JST）のスナップショットがまだなければ自動的に保存"""
    if is_public_read_only():
        return

    if st.session_state.get('auto_snapshot_checked', False):
        return
        
    try:
        val_jpy = total_value if vs_currency == "jpy" else total_value * exchange_rate
        
        latest = get_latest_snapshot()
        JST_tz = timezone(timedelta(hours=9))
        today = datetime.now(JST_tz).date().isoformat()
        
        if not latest or latest['date'] != today:
            if save_portfolio_snapshot(val_jpy):
                print(f"[AUTO SNAPSHOT] Created snapshot for {today}: JPY {val_jpy:,.0f}")
            else:
                print("[AUTO SNAPSHOT] Failed to save snapshot")
        
        st.session_state['auto_snapshot_checked'] = True
    except Exception as e:
        print(f"[AUTO SNAPSHOT ERROR] {e}")

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

# 全画面・全セッションで共通の価格キャッシュを使用する。
persisted_prices = load_price_cache()
try:
    with st.spinner('最新価格を取得中...'):
        price_result = get_current_prices(
            api_ids,
            fallback_prices=persisted_prices,
            force_refresh=force_refresh,
        )
    current_prices = price_result.prices
    if price_result.stale:
        st.caption("価格更新が混み合っているため、最終取得価格を表示しています。")
    if price_result.source == "live" and not is_public_read_only():
        save_price_cache(current_prices)
except CoinGeckoError:
    if persisted_prices:
        current_prices = persisted_prices
        st.caption("価格更新が混み合っているため、保存済みの価格を表示しています。")
    else:
        current_prices = {}
        st.warning("価格データを取得できませんでした。時間をおいて再度お試しください。")


# 総資産額の計算とチャート用データ作成
total_portfolio_value = 0
portfolio_display_data = []

# コストベースデータを取得
cost_basis_data = calculate_cost_basis()

for item in portfolio_data:
    p_id, symbol, name, api_id, icon_url, location, holdings = item
    
    # 価格データの抽出
    price_data = current_prices.get(api_id, {})
    price = price_data.get(vs_currency) or 0
    
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
        price_usd = current_prices.get(api_id, {}).get('usd') or 0
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

# 自動スナップショット処理を実行
if portfolio_display_data:
    handle_auto_snapshot(total_portfolio_value, vs_currency, exchange_rate)

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
JST_tz = timezone(timedelta(hours=9))
now_jst = datetime.now(JST_tz)
public_chip = '<span class="public-chip">公開ポートフォリオ</span>' if is_public_read_only() else ''

st.markdown(f"""
<div class="app-header">
    <div class="app-brand">
        <span class="brand-mark"><span></span><span></span><span></span></span>
        <span class="app-brand-copy">
            <span class="app-brand-title">CryptoFolio</span>
            <span class="app-brand-subtitle">Portfolio</span>
        </span>
    </div>
    <div class="app-header-meta">
        <span class="rate-badge">1 USD = ¥{exchange_rate:.2f}</span>
        <span>表示更新 {now_jst.strftime('%H:%M')} JST</span>
        {public_chip}
    </div>
</div>
""", unsafe_allow_html=True)


# 総損益の計算（含み益のみ、今年の取引ベース）
# まず、現在のポートフォリオ価値をUSDで計算
total_portfolio_value_usd = 0
for item in portfolio_display_data:
    api_id = item['api_id']
    holdings = item['holdings']
    price_data = current_prices.get(api_id, {})
    price_usd = price_data.get('usd') or 0  # 常にUSD価格を使用
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

# Fear & Greed Index ウィジェット
fng_data = fetch_fear_greed()
if fng_data:
    fng_val = fng_data['value']
    fng_label = fng_data['label']
    fng_label_ja = {
        'Extreme Fear': '極度の恐怖',
        'Fear': '恐怖',
        'Neutral': '中立',
        'Greed': '強欲',
        'Extreme Greed': '極度の強欲',
    }.get(fng_label, fng_label)
    if fng_val <= 25:
        fng_color = '#ff453a'
    elif fng_val <= 45:
        fng_color = '#ff9f0a'
    elif fng_val <= 55:
        fng_color = '#ffd60a'
    elif fng_val <= 75:
        fng_color = '#30d158'
    else:
        fng_color = '#30d158'
    
    st.markdown(f"""
    <div class="sentiment-card">
        <div class="sentiment-copy">
            <span class="sentiment-dot" style="background:{fng_color}; box-shadow:0 0 0 5px color-mix(in srgb, {fng_color} 14%, transparent);"></span>
            <div>
                <span class="sentiment-label">市場心理</span>
                <span class="sentiment-state" style="color:{fng_color};">{fng_label_ja}</span>
            </div>
        </div>
        <div class="sentiment-score">
            <div class="sentiment-track">
                <div style="width:{fng_val}%; height:100%; background:{fng_color}; border-radius:inherit;"></div>
            </div>
            <span style="color:{fng_color};">{fng_val}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

# 価格変動アラートバナー
alert_assets = []
for item in portfolio_display_data:
    api_id = item['api_id']
    change_key = f"{vs_currency}_24h_change"
    change = current_prices.get(api_id, {}).get(change_key, 0) or 0
    if abs(change) >= 10:
        alert_assets.append({'symbol': item['symbol'], 'change': change})

if alert_assets:
    alert_html_items = ''
    for a in sorted(alert_assets, key=lambda x: abs(x['change']), reverse=True):
        if a['change'] > 0:
            alert_html_items += f'<span class="alert-item alert-up">{a["symbol"]} +{a["change"]:.1f}%</span>'
        else:
            alert_html_items += f'<span class="alert-item alert-down">{a["symbol"]} {a["change"]:.1f}%</span>'
    
    st.markdown(f"""
    <div class="alert-banner">
        <span class="alert-text">24時間の大幅変動</span>
        {alert_html_items}
    </div>
    """, unsafe_allow_html=True)


# --- Gemini AI コメントセクション ---
def generate_and_save_ai_comment():
    """AIコメントを生成して保存"""
    if is_public_read_only():
        return None

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

if not is_public_read_only() and (ai_comment_data is None or ai_comment_data.get('date') != today_str):
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

if not is_public_read_only() and gemini_configured and portfolio_display_data:
    if st.button("✨ インサイトを更新", help="Geminiデイリーインサイトを最新のデータで再生成します"):
        with st.spinner('✨ AIコメントを生成中...'):
            new_comment = generate_and_save_ai_comment()
            if new_comment:
                ai_comment_data = {'date': today_str, 'comment': new_comment}
                st.success("インサイトを更新しました！")
                time.sleep(1)
                st.rerun()

# AIコメントは管理画面だけに表示し、公開画面はデータ中心に保つ。
show_ai_comment = (
    not is_public_read_only()
    and bool(ai_comment_data and ai_comment_data.get('comment'))
)

if show_ai_comment:
    comment_date = escape(str(ai_comment_data.get('date', '')))
    comment_text = escape(str(ai_comment_data.get('comment', '')))
    
    st.markdown(f"""
    <div class="ai-insight-card">
        <div class="ai-insight-header">
            <span class="ai-insight-title">✨ AIポートフォリオメモ</span>
            <span class="ai-insight-date">{comment_date}</span>
        </div>
        <div class="ai-insight-body">{comment_text}</div>
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
    st.markdown("""<div style="margin-top: 2rem;"></div>""", unsafe_allow_html=True)
    if is_public_read_only():
        st.markdown(
            "<div class='section-header'><div class='section-title'>主な保有資産</div>"
            "<div class='section-caption'>評価額上位5銘柄</div></div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown("### 保有資産一覧")

    # データフレームの作成
    df_holdings = pd.DataFrame(portfolio_display_data)
    
    # 評価額（value）でソート（降順）
    df_holdings = df_holdings.sort_values(by='value', ascending=False)
    
    # 表示用にデータを整形
    display_df = df_holdings.copy()
    
    # Location をスタイリッシュなバッジ表記に変換
    def format_location(loc):
        if not loc:
            return "📦 Unknown"
        loc_lower = str(loc).lower()
        if 'main' in loc_lower or 'メイン' in loc_lower:
            return f"🔐 {loc}"
        elif 'ledger' in loc_lower or 'cold' in loc_lower:
            return f"🛡️ {loc}"
        elif 'exchange' in loc_lower or 'binance' in loc_lower or 'bybit' in loc_lower or 'coincheck' in loc_lower or 'bitbank' in loc_lower:
            return f"🏦 {loc}"
        elif 'staking' in loc_lower or 'stake' in loc_lower:
            return f"⚡ {loc}"
        elif 'defi' in loc_lower or 'pool' in loc_lower:
            return f"🌊 {loc}"
        else:
            return f"📦 {loc}"
    
    display_df['location'] = display_df['location'].apply(format_location)
    
    # P/L表示用カラム（統合: %と金額を1列に）
    def format_pl_combined(row):
        pl = row['pl_percent']
        upl = row['unrealized_pl']
        if vs_currency == "jpy":
            upl_disp = upl * exchange_rate
            sym = "¥"
            amt_str = f"{abs(upl_disp):,.0f}"
        else:
            upl_disp = upl
            sym = "$"
            amt_str = f"{abs(upl_disp):,.2f}"
            
        if pl > 0:
            return f"+{pl:.1f}% (+{sym}{amt_str})"
        elif pl < 0:
            return f"{pl:.1f}% (-{sym}{amt_str})"
        else:
            return f"0.0% ({sym}0)"
    
    display_df['pl_combined'] = display_df.apply(format_pl_combined, axis=1)
    
    # Sparkline データ取得（7日間の価格推移） - /coins/markets APIで一括取得
    @st.cache_data(ttl=21600, show_spinner=False)
    def get_sparkline_data(api_ids_list):
        """複数資産の7日スパークラインデータを一括取得（/coins/markets API使用）"""
        sparklines = {}
        
        # /coins/markets エンドポイントで一括取得（sparkline=true）
        # 1リクエストで最大250件まで取得可能
        ids_str = ",".join(api_ids_list)
        try:
            data = coingecko_get_json(
                "/coins/markets",
                params={
                    'vs_currency': 'usd',
                    'ids': ids_str,
                    'sparkline': 'true',
                    'price_change_percentage': '7d',
                    'per_page': 250,
                    'page': 1
                },
                timeout=15,
                max_attempts=1,
            )
            for coin in data if isinstance(data, list) else []:
                coin_id = coin.get('id')
                spark_in_7d = coin.get('sparkline_in_7d', {})
                price_list = spark_in_7d.get('price', [])

                if price_list and len(price_list) > 0:
                    n_points = 24
                    if len(price_list) >= n_points:
                        indices = [int(i * (len(price_list) - 1) / (n_points - 1)) for i in range(n_points)]
                        resampled_prices = [price_list[idx] for idx in indices]
                    else:
                        resampled_prices = price_list + [price_list[-1]] * (n_points - len(price_list))

                    cleaned_prices = []
                    last_valid = price_list[0] if price_list[0] is not None else 0.0
                    for p in resampled_prices:
                        if p is None or not isinstance(p, (int, float)):
                            cleaned_prices.append(float(last_valid))
                        else:
                            cleaned_prices.append(float(p))
                            last_valid = p

                    sparklines[coin_id] = cleaned_prices
                else:
                    sparklines[coin_id] = None
        except CoinGeckoError:
            pass
        
        # 取得できなかったIDにはNoneを設定
        for api_id in api_ids_list:
            if api_id not in sparklines:
                sparklines[api_id] = None
        
        return sparklines
    
    # スパークラインデータ取得
    api_ids_for_spark = [row['api_id'] for _, row in display_df.iterrows() if row.get('api_id')]
    spark_data = get_sparkline_data(tuple(api_ids_for_spark))
    
    # DataFrameにスパークライン列追加
    display_df['sparkline'] = display_df['api_id'].apply(
        lambda x: spark_data.get(x) if spark_data.get(x) else None
    )

    # 最大評価額を取得（ProgressColumn用）
    max_value = display_df['value'].max() if len(display_df) > 0 else 1

    # カラム設定 - DeFiスタイル（最適化: avg_costを削除、P/Lを統合、sparkline追加）
    column_config = {
        "icon_url": st.column_config.ImageColumn(
            "🪙",
            help="銘柄アイコン",
            width="small"
        ),
        "symbol": st.column_config.TextColumn(
            "銘柄",
            width="small"
        ),
        "name": st.column_config.TextColumn(
            "資産名",
            width="small"
        ),
        "location": st.column_config.TextColumn(
            "保管場所",
            width="small",
            help="保管場所"
        ),
        "holdings": st.column_config.NumberColumn(
            "保有数量",
            format="%.4f",
            width="small"
        ),
        "price": st.column_config.NumberColumn(
            f"現在価格 ({currency_symbol})",
            format="%.4f" if currency == "USD" else "%.0f",
            width="small"
        ),
        "value": st.column_config.ProgressColumn(
            f"評価額 ({currency_symbol})",
            format=f"{currency_symbol}%.0f",
            min_value=0,
            max_value=float(max_value * 1.1),
            width="small",
            help="評価額（バーはポートフォリオ内の相対比率）"
        ),
        "sparkline": st.column_config.LineChartColumn(
            "7日推移",
            width="medium",
            help="過去7日間の価格推移"
        ),
        "pl_combined": st.column_config.TextColumn(
            "損益",
            width="medium",
            help="損益率 & 未実現損益"
        )
    }

    # 表示するカラムの順序（詳細表示と簡易表示で切り替え）
    if layout_mode == "コンパクト":
        display_cols = ["icon_url", "symbol", "holdings", "value", "pl_combined"]
    elif is_public_read_only():
        display_cols = ["icon_url", "symbol", "name", "holdings", "price", "value", "sparkline", "pl_combined"]
    else:
        display_cols = ["icon_url", "symbol", "name", "location", "holdings", "price", "value", "sparkline", "pl_combined"]

    table_df = display_df.head(5) if is_public_read_only() else display_df

    # 行数に応じて高さを動的に計算（1行あたり35px + ヘッダー40px）
    minimum_table_height = 260 if is_public_read_only() else 500
    table_height = max(minimum_table_height, len(table_df) * 35 + 48)
    st.dataframe(
        table_df[display_cols],
        column_config=column_config,
        use_container_width=True,
        hide_index=True,
        height=table_height
    )

else:
    st.info("保有している資産はありません。")

st.markdown("""<div style="margin-top: 2.5rem;"></div>""", unsafe_allow_html=True)

if is_public_read_only():
    if st.button("すべての保有資産を見る", key="goto_assets", type="primary", use_container_width=True):
        st.switch_page("pages/1_assets.py")
else:
    st.markdown("### 次のページ")
    qa_col1, qa_col2 = st.columns(2, gap="medium")

    with qa_col1:
        st.markdown("""
        <div class="qa-card">
            <div class="qa-card-icon">📊</div>
        <div class="qa-card-title">資産管理</div>
            <div class="qa-card-desc">登録 ・ 編集 ・ 削除</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("資産管理ページへ →", key="goto_assets", use_container_width=True):
            st.switch_page("pages/1_assets.py")

    with qa_col2:
        st.markdown("""
        <div class="qa-card">
            <div class="qa-card-icon">📋</div>
        <div class="qa-card-title">取引記録</div>
            <div class="qa-card-desc">売買履歴の確認</div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("取引記録ページへ →", key="goto_transactions", use_container_width=True):
            st.switch_page("pages/2_transactions.py")

# フッター
st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
st.markdown("""
<div class="footer-text">
    価格データ: CoinGecko API  ·  公開ポートフォリオ
</div>
""", unsafe_allow_html=True)
