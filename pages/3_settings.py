import streamlit as st
from admin_auth import is_admin_authenticated,sign_in_admin
from access_control import (snapshot_backend_configuration_error,snapshot_admin_configuration_error,
                            is_snapshot_admin_unlocked,verify_snapshot_admin_pin)
from database_supabase import capture_portfolio_snapshot
from portfolio_service import public_data
from portfolio_logic import money
from components.shell import intro,preferences

currency,mask=preferences()
intro('設定','表示を整え、記録を管理。')
with st.container(border=True):
    st.subheader('表示設定')
    selected=st.segmented_control('保有資産の表示密度',['標準','コンパクト'],default=st.session_state.get('display_density','標準'),key='density_widget')
    if selected: st.session_state['display_density']=selected
    st.caption('通貨・金額の非表示・表示密度は、このタブでページを移動しても保持されます。')
    if st.button('表示データを再読み込み',icon=':material/refresh:'):
        public_data.clear();st.rerun()
    st.caption('価格への連続アクセスを避けるため、価格のキャッシュと待機時間は維持します。')

feedback=st.session_state.pop('snapshot_feedback',None)
if feedback:
    if feedback.get('ok'): st.success(f"{feedback['date']} の評価額を記録しました。")
    else: st.error(feedback.get('message','記録できませんでした。'))

def save_snapshot():
    with st.spinner('現在の評価額を記録中…'): result=capture_portfolio_snapshot()
    if result.get('ok'): public_data.clear()
    st.session_state['snapshot_feedback']=result
    st.rerun()

admin=is_admin_authenticated()
if not admin:
    with st.container(border=True):
        st.subheader('管理者ログイン')
        st.caption('取引の記録、銘柄の編集、目標の管理ができます。')
        with st.form('settings_admin_login'):
            email=st.text_input('メールアドレス',autocomplete='email')
            password=st.text_input('パスワード',type='password',autocomplete='current-password')
            submitted=st.form_submit_button('ログイン',type='primary')
        if submitted:
            ok,message=sign_in_admin(email,password)
            if ok: st.rerun()
            else: st.error(message)
    with st.expander('管理コードで評価額を記録'):
        config=snapshot_admin_configuration_error()
        if config: st.caption('管理者としてログインすると、記録機能を利用できます。')
        elif is_snapshot_admin_unlocked():
            if st.button('今日の評価額を記録',key='pin_snapshot'): save_snapshot()
        else:
            with st.form('settings_snapshot_pin'):
                pin=st.text_input('管理コード',type='password')
                verified=st.form_submit_button('確認して記録')
            if verified:
                ok,message=verify_snapshot_admin_pin(pin)
                if ok: save_snapshot()
                else: st.error(message)
else:
    with st.container(border=True):
        st.subheader('評価額の記録')
        data=public_data()
        history=data.get('history',[])
        if history:
            latest=history[-1]
            st.write(f"最新：{latest['date']} · {money(latest.get('total_value_'+currency.lower()),currency,masked=mask)}")
            st.caption(f"{len(history)}日分の記録")
        st.caption('JPYとUSDの評価額を記録します。同日分は最新の記録で更新します。管理者ログイン中は管理コード不要です。')
        config=snapshot_backend_configuration_error()
        if config: st.warning(config)
        if st.button('今日の評価額を記録',type='primary',disabled=bool(config),key='admin_snapshot'): save_snapshot()
    st.page_link('pages/2_transactions.py',label='取引履歴・CSV出力',icon=':material/receipt_long:')
    st.page_link('pages/4_goals.py',label='数量目標・目標配分',icon=':material/flag:')
