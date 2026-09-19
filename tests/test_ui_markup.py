import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch

from components.ui_markup import animated_value, goal_markup, insight_markup, success_markup


class MarkupTests(unittest.TestCase):
    def setUp(self):
        self.row = dict(holdings=5, price=120, weight=23.5)
        self.goal = dict(asset_id=1, target_quantity=10, target_weight=30)

    def test_mask_removes_values_from_accessibility_and_progress_metadata(self):
        html = animated_value('123456.78', 'total', masked=True)
        self.assertNotIn('123456', html)
        self.assertIn('aria-label="••••••"', html)
        self.assertIn('data-motion-enabled="false"', html)
        html = goal_markup('BTC', self.row, self.goal, 'JPY', True)
        self.assertNotIn('50.0%', html)
        self.assertNotIn('progressbar', html)
        self.assertNotIn('600', html)
        self.assertIn('23.5%', html)  # Existing privacy policy retains allocations.

    def test_goal_compares_quantities_and_selected_currency(self):
        for currency, price in [('JPY', '¥600'), ('USD', '$600.00')]:
            with self.subTest(currency=currency):
                html = goal_markup('BTC', self.row, self.goal, currency)
                self.assertIn(price, html)
                self.assertIn('aria-label="50.0%"', html)
                self.assertIn('+6.5ポイント', html)
                for label in ['現在', '目標', 'あと']:
                    self.assertIn(f'<dt>{label}</dt>', html)

    def test_overachievement_retains_real_ratio_but_clamps_track(self):
        html = goal_markup('BTC', dict(self.row, holdings=15), self.goal, 'JPY')
        self.assertIn('aria-valuenow="100.0"', html)
        self.assertIn('aria-valuetext="150.0%"', html)
        self.assertIn('数量目標を達成しています。', html)

    def test_allocation_only_and_missing_price_are_readable(self):
        html = goal_markup('BTC', dict(self.row, weight=None), dict(self.goal, target_quantity=None), 'JPY')
        self.assertNotIn('progressbar', html)
        self.assertIn('価格が揃うと', html)
        html = goal_markup('BTC', dict(self.row, price=None), self.goal, 'JPY', complete=False)
        self.assertIn('現在評価額：—', html)
        self.assertIn('価格を取得できた分', html)

    def test_markup_escapes_external_and_user_text(self):
        attack = '<img src=x onerror=alert(1)>'
        for html in [success_markup(attack), animated_value(attack, '" onfocus="x'),
                     goal_markup(attack, self.row, self.goal, 'JPY'),
                     insight_markup(dict(date=attack, comment=attack))]:
            self.assertNotIn('<img', html)
            self.assertNotIn('data-motion-key="" onfocus', html)
            self.assertIn('&lt;img', html)

    def test_saved_insights_have_three_sections_and_legacy_fallback(self):
        record = dict(date='2026-09-19', sections=dict(overview='+2.4% の変化', drivers='BTCの影響', watch='配分を確認'))
        html = insight_markup(record)
        self.assertEqual(html.count('data-insight-card='), 3)
        self.assertEqual(html.count('role="tab"'), 3)
        self.assertIn('<strong class="cf-inline-number">+2.4%</strong>', html)
        self.assertNotEqual(html.split('data-insight-id="')[1].split('"')[0],
                            insight_markup(record, archive=True).split('data-insight-id="')[1].split('"')[0])
        legacy = insight_markup(dict(date='2026-06-01', comment='旧メモ'), archive=True)
        self.assertIn('旧メモ', legacy)
        self.assertNotIn('role="tab"', legacy)

    def test_loading_clears_placeholder_on_success_and_failure(self):
        st = types.ModuleType('streamlit')
        st.empty = Mock()
        spec = importlib.util.spec_from_file_location('motion_test', Path(__file__).parents[1] / 'components/motion.py')
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'streamlit': st}):
            spec.loader.exec_module(module)
        with module.loading('確認中', 'thinking') as status:
            status('保存中')
        st.empty.return_value.empty.assert_called_once()
        self.assertIn('保存中', st.empty.return_value.markdown.call_args.args[0])
        st.empty.reset_mock()
        with self.assertRaises(RuntimeError), module.loading('取得中'):
            raise RuntimeError('network failed')
        st.empty.return_value.empty.assert_called_once()


if __name__ == '__main__':
    unittest.main()
