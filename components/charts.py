
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime

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
FALLBACK_COLORS = [
    '#00d9ff', '#7000ff', '#ff00aa', '#00ff9d', '#ffcc00', 
    '#ff4b4b', '#2e2e2e', '#575757', '#888888', '#aaaaaa'
]

def render_charts(portfolio_display_data, get_portfolio_history_func):
    """
    Renders the charts section (Allocation, Top Assets, History).
    """
    if not portfolio_display_data:
        st.info("No data available for charts.")
        return

    st.markdown("### Portfolio Analysis")
    
    chart_col1, chart_col2, chart_col3 = st.columns(3)
    
    # データを価値順にソート (全体で使用)
    sorted_data = sorted(portfolio_display_data, key=lambda x: x['value'], reverse=True)
    
    # 色の割り当て (シンボル -> 色)
    color_map = {}
    for i, item in enumerate(sorted_data):
        symbol = item['symbol']
        # ブランドカラーがあればそれを使用、なければフォールバックカラー
        color = CRYPTO_COLORS.get(symbol, FALLBACK_COLORS[i % len(FALLBACK_COLORS)])
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
                font=dict(color="#e8edf5", size=14),
                y=0.98,
                x=0.5,
                xanchor='center',
                yanchor='top'
            ),
            showlegend=True,
            legend=dict(
                font=dict(color="#94a3b8", size=10),
                orientation="h",
                yanchor="top",
                y=-0.1,
                xanchor="center",
                x=0.5
            ),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(t=40, b=50, l=20, r=20),
            height=300,
            annotations=[dict(
                text=f"<b>${total_value:,.0f}</b>",
                x=0.5, y=0.5,
                font=dict(size=18, color='#00d9ff', family='Monaco, monospace'),
                showarrow=False
            )]
        )
        
        fig_donut.update_traces(
            hoverinfo='label+value+percent', 
            textfont_size=12
        )
        
        st.plotly_chart(fig_donut, use_container_width=True)

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
                font=dict(color="#e8edf5", size=14),
                y=0.98,
                x=0.5,
                xanchor='center',
                yanchor='top'
            ),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(showgrid=False, showticklabels=False),
            yaxis=dict(showgrid=False, tickfont=dict(color='#94a3b8')),
            margin=dict(t=40, b=10, l=10, r=10),
            height=300
        )
        
        st.plotly_chart(fig_bar, use_container_width=True)

    # 3. ポートフォリオ履歴チャート（期間セレクター付き）
    with chart_col3:
        # 期間セレクター設定
        PERIOD_CONFIG = {
            '1W':  {'days': 7,    'label': '1 Week',    'tickformat': '%m/%d', 'marker_size': 6},
            '1M':  {'days': 30,   'label': '1 Month',   'tickformat': '%m/%d', 'marker_size': 5},
            '3M':  {'days': 90,   'label': '3 Months',  'tickformat': '%m/%d', 'marker_size': 4},
            '6M':  {'days': 180,  'label': '6 Months',  'tickformat': '%Y/%m', 'marker_size': 3},
            '1Y':  {'days': 365,  'label': '1 Year',    'tickformat': '%Y/%m', 'marker_size': 3},
            'ALL': {'days': 9999, 'label': 'All Time',  'tickformat': '%Y/%m', 'marker_size': 2},
        }
        
        # 期間セレクター（横並びラジオボタン）
        selected_period = st.radio(
            "期間",
            options=list(PERIOD_CONFIG.keys()),
            index=1,  # デフォルト: 1M
            horizontal=True,
            key="history_period_selector",
            label_visibility="collapsed"
        )
        
        config = PERIOD_CONFIG[selected_period]
        snapshot_data = get_portfolio_history_func(days=config['days'])
        
        if snapshot_data:
            hist_dates = [datetime.fromisoformat(s[0]) for s in snapshot_data]
            hist_values = [s[1] for s in snapshot_data]
            
            # 変化率の計算
            if len(hist_values) >= 2:
                first_val = hist_values[0]
                last_val = hist_values[-1]
                change_pct = ((last_val - first_val) / first_val) * 100 if first_val > 0 else 0
                change_amount = last_val - first_val
                change_color = "#00ff9d" if change_pct >= 0 else "#ff4b4b"
                change_sign = "+" if change_pct >= 0 else ""
                change_icon = "▲" if change_pct >= 0 else "▼"
            else:
                change_pct = 0
                change_amount = 0
                change_color = "#888"
                change_sign = ""
                change_icon = "—"
            
            # タイトルと変化率をチャート外に表示
            st.markdown(
                f"<div style='text-align:center;'>"
                f"<span style='color:#e8edf5;font-size:14px;font-weight:bold;'>History ({config['label']})</span>"
                f"<br><span style='font-size:12px;color:{change_color}'>"
                f"{change_icon} {change_sign}{change_pct:.1f}%"
                f" ({change_sign}¥{abs(change_amount):,.0f})</span>"
                f"</div>",
                unsafe_allow_html=True
            )
            
            # Y軸の範囲を動的に設定（変動を見やすくする）
            min_val = min(hist_values)
            max_val = max(hist_values)
            val_range = max_val - min_val
            padding = val_range * 0.15 if val_range > 0 else max_val * 0.05
            y_min = max(0, min_val - padding)
            y_max = max_val + padding
            
            fig_hist = go.Figure()
            
            fig_hist.add_trace(go.Scatter(
                x=hist_dates, 
                y=hist_values,
                mode='lines+markers',
                name='Portfolio Value',
                line=dict(color='#3b82f6', width=2),
                marker=dict(size=config['marker_size'], color='#3b82f6'),
                fill='tozeroy',
                fillcolor='rgba(59, 130, 246, 0.1)',
                hovertemplate='%{x|%Y-%m-%d}<br>¥%{y:,.0f}<extra></extra>'
            ))
            
            fig_hist.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(
                    showgrid=False, 
                    tickfont=dict(color='#94a3b8', size=10),
                    tickformat=config['tickformat']
                ),
                yaxis=dict(
                    showgrid=True, 
                    gridcolor='rgba(59, 130, 246, 0.08)',
                    tickfont=dict(color='#94a3b8', size=10),
                    tickformat='s',
                    range=[y_min, y_max]
                ),
                margin=dict(t=10, b=20, l=30, r=10),
                height=280,
                showlegend=False
            )
            
            st.plotly_chart(fig_hist, use_container_width=True)
        else:
            st.info("No history data available.")

def render_price_analysis_chart(portfolio_display_data, fetch_market_chart_func, fetch_exchange_rate_history_func, currency_symbol, vs_currency):
    """
    Renders the Price Trend and Exchange Rate charts.
    """
    st.markdown("""<div style="margin-top: 2rem;"></div>""", unsafe_allow_html=True)
    
    # 3. 価格推移チャート（フルワイド版 - Price Trend）
    st.markdown("### 📈 Asset Price Trend")
    
    # データを価値順にソート
    sorted_data = sorted(portfolio_display_data, key=lambda x: x['value'], reverse=True)
    
    # 色の割り当て
    color_map = {}
    for i, item in enumerate(sorted_data):
        symbol = item['symbol']
        color = CRYPTO_COLORS.get(symbol, FALLBACK_COLORS[i % len(FALLBACK_COLORS)])
        color_map[symbol] = color

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
                market_data = fetch_market_chart_func(selected_api_id, vs_curr=vs_currency, days=days_param)
            
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
                        font=dict(color="#e8edf5", size=16),
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

    st.markdown("""<div style="margin-top: 2rem;"></div>""", unsafe_allow_html=True)
    
    # 4. 為替レートチャート (USD/JPY Analysis)
    
    exchange_data = fetch_exchange_rate_history_func(days=30)
    
    if exchange_data and 'prices' in exchange_data:
        ex_prices = exchange_data['prices']
        ex_dates = [datetime.fromtimestamp(p[0]/1000) for p in ex_prices]
        ex_values = [p[1] for p in ex_prices]
        
        # 直近のレートを表示
        latest_rate = ex_values[-1] if ex_values else 0
        rate_diff = ex_values[-1] - ex_values[0] if len(ex_values) > 1 else 0
        diff_color = "#00ff9d" if rate_diff >= 0 else "#ff4b4b"
        diff_sign = "+" if rate_diff >= 0 else ""
        
        st.markdown(f"### 💱 USD/JPY &nbsp;&nbsp; `¥{latest_rate:,.2f}`")
        
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
            title_font_color="#e8edf5",
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(
                showgrid=False, 
                tickfont=dict(color='#888'),
                linecolor='#333'
            ),
            yaxis=dict(
                showgrid=True, 
                gridcolor='rgba(59, 130, 246, 0.08)', 
                tickfont=dict(color='#94a3b8'),
                tickprefix="¥",
                range=[min(ex_values) * 0.99, max(ex_values) * 1.01]  # Y軸の範囲を動的に設定
            ),
            margin=dict(t=40, b=0, l=0, r=0),
            height=300,
            showlegend=False
        )
        
        st.plotly_chart(fig_ex, use_container_width=True)

    st.markdown("""<div style="margin-top: 1rem;"></div>""", unsafe_allow_html=True)
