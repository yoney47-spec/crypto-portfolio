from html import escape
from datetime import datetime
import streamlit as st
from portfolio_service import portfolio,exchange_rate,market_overview
from portfolio_logic import year_to_date,history_series,money,percent,JST
from components.shell import intro,preferences,overview,freshness
from components.portfolio_charts import history_chart,composition,impacts

currency,mask=preferences()
intro('ポートフォリオ','資産の変化を捉えて、次の判断へ。')
with st.spinner('ポートフォリオを読み込み中…'):
    data=portfolio(currency)
if data.get('error'):
    st.error(data['error']);st.stop()
if not data['rows']:
    st.info('保有資産はまだありません。管理者が取引を登録すると表示されます。');st.stop()
ytd=year_to_date(data['history'],data['total'] if data['complete'] else None,data['stats'],currency)
overview(data,currency,mask,ytd)
freshness(data)
with st.expander('増減の計算方法'):
    st.write(ytd['reason'])
    st.caption('24時間の価格影響 = 現在の評価額 − 現在評価額 ÷（1 + 24時間変化率）。現在の保有数量を固定して計算します。価格や変化率がない銘柄を0として扱いません。')
with st.container(border=True):
    st.subheader('資産の推移')
    days=st.segmented_control('表示期間',[7,30,90,365,9999],default=90,format_func=lambda v:'すべて' if v==9999 else f'{v}日',key='portfolio_period') or 90
    history=history_series(data['history'],currency,days)
    history_chart(history,currency,mask)
    st.caption('記録された評価額の推移です。取引や入出庫による変化を含むため、運用利回りとは異なります。')
    if currency=='USD': st.caption('USD建ての履歴は、新しい記録から蓄積します。過去の円建て記録を現在の為替で置き換えることはしません。')
a,b=st.columns([1.2,1])
with a:
    with st.container(border=True):
        st.subheader('今日の変化をつくった銘柄')
        impacts(data['rows'],currency,mask)
with b:
    with st.container(border=True):
        st.subheader('資産の構成')
        composition(data['rows'])
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
    from database_supabase import get_latest_ai_comment
    comment=get_latest_ai_comment()
    if comment and not mask:
        st.markdown(f"<div class='ai-insight-card'><strong>分析メモ · {escape(comment['date'])}</strong><br>{escape(comment['comment'])}</div>",unsafe_allow_html=True)
    elif mask: st.caption('金額非表示中は、金額を含む可能性がある分析メモを隠しています。')
    else: st.caption('保存された分析メモはまだありません。')
