import streamlit as st
from access_control import stop_on_private_page
from components.shell import intro,preferences
from database_supabase import get_assets_list
from portfolio_service import portfolio
from portfolio_logic import goal_progress,quantity,percent,money
from workspace_data import goals,save_goal,delete_goal

stop_on_private_page()
currency,mask=preferences()
intro('目標','積み上げたい数量と、目指す資産配分をひとつの場所で。')
try: saved=goals()
except Exception: st.error('目標を読み込めませんでした。接続とログイン状態を確認してください。');st.stop()
data=portfolio(currency)
if data.get('error'): st.error(data['error']);st.stop()
assets=get_assets_list();rows={r['id']:r for r in data['rows']}
if not assets: st.info('銘柄を登録すると目標を設定できます。');st.page_link('pages/1_assets.py',label='銘柄を登録');st.stop()
if not saved: st.info('まずは1つ、目標を設定しましょう。数量だけ、配分だけでも設定できます。')
for goal in saved:
    aid=goal['asset_id'];row=rows.get(aid,{'holdings':0,'weight':0,'price':None})
    symbol=next((a[2] for a in assets if a[0]==aid),'—')
    progress=goal_progress(row['holdings'],goal.get('target_quantity'),row['weight'],goal.get('target_weight'))
    with st.container(border=True):
        st.subheader(symbol)
        if progress['ratio'] is not None:
            ratio=progress['ratio']
            st.progress(min(max(ratio,0),1),text=f'数量目標の達成率 {ratio*100:.1f}%')
            st.write(f"{quantity(row['holdings'],masked=mask)} / {quantity(goal['target_quantity'],masked=mask)} {symbol}")
            st.caption(f"あと {quantity(progress['remaining'],masked=mask)} {symbol} · 現在価格で {money(progress['remaining']*row['price'] if row['price'] is not None else None,currency,masked=mask)}")
        if goal.get('target_weight') is not None:
            st.write(f"配分：現在 {percent(row['weight'],signed=False)} → 目標 {percent(goal['target_weight'],signed=False)}")
            st.caption(f"目標との差 {progress['weight_gap']:+.1f}ポイント" if progress['weight_gap'] is not None else '価格が揃うと配分差を計算します。')
            if not data['complete']: st.caption('現在の構成比は価格を取得できた分で計算しています。')
st.subheader('目標を設定・変更')
if mask:
    st.info('目標の入力値を表示するには「金額を隠す」をオフにしてください。');st.stop()
aids=[a[0] for a in assets]
pref=st.session_state.get('goal_asset_id')
aid=st.selectbox('銘柄',aids,index=aids.index(pref) if pref in aids else 0,format_func=lambda v:next(f'{a[2]} · {a[1]}' for a in assets if a[0]==v))
existing=next((g for g in saved if g['asset_id']==aid),{})
with st.form(f'goal_editor_{aid}'):
    use_qty=st.checkbox('数量の目標を設定',value=existing.get('target_quantity') is not None or not existing)
    target=st.number_input('目標数量',min_value=0.0,value=float(existing.get('target_quantity') or 0),format='%.8f',help='例：BTCを0.1枚。自分で決めた目標を入力してください。')
    use_weight=st.checkbox('配分の目標を設定',value=existing.get('target_weight') is not None)
    weight=st.number_input('目標配分（%）',min_value=0.0,max_value=100.0,value=float(existing.get('target_weight') or 0),step=1.0)
    submitted=st.form_submit_button('目標を保存',type='primary')
if submitted:
    try:
        save_goal(aid,target if use_qty else None,weight if use_weight else None)
        st.session_state['goal_asset_id']=aid;st.rerun()
    except ValueError as e: st.error(str(e))
    except Exception: st.error('保存できませんでした。入力内容を保持しています。接続とログイン状態を確認してください。')
if existing:
    with st.expander('この目標を削除'):
        confirmed=st.checkbox('この銘柄の目標を削除する')
        if st.button('目標を削除',disabled=not confirmed):
            try: delete_goal(aid);st.rerun()
            except Exception: st.error('削除できませんでした。再度お試しください。')
