"""Read-only dashboard fragment; no AI generation or private form reruns."""
from datetime import datetime

import streamlit as st

from market_data import CURRENT_PRICE_TTL_SECONDS
from portfolio_service import portfolio
from portfolio_logic import year_to_date, history_series, JST
from components.shell import overview, freshness
from components.portfolio_charts import history_chart, composition, impacts
from components.motion import loading
from dashboard_refresh import refresh_dashboard


@st.fragment(run_every=60)
def render_live_dashboard(currency, mask, view_id):
    # Timer ticks only check the local schedule. Network reads remain around
    # ten minutes apart and the existing cross-session API cache is preserved.
    state = st.session_state.setdefault('dashboard_refresh', {})
    def fetch():
        return refresh_dashboard(state, currency, view_id, portfolio, price_ttl=CURRENT_PRICE_TTL_SECONDS)
    if currency not in state:
        with loading('ポートフォリオを読み込み中…'):
            entry = fetch()
    else:
        entry = fetch()
    data = entry['data']
    if data.get('error'):
        st.error(data['error'])
        return
    if entry['failed']:
        st.warning('自動更新できなかったため、前回の表示を保っています。約10分後に再確認します。')
    if not data['rows']:
        st.info('保有資産はまだありません。管理者が取引を登録すると表示されます。')
        return
    checked = datetime.fromtimestamp(entry['checked'], JST).strftime('%H:%M:%S')
    st.caption(f'約10分ごとに自動更新 · 最終確認 {checked} JST')
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
        if currency=='USD' and any(r.get('estimated') for r in history):
            st.caption('過去のUSD未記録分は、当日の日次為替（休業日は直前の公表値）で円の記録を換算した参考値です。為替変動のため、円とドルでは推移の形に差が出ます。')
    a,b=st.columns([1.2,1])
    with a:
        with st.container(border=True):
            st.subheader('今日の変化をつくった銘柄')
            impacts(data['rows'],currency,mask)
    with b:
        with st.container(border=True):
            st.subheader('資産の構成')
            composition(data['rows'])
