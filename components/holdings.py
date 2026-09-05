from html import escape
import pandas as pd
import streamlit as st
from admin_auth import is_admin_authenticated
from portfolio_logic import money,quantity,percent,tone
from portfolio_service import coin_history
from components.portfolio_charts import line_figure


@st.dialog('銘柄の詳細', width='large')
def asset_detail(row, data, currency, mask):
    with st.container(border=True,key='asset-detail'):
        st.subheader(f"{row['symbol']} · {row['name']}")
        a,b=st.columns(2)
        a.metric('評価額',money(row['value'],currency,masked=mask))
        b.metric('保有数量',quantity(row['holdings'],masked=mask))
        c,d=st.columns(2)
        c.metric(f'現在価格（{currency}）',money(row['price'],currency,price=True,masked=mask))
        d.metric('24時間変化率',percent(row['change']))
        st.caption(f"構成比 {percent(row['weight'],signed=False)} · 24時間の影響額 {money(row['contribution'],currency,masked=mask,signed=True)}")
        days=st.segmented_control('価格推移',[7,30,90,365],default=30,format_func=lambda v:f'{v}日',key=f"asset_period_{row['id']}") or 30
        with st.spinner('価格推移を読み込み中…'):
            records=coin_history(row['api_id'],currency,days)
        if records:
            st.plotly_chart(line_figure(records,currency,mask,height=260),key=f"asset_chart_{row['id']}",config={'displayModeBar':False},width='stretch')
            st.caption(f"最新の記録：{records[-1]['date'][:16].replace('T',' ')} JST · {money(records[-1]['value'],currency,price=True,masked=mask)}")
        else:
            st.info('価格推移を取得できませんでした。しばらくしてもう一度お試しください。')
        quote=data['prices'].get(row['api_id'],{})
        fx=quote.get('jpy')/quote['usd'] if quote.get('usd') and quote.get('jpy') else None
        avg=row.get('avg_cost')
        if avg is not None and is_admin_authenticated():
            displayed=avg if currency=='USD' else avg*fx if fx else None
            st.caption(f"購入平均単価（参考）：{money(displayed,currency,price=True,masked=mask)}")
            st.caption('過去の購入総額 ÷ 購入数量。売却後の税務上の取得原価ではありません。円表示は現在の価格通貨比で換算した参考値です。')
        if is_admin_authenticated():
            st.session_state['goal_asset_id']=row['id']
            st.page_link('pages/4_goals.py',label='この資産の目標を設定',icon=':material/flag:')
            if st.toggle('この銘柄の取引履歴を表示',key=f"private_asset_transactions_{row['id']}"):
                from workspace_data import transaction_rows
                try:
                    tx=[t for t in transaction_rows() if t['asset_id']==row['id']]
                    table=[{'日付':t['date'][:10],'種類':t['type'],'数量':quantity(t['quantity'],masked=mask),'元の金額':money(t.get('input_total') if t.get('input_total') is not None else t['total_amount'],t.get('input_currency') or 'USD',masked=mask),'保管先':t.get('source') or '—'} for t in tx]
                    st.dataframe(pd.DataFrame(table),hide_index=True,width='stretch') if table else st.info('取引履歴はありません。')
                except Exception:
                    st.error('取引履歴を取得できませんでした。ログイン状態と接続をご確認ください。')
        if st.button('一覧に戻る',key='close_asset_detail',width='stretch'):
            st.rerun()


def holdings_list(data,currency,mask):
    rows=data['rows']
    selected=None
    a,b=st.columns([2,1])
    query=a.text_input('銘柄を検索',placeholder='BTC / Bitcoin',key='asset_search')
    sorting=b.selectbox('並び順',['評価額が大きい順','24時間の影響が大きい順','24時間上昇率順','銘柄名順'],key='asset_sort')
    rows=[r for r in rows if query.casefold() in f"{r['symbol']} {r['name']}".casefold()]
    if sorting=='24時間の影響が大きい順': rows.sort(key=lambda r:abs(r['contribution']) if r['contribution'] is not None else -1,reverse=True)
    elif sorting=='24時間上昇率順': rows.sort(key=lambda r:r['change'] if r['change'] is not None else float('-inf'),reverse=True)
    elif sorting=='銘柄名順': rows.sort(key=lambda r:r['symbol'])
    if not rows:
        st.info('条件に一致する保有資産はありません。')
        return
    compact=st.session_state.get('display_density')=='コンパクト'
    with st.container(key='holdings-desktop'):
        frame=pd.DataFrame([{'銘柄':r['symbol'],'数量':quantity(r['holdings'],masked=True) if mask else r['holdings'],
                             '評価額':money(None,currency,masked=True) if mask else r['value'],
                             '24時間 %':r['change'],'構成比 %':r['weight']} for r in rows])
        config={'評価額':st.column_config.TextColumn(f'評価額（{currency}）') if mask else st.column_config.NumberColumn(f'評価額（{currency}）',format='localized'),
                '数量':st.column_config.TextColumn('数量') if mask else st.column_config.NumberColumn('数量',format='%.8f'),
                '24時間 %':st.column_config.NumberColumn('24時間 %',format='%+.2f'),
                '構成比 %':st.column_config.NumberColumn('構成比 %',format='%.1f')}
        event=st.dataframe(frame,hide_index=True,column_config=config,width='stretch',height=min(560,45+len(rows)*(36 if compact else 48)),
                           row_height=36 if compact else 48,on_select='rerun',selection_mode='single-row',key='holdings_table')
        signature=(tuple(r['id'] for r in rows),tuple(event.selection.rows))
        if event.selection.rows and signature != st.session_state.get('holding_selection'):
            idx=event.selection.rows[0]
            if idx < len(rows): selected=rows[idx]
        st.session_state['holding_selection']=signature
        st.caption('行を選ぶと詳細を表示します。列名をクリックして数値を並べ替えできます。')
    with st.container(key='holdings-mobile'):
        with st.container(key='density-compact' if compact else 'density-standard'):
            for row in rows:
                with st.container(border=True):
                    html=f"<div class='asset-summary'><div><strong>{escape(row['symbol'])}</strong><p>{escape(row['name'])}</p></div><div class='asset-right'><strong>{escape(money(row['value'],currency,masked=mask))}</strong><p><span class='{tone(row['change'])}'>{escape(percent(row['change']))}</span> · 24時間</p></div></div>"
                    st.markdown(html,unsafe_allow_html=True)
                    if not compact: st.caption(f"{quantity(row['holdings'],masked=mask)} {row['symbol']} · 構成比 {percent(row['weight'],signed=False)}")
                    if st.button(f"{row['symbol']} の詳細",key=f"mobile_asset_{row['id']}",width='stretch'):
                        selected=row
    if selected:
        asset_detail(selected,data,currency,mask)
