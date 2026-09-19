"""Optional live market chart with the original evaluation-currency fallback."""
import streamlit as st
import streamlit.components.v1 as components

from components.motion import loading
from components.portfolio_charts import line_figure
from portfolio_logic import money
from portfolio_service import coin_history
from tradingview_config import market_for, widget_html


def render_asset_chart(row, currency, mask):
    market = market_for(row.get('api_id'))
    use_tradingview = False
    if market and not mask:
        mode = st.segmented_control(
            'チャート', ['TradingView', f'{currency}の価格推移'],
            default='TradingView', key=f"asset_chart_mode_{row['id']}_{currency}",
        ) or 'TradingView'
        use_tradingview = mode == 'TradingView'
    elif not market:
        st.caption('この銘柄は従来の価格推移を表示します。')

    if use_tradingview:
        st.caption(f'{market.exchange} · {market.base}/{market.quote} 現物市場 · TradingView')
        st.caption(f'チャートは{market.quote}建てです。上の{currency}建て評価額とは価格の取得元・更新時刻が異なります。')
        with st.container(key='tradingview-chart'):
            components.html(widget_html(market), height=440, scrolling=False, tab_index=0)
        st.caption(f'表示できない場合は「{currency}の価格推移」に切り替えてください。')
        return

    days = st.segmented_control('価格推移', [7,30,90,365], default=30,
        format_func=lambda v:f'{v}日', key=f"asset_period_{row['id']}") or 30
    with loading('価格推移を読み込み中…', kind='chart'):
        records = coin_history(row['api_id'], currency, days)
    if records:
        st.plotly_chart(line_figure(records,currency,mask,height=260), key=f"asset_chart_{row['id']}",
            config={'displayModeBar':False}, width='stretch')
        st.caption(f"最新の記録：{records[-1]['date'][:16].replace('T',' ')} JST · {money(records[-1]['value'],currency,price=True,masked=mask)}")
    else:
        st.info('価格推移を取得できませんでした。しばらくしてもう一度お試しください。')
