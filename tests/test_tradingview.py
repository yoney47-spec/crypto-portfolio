import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import MagicMock, Mock, patch

from tradingview_config import Market, market_for, widget_html


class TradingViewTests(unittest.TestCase):
    def setUp(self):
        self.st = types.ModuleType('streamlit')
        self.st.__path__ = []
        for name in ['caption','plotly_chart','info']:
            setattr(self.st, name, Mock())
        self.st.container = MagicMock()
        self.st.segmented_control = Mock(side_effect=lambda *a,**kw: kw['default'])
        components = types.ModuleType('streamlit.components')
        components.__path__ = []
        self.embed = types.ModuleType('streamlit.components.v1')
        self.embed.html = Mock()
        self.st.components = components
        components.v1 = self.embed
        service = types.ModuleType('portfolio_service')
        service.coin_history = Mock(return_value=[{'date':'2026-09-19', 'value':100}])
        self.history = service.coin_history
        charts = types.ModuleType('components.portfolio_charts')
        charts.line_figure = Mock()
        self.figure = charts.line_figure
        motion = types.ModuleType('components.motion')
        motion.loading = MagicMock()
        spec = importlib.util.spec_from_file_location('asset_chart_test',Path(__file__).parents[1]/'components/asset_chart.py')
        self.module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'streamlit':self.st,'streamlit.components':components,
            'streamlit.components.v1':self.embed,'portfolio_service':service,
            'components.portfolio_charts':charts,'components.motion':motion}):
            spec.loader.exec_module(self.module)
        self.row = dict(id=1,api_id='kaspa',symbol='KAS',holdings=12345,private_cost=99999)

    def test_known_spot_market_has_attribution_and_no_private_data(self):
        self.module.render_asset_chart(self.row,'JPY',False)
        html = self.embed.html.call_args.args[0]
        self.assertIn('KUCOIN:KASUSDT',html)
        self.assertIn('by TradingView',html)
        self.assertNotIn('12345',html)
        self.assertNotIn('99999',html)
        self.history.assert_not_called()
        captions=' '.join(c.args[0] for c in self.st.caption.call_args_list)
        self.assertIn('USDT建て',captions)
        self.assertIn('JPY建て',captions)

    def test_mask_never_mounts_tradingview_and_keeps_index_chart(self):
        self.module.render_asset_chart(self.row,'USD',True)
        self.embed.html.assert_not_called()
        self.history.assert_called_once_with('kaspa','USD',30)
        self.assertTrue(self.figure.call_args.args[2])

    def test_unknown_ticker_is_not_guessed(self):
        self.assertIsNone(market_for('unknown-kas-clone'))
        self.module.render_asset_chart(dict(self.row,api_id='unknown-kas-clone'),'JPY',False)
        self.embed.html.assert_not_called()
        self.history.assert_called_once()

    def test_selected_currency_fallback_fetches_only_requested_history(self):
        self.st.segmented_control.side_effect=['USDの価格推移',7]
        self.module.render_asset_chart(self.row,'USD',False)
        self.embed.html.assert_not_called()
        self.history.assert_called_once_with('kaspa','USD',7)

    def test_widget_cannot_switch_to_a_different_asset_or_fake_quote(self):
        html=widget_html(market_for('bitcoin'))
        options=json.loads(html.split(' async>')[1].split('</script>')[0])
        self.assertFalse(options['allow_symbol_change'])
        self.assertEqual(options['locale'],'ja')
        self.assertNotIn('currency',options)
        with self.assertRaises(ValueError):
            widget_html(Market('</script><script>alert(1)</script>','bad','bad'))


if __name__=='__main__':
    unittest.main()
