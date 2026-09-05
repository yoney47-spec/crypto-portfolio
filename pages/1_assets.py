from io import BytesIO
import base64
import pandas as pd
from PIL import Image
import streamlit as st
from admin_auth import is_admin_authenticated
from components.shell import intro,preferences,freshness
from components.holdings import holdings_list
from portfolio_service import portfolio,search_coins
from market_data import CoinGeckoError
from database_supabase import get_all_assets,add_asset,update_asset,delete_asset

currency,mask=preferences()
intro('保有資産','銘柄を比較し、価格と保有状況を詳しく確認。')
admin=is_admin_authenticated()
mode=st.segmented_control('表示内容',['保有一覧','銘柄を管理'],default='保有一覧',key='assets_mode') if admin else '保有一覧'
if mode!='銘柄を管理':
    with st.spinner('保有資産を読み込み中…'): data=portfolio(currency)
    if data.get('error'): st.error(data['error']);st.stop()
    freshness(data)
    holdings_list(data,currency,mask)
else:
    assets=get_all_assets()
    st.caption('取引のない銘柄もここで登録・編集できます。保管先は管理者のみが閲覧できます。')
    action=st.radio('操作',['新しい銘柄を追加','登録済み銘柄を編集'],horizontal=True)
    current=None
    if action=='登録済み銘柄を編集':
        if not assets: st.info('登録された銘柄はありません。');st.stop()
        aid=st.selectbox('編集する銘柄',[a[0] for a in assets],format_func=lambda v:next(f'{a[2]} · {a[1]}' for a in assets if a[0]==v))
        current=next(a for a in assets if a[0]==aid)
    else:
        with st.form('coin_search_form'):
            query=st.text_input('銘柄名・シンボルを検索',placeholder='Bitcoin / BTC')
            search=st.form_submit_button('銘柄を探す')
        if search:
            if len(query.strip())<2: st.warning('2文字以上で検索してください。')
            else:
                try:
                    with st.spinner('銘柄を検索中…'): st.session_state['coin_results']=search_coins(query)
                except CoinGeckoError: st.error('検索を利用できませんでした。時間をおいてお試しください。')
        results=st.session_state.get('coin_results',[])
        if search and not results: st.info('候補がありません。別の名称で検索するか、下の詳細設定から登録できます。')
        if results:
            pick=st.selectbox('検索結果',range(len(results)),format_func=lambda i:f"{results[i]['name']} · {results[i]['symbol']}（{results[i]['api_id']}）")
            c=results[pick];current=(None,c['name'],c['symbol'],c['api_id'],c['icon_url'],'')
    aid=current[0] if current else None
    signature=f"{action}-{current[3] if current else 'manual'}"
    with st.form(f'asset_form_{signature}'):
        name=st.text_input('銘柄名',value=current[1] if current else '')
        symbol=st.text_input('シンボル',value=current[2] if current else '')
        location=st.text_input('保管先（非公開）',value=current[5] or '' if current else '',placeholder='取引所 / ウォレット')
        with st.expander('価格連携・アイコンの詳細設定',expanded=current is None):
            api_id=st.text_input('CoinGecko ID',value=current[3] or '' if current else '',help='検索結果から選ぶと自動で入力されます。')
            icon_url=st.text_input('アイコンURL',value=current[4] or '' if current else '')
            upload=st.file_uploader('アイコン画像',type=['png','jpg','jpeg','webp'])
        save=st.form_submit_button('変更を保存' if aid else '銘柄を登録',type='primary')
    if save:
        if not name.strip() or not symbol.strip() or not api_id.strip(): st.error('銘柄名・シンボル・価格連携IDを入力してください。')
        else:
            image_ok=True
            if upload:
                try:
                    if upload.size>5*1024*1024: raise ValueError('too large')
                    img=Image.open(upload);img.thumbnail((128,128));buffer=BytesIO();img.convert('RGBA').save(buffer,format='PNG')
                    icon_url='data:image/png;base64,'+base64.b64encode(buffer.getvalue()).decode()
                except Exception: st.error('画像を読み込めませんでした。5MB以下の画像を選んでください。');image_ok=False
            if image_ok:
                args=(name.strip(),symbol.strip(),api_id.strip(),icon_url,location.strip())
                ok=update_asset(aid,*args) if aid else add_asset(*args)
                if ok: st.cache_data.clear();st.success('銘柄を保存しました。')
                else: st.error('保存できませんでした。重複する銘柄や入力内容をご確認ください。')
    if aid:
        with st.expander('この銘柄を削除'):
            confirmed=st.checkbox(f'{current[2]} を削除する内容を確認しました')
            if st.button('銘柄を削除',disabled=not confirmed):
                ok,message=delete_asset(aid)
                if ok: st.cache_data.clear();st.rerun()
                else: st.error(message)
