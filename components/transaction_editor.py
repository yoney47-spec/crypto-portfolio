from datetime import datetime, timedelta
import math
import streamlit as st
from portfolio_logic import JST,convert_trade,money,quantity
from portfolio_service import exchange_rate
from database_supabase import add_transaction,update_transaction,delete_transaction

TYPES={'Buy':'購入','Sell':'売却','Transfer':'出庫','Airdrop':'エアドロップ','Staking Reward':'ステーキング報酬','Interest':'利息','Gift':'贈与の受取'}


def as_jst(value):
    dt=datetime.fromisoformat(str(value).replace('Z','+00:00'))
    return dt.replace(tzinfo=JST) if dt.tzinfo is None else dt.astimezone(JST)


def new_draft(row=None,clone=False):
    now=datetime.now(JST).replace(second=0,microsecond=0)
    row=row or {}
    dt=now if clone or not row else as_jst(row['date'])
    return dict(id=None if clone else row.get('id'),date=dt.date(),time=dt.time().replace(tzinfo=None),
                type=row.get('type','Buy'),asset_id=row.get('asset_id'),quantity=float(row.get('quantity') or 0),
                currency=(row.get('input_currency') or 'USD') if row else 'JPY',price=float(row.get('input_price') if row.get('input_price') is not None else row.get('price_per_unit') or 0),
                fee=float(row.get('fee_amount') or 0),fee_currency=row.get('fee_currency') or 'USD',source=row.get('source') or '',notes=row.get('notes') or '',
                manual_rate=None,
                original_day=dt.date() if row and not clone else None,
                saved_fx={'rate':float(row['exchange_rate']),'date':str(row['exchange_rate_date']),
                          'source':row['exchange_rate_source']} if row.get('exchange_rate') and not clone else None)


def begin_edit(row=None,clone=False):
    st.session_state['trade_draft']=new_draft(row,clone)
    st.session_state['trade_revision']=st.session_state.get('trade_revision',0)+1
    st.session_state['trade_mode']='入力'


def open_editor(row, clone=False):
    begin_edit(row,clone)
    st.session_state['trade_mode_control']='入力'


def duplicate_candidates(records,dt,aid,qty,exclude=None):
    return [r for r in records if r['id']!=exclude and r['asset_id']==aid
            and math.isclose(float(r['quantity']),float(qty),rel_tol=1e-12,abs_tol=0)
            and abs((as_jst(r['date'])-dt).total_seconds())<=300]


@st.dialog('取引内容を確認',width='small')
def confirm_save(payload,editing):
    st.write(f"{payload['symbol']} · {TYPES[payload['trans_type']]}")
    st.write(payload['date_obj'].strftime('%Y年%m月%d日 %H:%M JST'))
    st.write(f"数量：{quantity(payload['quantity'])}")
    meta=payload['input_metadata']
    st.write(f"入力金額：{money(meta['input_total'],meta['input_currency'])}")
    if meta['input_currency']=='JPY': st.caption(f"換算単価 {money(payload['price_per_unit'],'USD',price=True)} · 1 USD = {meta['exchange_rate']:,.4f} JPY")
    if payload['fee_amount']: st.write(f"手数料：{quantity(payload['fee_amount'])} {payload['fee_currency']}")
    if payload['source']: st.write(f"保管先：{payload['source']}")
    st.caption('この取引記録を保存します。取引所での売買や送金は実行されません。')
    if st.button('変更を保存' if editing else 'この内容で記録',type='primary',key='trade_confirm_save',width='stretch'):
        args={k:v for k,v in payload.items() if k not in ('symbol','transaction_id')}
        if editing:
            args.pop('skip_duplicate_check',None)
            ok=update_transaction(payload['transaction_id'],**args)
        else: ok=add_transaction(**args)
        if ok:
            begin_edit()
            st.session_state['trade_feedback']='取引を保存しました。'
            st.rerun()
    if st.button('入力に戻る',key='trade_cancel_confirm',width='stretch'): st.rerun()


@st.dialog('取引を削除')
def confirm_delete(row):
    st.write(f"{as_jst(row['date']):%Y年%m月%d日 %H:%M} · {row['symbol']} · {TYPES.get(row['type'],row['type'])}")
    st.write(f"数量 {quantity(row['quantity'])}")
    st.caption('この取引の記録を削除すると、保有数量と集計が更新されます。')
    if st.button('この取引を削除',type='primary',key='trade_confirm_delete'):
        if delete_transaction(row['id']):
            st.session_state['trade_feedback']='取引を削除しました。';st.rerun()


def render_editor(assets,records):
    if 'trade_draft' not in st.session_state: begin_edit()
    draft=st.session_state['trade_draft']
    rev=st.session_state.get('trade_revision',0)
    key=lambda name:f'trade_field_{rev}_{name}'
    editing=draft.get('id') is not None
    st.subheader('取引を編集' if editing else '取引を記録')
    if not editing:
        template=st.selectbox('入力テンプレート',['通常の取引','ステーキング報酬','エアドロップ','利息'],key=key('template'))
        if st.button('テンプレートを適用',key=key('apply_template')):
            draft['type']={'通常の取引':'Buy','ステーキング報酬':'Staking Reward','エアドロップ':'Airdrop','利息':'Interest'}[template]
            if draft['type']!='Buy':draft['price']=0.0;draft['fee']=0.0
            st.session_state['trade_revision']=rev+1;st.rerun()
    aids=[a[0] for a in assets]
    a,b=st.columns(2)
    aid=a.selectbox('銘柄',aids,index=aids.index(draft['asset_id']) if draft['asset_id'] in aids else 0,
                    format_func=lambda v:next(f'{x[2]} · {x[1]}' for x in assets if x[0]==v),key=key('asset'))
    typ=b.selectbox('取引の種類',list(TYPES),index=list(TYPES).index(draft['type']),format_func=TYPES.get,key=key('type'))
    a,b=st.columns(2)
    day=a.date_input('取引日（日本時間）',value=draft['date'],max_value=datetime.now(JST).date(),key=key('date'))
    time=b.time_input('時刻',value=draft['time'],key=key('time'))
    a,b=st.columns(2)
    qty=a.number_input('数量',min_value=0.0,value=draft['quantity'],format='%.8f',key=key('quantity'))
    currency=b.selectbox('入力通貨',['JPY','USD'],index=['JPY','USD'].index(draft['currency']),key=key('currency'))
    price=st.number_input(f'1枚あたりの単価（{currency}）',min_value=0.0,value=draft['price'],format='%.8f',key=key('price'))
    if typ in ('Airdrop','Staking Reward','Interest'): st.caption('無償取得は単価0でも記録できます。受取時の参考単価を記録する場合は入力してください。')
    if typ=='Transfer': st.caption('出庫は保有数量から減算します。受渡時の評価単価を入力すると年初来損益の調整に利用します。自己口座間の移動で総保有量が変わらない場合は登録不要です。')
    if typ=='Gift': st.caption('贈与の受取は保有数量に加算します。受取時の評価単価を入力すると年初来損益の入金調整に利用します。')
    fx=draft.get('saved_fx') if editing and day==draft.get('original_day') else None
    if fx is None: fx=exchange_rate(day.isoformat())
    manual=st.checkbox('換算レートを手入力',value=draft.get('manual_rate') is not None,key=key('manual'))
    if manual:
        rate=st.number_input('1 USDあたりのJPY',min_value=0.0,value=float(draft.get('manual_rate') or (fx['rate'] if fx else 0)),format='%.6f',key=key('rate'))
        fx_info={'rate':rate,'date':day.isoformat(),'source':'手入力'}
    else: fx_info=fx
    if fx_info: st.caption(f"換算レート：1 USD = {fx_info['rate']:,.4f} JPY · {fx_info['date']} · {fx_info['source']}")
    elif currency=='JPY': st.warning('この日の参考レートを取得できませんでした。換算レートを手入力してください。')
    else: st.caption('この日の円換算レートは未取得です。USD建てのまま記録できます。')
    calculated=None;error=None
    try:
        calculated=convert_trade(qty,price,currency,fx_info['rate'] if fx_info else None)
        st.metric('入力金額の合計',money(calculated['input_total'],currency))
        if currency=='JPY':st.caption(f"USD換算：{money(calculated['total_amount'],'USD')}（手数料を除く）")
    except ValueError as exc: error=str(exc);st.caption(error)
    with st.expander('手数料・保管先・メモ',expanded=editing):
        a,b=st.columns(2)
        fee=a.number_input('手数料',min_value=0.0,value=draft['fee'],format='%.8f',key=key('fee'))
        fee_currency=b.text_input('手数料の通貨',value=draft['fee_currency'],max_chars=12,key=key('fee_currency'))
        source=st.text_input('取引所・ウォレット',value=draft['source'],key=key('source'))
        notes=st.text_area('メモ',value=draft['notes'],key=key('notes'))
        st.caption('手数料は別項目として保存します。保有数量から手数料を自動減算しません。')
    draft.update(date=day,time=time,type=typ,asset_id=aid,quantity=qty,currency=currency,price=price,fee=fee,fee_currency=fee_currency,source=source,notes=notes,manual_rate=fx_info['rate'] if manual else None)
    dt=datetime.combine(day,time,tzinfo=JST)
    duplicates=duplicate_candidates(records,dt,aid,qty,exclude=draft.get('id')) if qty else []
    allow=False
    if duplicates:
        st.warning(f'同じ銘柄・数量で、時刻が近い取引が{len(duplicates)}件あります。')
        for row in duplicates[:3]: st.caption(f"{as_jst(row['date']):%Y/%m/%d %H:%M} · {TYPES.get(row['type'],row['type'])} · {quantity(row['quantity'])}")
        allow=st.checkbox('重複候補を確認し、別の取引として保存する',key=key('allow_duplicate'))
    if st.button('内容を確認',type='primary',width='stretch',disabled=bool(error) or bool(duplicates and not allow),key=key('review')):
        if not fee_currency.strip():st.error('手数料の通貨を入力してください。');return
        metadata={k:calculated[k] for k in ('input_currency','input_price','input_total')}
        metadata.update(exchange_rate=fx_info['rate'] if fx_info else None,exchange_rate_source=fx_info['source'] if fx_info else None,exchange_rate_date=fx_info['date'] if fx_info else None)
        payload=dict(date_obj=dt,trans_type=typ,asset_id=aid,quantity=calculated['quantity'],price_per_unit=calculated['price_per_unit'],total_amount=calculated['total_amount'],
                     notes=notes,fee_amount=fee,fee_currency=fee_currency.strip().upper(),source=source,input_metadata=metadata,
                     skip_duplicate_check=allow,transaction_id=draft.get('id'),symbol=next(a[2] for a in assets if a[0]==aid))
        confirm_save(payload,editing)
    if editing and st.button('編集をやめて新規入力',key=key('reset')):begin_edit();st.rerun()
