from datetime import datetime
import pandas as pd
import streamlit as st
from access_control import stop_on_private_page
from database_supabase import get_assets_list
from workspace_data import transaction_rows
from portfolio_logic import JST,money,quantity
from components.shell import intro,preferences
from components.transaction_editor import TYPES,render_editor,open_editor,as_jst,confirm_delete

stop_on_private_page()
currency,mask=preferences()
intro('取引','円で入力し、記録を残す。履歴から次の取引もすぐに。')
feedback=st.session_state.pop('trade_feedback',None)
if feedback:st.success(feedback)
if mask:st.info('取引の入力・履歴・CSVを表示するには「金額を隠す」をオフにしてください。');st.stop()
try: rows=transaction_rows()
except Exception:st.error('取引履歴を取得できませんでした。接続とログイン状態をご確認ください。');st.stop()
assets=get_assets_list()
if not assets:st.info('先に銘柄を登録してください。');st.page_link('pages/1_assets.py',label='銘柄を登録');st.stop()
mode=st.radio('操作',['入力','履歴'],horizontal=True,index=['入力','履歴'].index(st.session_state.get('trade_mode','入力')),key='trade_mode_control')
# A requested edit/clone takes precedence once over the persistent radio value.
if st.session_state.pop('trade_open_editor',False):mode='入力'
st.session_state['trade_mode']=mode
if mode=='入力':render_editor(assets,rows)
else:
    a,b=st.columns(2)
    query=a.text_input('銘柄・保管先・メモを検索')
    typ=b.selectbox('種類',['すべて']+list(TYPES),format_func=lambda v:TYPES.get(v,v))
    current=[r for r in rows if (typ=='すべて' or r['type']==typ) and query.casefold() in f"{r['symbol']} {r.get('source','')} {r.get('notes','')}".casefold()]
    st.caption(f'{len(current)}件の取引')
    def original_amount(r):return money(r['input_total'],r['input_currency']) if r.get('input_total') is not None else money(r['total_amount'],'USD')
    export=pd.DataFrame([{**{k:v for k,v in r.items() if k not in ('asset_name',)},'date':as_jst(r['date']).isoformat()} for r in current])
    for col in export.select_dtypes(include='object').columns:
        export[col]=export[col].map(lambda v:"'"+v if isinstance(v,str) and v.startswith(('=','+','-','@','\t','\r')) else v)
    st.download_button('表示中の取引をCSVで保存',data=export.to_csv(index=False).encode('utf-8-sig'),file_name=f'cryptofolio_transactions_{datetime.now(JST):%Y%m%d}.csv',mime='text/csv')
    if not current:st.info('一致する取引はありません。');st.stop()
    frame=pd.DataFrame([{'日時':as_jst(r['date']).strftime('%Y/%m/%d %H:%M'),'銘柄':r['symbol'],'種類':TYPES.get(r['type'],r['type']),'数量':float(r['quantity']),'USD金額':float(r['total_amount']),'元の金額':original_amount(r)} for r in current])
    selected=None
    with st.container(key='trades-desktop'):
        event=st.dataframe(frame,hide_index=True,width='stretch',on_select='rerun',selection_mode='single-row',key='trade_history_table',
                           column_config={'数量':st.column_config.NumberColumn(format='%.8f'),'USD金額':st.column_config.NumberColumn(format='localized')})
        st.caption('行を選択して編集・複製・削除できます。元の通貨と換算レートは取引ごとに保持します。')
        selected=current[event.selection.rows[0]] if event.selection.rows and event.selection.rows[0]<len(current) else None
    with st.container(key='trades-mobile'):
        page_count=max(1,(len(current)+9)//10)
        page=st.selectbox('履歴のページ',range(page_count),format_func=lambda i:f'{i+1} / {page_count}',key='trade_mobile_page')
        for row in current[page*10:page*10+10]:
            with st.container(border=True):
                st.write(f"{row['symbol']} · {TYPES.get(row['type'],row['type'])}")
                st.caption(f"{as_jst(row['date']):%Y/%m/%d %H:%M} · {quantity(row['quantity'])}枚")
                st.write(original_amount(row))
                left,right=st.columns(2)
                left.button('編集',key=f"trade_mobile_edit_{row['id']}",on_click=open_editor,args=(row,False),width='stretch')
                right.button('複製',key=f"trade_mobile_clone_{row['id']}",on_click=open_editor,args=(row,True),width='stretch')
                with st.expander('換算・メモ・削除'):
                    if row.get('exchange_rate'): st.caption(f"1 USD = {row['exchange_rate']} JPY · {row.get('exchange_rate_date','')}")
                    if row.get('notes'): st.write(row['notes'])
                    if st.button('この取引を削除',key=f"trade_mobile_delete_{row['id']}"): confirm_delete(row)
    if selected:
        st.subheader(f"{selected['symbol']} · {as_jst(selected['date']):%Y/%m/%d %H:%M}")
        st.write(f"{TYPES.get(selected['type'],selected['type'])} · {quantity(selected['quantity'])}枚 · {original_amount(selected)}")
        if selected.get('exchange_rate'):st.caption(f"1 USD = {selected['exchange_rate']} JPY · {selected.get('exchange_rate_date','')} · {selected.get('exchange_rate_source','')}")
        if selected.get('notes'):st.write(selected['notes'])
        a,b,c=st.columns(3)
        a.button('編集',width='stretch',on_click=open_editor,args=(selected,False))
        b.button('複製して入力',width='stretch',on_click=open_editor,args=(selected,True))
        if c.button('削除',width='stretch'):confirm_delete(selected)
