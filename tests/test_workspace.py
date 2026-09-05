from datetime import date
from unittest.mock import patch
import pytest
from streamlit.testing.v1 import AppTest
from portfolio_logic import build_portfolio, convert_trade, year_to_date, history_series, money
from components.transaction_editor import new_draft

HOLDINGS=[(1,'BTC','Bitcoin','bitcoin',None,'',2)]
PRICES={'bitcoin':{'usd':110,'jpy':16500,'usd_24h_change':10,'jpy_24h_change':10}}

def data(currency):
    return dict(build_portfolio(HOLDINGS,PRICES,{},currency),history=[],stats={},prices=PRICES,
                updated_at=None,source='test',stale=False,price_error=None)

def test_price_effect_and_missing_quotes():
    p=data('USD')
    assert p['change_amount']==pytest.approx(20)
    assert p['change_percent']==pytest.approx(10)
    absent=build_portfolio(HOLDINGS,{}, {},'JPY')
    assert absent['total'] is None and absent['missing']==['BTC']
    assert absent['change_amount'] is None

def test_history_never_converts_old_jpy_to_usd():
    rows=[{'date':'2026-09-05','total_value_jpy':1500}]
    assert history_series(rows,'USD',30,date(2026,9,5))==[]
    assert history_series(rows,'JPY',30,date(2026,9,5))[0]['value']==1500

def test_ytd_needs_baseline_and_complete_cash_flows():
    records=[{'date':'2025-12-31','total_value_usd':100}]
    assert year_to_date(records,170,{'net_flow_usd':20,'unknown_usd':False},'USD',date(2026,9,5))['amount']==50
    assert year_to_date([],170,{},'USD',date(2026,9,5))['amount'] is None
    assert year_to_date(records,170,{'net_flow_usd':20,'unknown_usd':True},'USD',date(2026,9,5))['amount'] is None

def test_jpy_trade_and_invalid_numbers():
    t=convert_trade('0.1','15000000','JPY',150)
    assert t['total_amount']==10000 and t['input_total']==1500000
    for qty,price,rate in [(float('nan'),1,150),(1,1,0),(-1,1,150),(1,float('inf'),150)]:
        with pytest.raises(ValueError): convert_trade(qty,price,'JPY',rate)
    assert money(.00001,'JPY',price=True)!='¥0'

def test_edit_preserves_saved_fx_clone_does_not():
    row={'id':7,'date':'2026-09-01T12:00:00+09:00','exchange_rate':145.5,
         'exchange_rate_date':'2026-09-01','exchange_rate_source':'ECB / Frankfurter'}
    assert new_draft(row)['saved_fx']['rate']==145.5
    assert new_draft(row,True)['saved_fx'] is None

@patch('portfolio_service.portfolio',side_effect=data)
def test_public_navigation_keeps_currency_and_masks(_portfolio):
    at=AppTest.from_file('app.py',default_timeout=10).run()
    assert not at.exception
    at.button_group(key='currency_widget').set_value('USD').run()
    at.toggle(key='mask_amounts').set_value(True).run()
    at.switch_page('pages/1_assets.py').run()
    assert not at.exception
    assert at.session_state['display_currency']=='USD'
    assert at.session_state['mask_amounts'] is True
    at.switch_page('pages/0_dashboard.py').run()
    assert not at.exception
    assert at.session_state['display_currency']=='USD'
    assert all('220' not in x.value for x in at.markdown if 'metric-grid' in x.value)

@patch('portfolio_service.portfolio',side_effect=data)
def test_private_pages_reject_anonymous(_portfolio):
    at=AppTest.from_file('app.py').run()
    for page in ['pages/2_transactions.py','pages/4_goals.py']:
        at.switch_page(page).run()
        assert not at.exception
        assert not at.number_input

@patch('access_control.is_admin_authenticated',return_value=True)
@patch('admin_auth.is_admin_authenticated',return_value=True)
@patch('components.transaction_editor.exchange_rate',return_value={'rate':150,'date':'2026-09-01','source':'test'})
@patch('database_supabase.get_assets_list',return_value=[(1,'Bitcoin','BTC')])
@patch('workspace_data.transaction_rows',return_value=[])
@patch('portfolio_service.portfolio',side_effect=data)
def test_admin_trade_preview_and_goal_validation(*_mocks):
    at=AppTest.from_file('app.py').run()
    at.switch_page('pages/2_transactions.py').run()
    assert not at.exception
    at.number_input(key='trade_field_1_quantity').set_value(0.1).run()
    at.number_input(key='trade_field_1_price').set_value(15000000).run()
    at.button(key='trade_field_1_review').click().run()
    assert not at.exception
    assert any('1,500,000' in x.value for x in at.markdown)

@patch('access_control.is_admin_authenticated',return_value=True)
@patch('admin_auth.is_admin_authenticated',return_value=True)
@patch('database_supabase.get_assets_list',return_value=[(1,'Bitcoin','BTC')])
@patch('workspace_data.goals',return_value=[])
@patch('workspace_data.save_goal',side_effect=RuntimeError('offline'))
@patch('portfolio_service.portfolio',side_effect=data)
def test_goal_save_failure_preserves_input(*_mocks):
    at=AppTest.from_file('app.py').run()
    at.switch_page('pages/4_goals.py').run()
    assert not at.exception
    at.number_input[0].set_value(0.1)
    next(b for b in at.button if b.label=='目標を保存').click().run()
    assert not at.exception
    assert at.number_input[0].value==0.1
    assert any('保存できませんでした' in x.value for x in at.error)
