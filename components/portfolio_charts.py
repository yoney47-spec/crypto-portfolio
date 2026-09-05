from html import escape
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from components.design_tokens import COLOR_ACTION, COLOR_GRID, COLOR_TEXT_MUTED, COLOR_POSITIVE, COLOR_NEGATIVE, FONT_UI
from portfolio_logic import money, percent, tone


def line_figure(records, currency, mask=False, height=320):
    values = [r['value'] for r in records]
    if mask:
        base = next((v for v in values if v > 0), None)
        values = [v / base * 100 if base else None for v in values]
    dates = [r['date'] for r in records]
    labels = [f"{str(d)[:10]}<br>{v:.2f}（基準100）" if mask and v is not None else f"{str(d)[:10]}<br>{money(v, currency, price=True)}" for d, v in zip(dates, values)]
    # Scale only the plotted axis. Hover labels and selected-day values remain exact.
    magnitude = max((abs(v) for v in values if v is not None), default=0)
    scale, unit = 1, '基準100' if mask else currency
    if not mask and currency == 'JPY':
        if magnitude >= 100_000_000:
            scale, unit = 100_000_000, '億円'
        elif magnitude >= 10_000:
            scale, unit = 10_000, '万円'
    plotted = [v / scale if v is not None else None for v in values]
    fig = go.Figure(go.Scatter(x=dates, y=plotted, mode='lines+markers', line=dict(color=COLOR_ACTION, width=2.5),
                             marker=dict(size=5), customdata=labels, hovertemplate='%{customdata}<extra></extra>'))
    fig.update_layout(height=height, margin=dict(l=4, r=8, t=28, b=8), font=dict(family=FONT_UI,size=12,color=COLOR_TEXT_MUTED),
                      paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', clickmode='event+select', dragmode=False,
                      xaxis=dict(tickformat='%m/%d', nticks=4, showgrid=False, fixedrange=True, automargin=True),
                      yaxis=dict(title=None, nticks=4, gridcolor=COLOR_GRID, fixedrange=True, automargin=True))
    fig.add_annotation(x=0, y=1.02, xref='paper', yref='paper', text=unit,
                       showarrow=False, xanchor='left', yanchor='bottom',
                       font=dict(size=12, color=COLOR_TEXT_MUTED))
    return fig


def history_chart(records, currency, mask, key='history'):
    if not records:
        st.info(f"この期間の{currency}建ての履歴はまだありません。管理者が記録すると表示されます。")
        return
    event = st.plotly_chart(line_figure(records,currency,mask), key=key, on_select='rerun', selection_mode='points',
                           config={'displayModeBar':False, 'scrollZoom':False}, width='stretch')
    selected = event.selection.points
    idx = selected[0].get('point_index',len(records)-1) if selected else len(records)-1
    idx = min(int(idx),len(records)-1)
    row = records[idx]
    st.caption(f"{row['date']} の評価額：{money(row['value'],currency,masked=mask)} · 点をタップすると記録日を確認できます")
    with st.expander('記録日を一覧で確認'):
        st.dataframe(pd.DataFrame([{'記録日':r['date'],'評価額':money(r['value'],currency,masked=mask)} for r in reversed(records)]),hide_index=True,width='stretch')


def composition(rows):
    rows = [r for r in rows if r.get('weight') is not None]
    if not rows:
        st.info('価格が揃うと構成比を表示します。')
        return
    top=rows[:5]
    labels=[r['symbol'] for r in top]; weights=[r['weight'] for r in top]
    if len(rows)>5:
        labels.append('その他'); weights.append(sum(r['weight'] for r in rows[5:]))
    fig=go.Figure(go.Pie(labels=labels,values=weights,hole=.7,sort=False,textinfo='none',
                        marker=dict(colors=[COLOR_ACTION,'#b37716','#15803d','#9c5364','#61748e','#72747d'],line=dict(color='#ffffff',width=3)),
                        hovertemplate='%{label} %{percent}<extra></extra>'))
    fig.update_layout(height=265,margin=dict(l=8,r=8,t=8,b=8),font=dict(family=FONT_UI,size=13),
                      paper_bgcolor='rgba(0,0,0,0)',legend=dict(orientation='h',y=-.03,x=.5,xanchor='center'))
    with st.container(key='composition-desktop'):
        st.plotly_chart(fig,config={'displayModeBar':False},width='stretch')
    with st.container(key='composition-mobile'):
        items = ''.join(f"<div class='composition-row'><dt>{escape(label)}</dt><dd>{weight:.1f}%</dd></div>"
                        for label,weight in zip(labels,weights))
        st.markdown(f"<dl class='composition-list'>{items}</dl>",unsafe_allow_html=True)
        with st.container(key='composition-chart-toggle'):
            with st.expander('円グラフで確認'):
                st.plotly_chart(fig,config={'displayModeBar':False},width='stretch',key='mobile_composition')


def impacts(rows,currency,mask):
    ranked=sorted((r for r in rows if r['contribution'] is not None),key=lambda r:abs(r['contribution']),reverse=True)[:5]
    if not ranked:
        st.info('24時間変化率を取得できると表示されます。')
        return
    maximum=max(abs(r['contribution']) for r in ranked) or 1
    html=''
    for row in ranked:
        v=row['contribution']; width=abs(v)/maximum*100
        html+=f"<div class='impact-row'><span>{escape(row['symbol'])}</span><div class='impact-track'><div class='impact-bar {tone(v)}' style='width:{width:.2f}%'></div></div><span class='impact-amount'>{escape(money(v,currency,masked=mask,signed=True))}</span></div>"
    st.markdown(html,unsafe_allow_html=True)
    st.caption('現在の保有数量を固定した、24時間の値動きによる影響額。入出庫の影響は含みません。')
