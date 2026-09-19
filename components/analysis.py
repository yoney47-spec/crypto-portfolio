from datetime import datetime

import streamlit as st

from analysis_logic import ERROR_MESSAGES
from analysis_service import daily_analysis
from portfolio_logic import JST, percent
from components.ui_markup import insight_markup
from components.motion import loading


def _time(value):
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00')).astimezone(JST).strftime('%m月%d日 %H:%M JST')
    except (ValueError, TypeError):
        return '不明'


def _memo(record, *, archive=False):
    st.markdown(insight_markup(record, archive=archive), unsafe_allow_html=True)
    if record.get('prices_updated_at'):
        st.caption(f"データ：{_time(record['prices_updated_at'])} · 生成：{_time(record['created_at'])} · Gemini")
        st.caption('USD価格の24時間変化と構成比に基づく観察メモです。入出金を含む運用損益や最新ニュースの分析ではありません。')


def render_analysis(data, mask):
    st.subheader('分析メモ')
    if mask:
        st.caption('金額非表示中は分析メモを隠しています。')
        return
    with loading('本日の分析メモを確認中…', kind='thinking') as update:
        result = daily_analysis(data, on_status=update)
    records = result.get('records', [])
    today = datetime.now(JST).date().isoformat()
    current = next((r for r in records if r['date'] == today), None)
    if current:
        _memo(current)
    else:
        status = result.get('status')
        code = status if status in ('processing', 'daily_limit') else result.get('error')
        st.info(ERROR_MESSAGES.get(code, '本日の分析メモはまだ保存されていません。'))
        if result.get('retry_at') and status != 'daily_limit':
            st.caption(f"次の試行：{_time(result['retry_at'])} 以降、この欄を開いたとき")
        context = result.get('context')
        if context:
            st.write('現在のデータから確認できること')
            top = context['top_assets'][0]
            st.write(f"最大の構成比：{top['symbol']} {top['weight_percent']:.1f}%")
            st.write(f"24時間の価格影響：{percent(context['change_percent'])}（USD基準・変化率を取得できた銘柄の範囲）")
            st.caption('上の数値はデータの集計です。AIが生成した文章ではありません。')
        if st.button('分析メモの状態を更新', key='refresh_analysis', icon=':material/refresh:'):
            st.rerun()
    st.caption('その日最初にこの欄を開いたときに生成し、同じ日のメモを共有します。日付は日本時間です。')
    older = [r for r in records if r['date'] < today]
    if older:
        with st.expander(f"過去のメモ · 最新 {older[0]['date']}"):
            record = older[0]
            if len(older) > 1:
                selected = st.selectbox('記録日', [r['date'] for r in older], key='analysis_archive_date')
                record = next(r for r in older if r['date'] == selected)
            _memo(record, archive=True)
