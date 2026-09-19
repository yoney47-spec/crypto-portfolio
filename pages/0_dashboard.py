from datetime import datetime
from time import monotonic_ns
import streamlit as st
from portfolio_service import portfolio,exchange_rate,market_overview
from portfolio_logic import money,percent,JST
from components.shell import intro,preferences
from components.live_dashboard import render_live_dashboard

currency,mask=preferences()
intro('ポートフォリオ','資産の変化を捉えて、次の判断へ。')
render_live_dashboard(currency,mask,view_id=monotonic_ns())
st.page_link('pages/1_assets.py',label='すべての保有資産と詳細を見る',icon=':material/arrow_forward:')
if st.toggle('市場データ・分析メモを表示',key='show_market_context'):
    with st.spinner('補足データを読み込み中…'):
        fx=exchange_rate(datetime.now(JST).date().isoformat())
        market=market_overview()
    a,b=st.columns(2)
    a.metric('USD/JPY · 日次参考値',money(fx['rate'],'JPY',price=True,masked=mask) if fx else '取得できません')
    if fx: a.caption(f"{fx['date']} · {fx['source']}")
    b.metric('市場全体の24時間変化',percent(market.get('market_cap_change_percentage_24h_usd')))
    b.caption('USD建て時価総額 · CoinGecko')
    from components.analysis import render_analysis
    data=portfolio(currency)
    if data.get("error"):
        st.info("分析に必要な保有データを取得できませんでした。")
    else:
        render_analysis(data, mask)
