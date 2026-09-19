import copy
from datetime import datetime, timedelta, timezone
import json
import sys
import types
import unittest
from unittest.mock import Mock, patch

from analysis_logic import analysis_context
from gemini_client import AnalysisUnavailable, generate_daily_analysis, validate_sections, resolve_model

# Keep these tests usable in minimal environments without network installs.
try:
    import requests
except ModuleNotFoundError:
    requests = types.ModuleType('requests')
    requests.get = Mock()
    requests.post = Mock()
    requests.exceptions = types.SimpleNamespace(RequestException=RuntimeError)
    sys.modules['requests'] = requests

SECTIONS = {k: '確認できるデータに基づいた分析コメントです。' for k in ('overview', 'drivers', 'watch')}


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 9, 8, 4, tzinfo=timezone.utc)
        self.data = {'updated_at': self.now, 'rows': [
            {'api_id': 'large', 'symbol': 'BTC', 'holdings': 100, 'value': 999, 'weight': 1, 'private_cost': 5},
            {'api_id': 'small', 'symbol': 'KAS', 'holdings': 1, 'value': 1, 'weight': 99}],
            'prices': {'large': {'usd': 10, 'jpy': 1000, 'usd_24h_change': 10},
                       'small': {'usd': 10, 'jpy': 1000, 'usd_24h_change': 100}}}

    def test_currency_independent_and_influence_not_percent_ranking(self):
        context = analysis_context(self.data, self.now)
        self.assertEqual(context['drivers'][0]['symbol'], 'BTC')
        self.assertAlmostEqual(context['top_assets'][0]['weight_percent'], 99.01)
        changed = copy.deepcopy(self.data)
        changed['rows'][0]['value'] = 900_000
        changed['rows'][0]['weight'] = 80
        self.assertEqual(context, analysis_context(changed, self.now))
        serialized = json.dumps(context)
        for forbidden in ('holdings', 'private_cost', 'total_value', '1000'):
            self.assertNotIn(forbidden, serialized)

    def test_missing_changes_are_not_zero_and_partial_is_explicit(self):
        self.data['prices']['small']['usd_24h_change'] = None
        context = analysis_context(self.data, self.now)
        self.assertFalse(context['change_complete'])
        self.assertEqual(context['top_assets'][1]['change_24h_percent'], None)
        self.assertAlmostEqual(context['change_percent'], 10)
        self.assertEqual(len(context['drivers']), 1)

    def test_stale_future_and_previous_day_prices_are_rejected(self):
        for stamp in (self.now - timedelta(minutes=16), self.now + timedelta(minutes=1), None):
            with self.subTest(stamp=stamp), self.assertRaises(AnalysisUnavailable):
                analysis_context(dict(self.data, updated_at=stamp), self.now)
        midnight = self.now.replace(hour=15, minute=1)
        with self.assertRaises(AnalysisUnavailable):
            analysis_context(dict(self.data, updated_at=midnight - timedelta(minutes=2)), midnight)

    def test_incomplete_price_blocks_generation(self):
        for value in (None, 0, float('nan'), float('inf')):
            self.data['prices']['large']['usd'] = value
            with self.subTest(value=value), self.assertRaises(AnalysisUnavailable):
                analysis_context(self.data, self.now)

    def test_section_schema_rejects_empty_incomplete_and_oversized_content(self):
        self.assertEqual(validate_sections(SECTIONS), SECTIONS)
        for sections in ({}, {'overview': 'short'}, dict(SECTIONS, watch='x' * 601), dict(SECTIONS, unknown='extra')):
            with self.subTest(sections=sections), self.assertRaises(AnalysisUnavailable):
                validate_sections(sections)

    @patch('requests.post')
    def test_gemini_uses_key_header_schema_and_validates_finished_result(self, post):
        post.return_value = Mock(status_code=200)
        post.return_value.json.return_value = {'candidates': [{'finishReason': 'STOP',
            'content': {'parts': [{'text': json.dumps(SECTIONS)}]}}]}
        self.assertEqual(generate_daily_analysis({'date': '2026-09-08'}, 'test-key'), SECTIONS)
        self.assertNotIn('test-key', post.call_args.args[0])
        self.assertEqual(post.call_args.kwargs['headers']['x-goog-api-key'], 'test-key')
        self.assertEqual(post.call_args.kwargs['json']['generationConfig']['responseMimeType'], 'application/json')

    @patch('requests.post')
    def test_upstream_errors_are_sanitized_and_not_retried_in_a_loop(self, post):
        for status, code in ((403, 'invalid_key'), (404, 'model_unavailable'), (429, 'rate_limited'), (503, 'provider_error')):
            post.reset_mock()
            post.return_value = Mock(status_code=status, text='sensitive upstream body')
            with self.assertRaises(AnalysisUnavailable) as caught:
                generate_daily_analysis({}, 'test-key')
            self.assertEqual(str(caught.exception), code)
            self.assertEqual(post.call_count, 1)

    @patch('requests.post')
    def test_truncated_and_blocked_outputs_are_not_saved(self, post):
        post.return_value = Mock(status_code=200)
        for candidate in ({'finishReason': 'MAX_TOKENS'}, {'finishReason': 'SAFETY'}, {'finishReason': 'STOP', 'content': {'parts': [{'text': 'invalid JSON'}]}}):
            post.return_value.json.return_value = {'candidates': [candidate]}
            with self.assertRaises(AnalysisUnavailable):
                generate_daily_analysis({}, 'test-key')

    @patch('requests.get')
    def test_live_catalog_skips_unavailable_models_and_non_text_models(self, get):
        get.return_value = Mock(status_code=200)
        get.return_value.json.return_value = {'models': [
            {'name': 'models/gemini-2.5-flash', 'supportedGenerationMethods': ['embedContent']},
            {'name': 'models/gemini-3.8-flash', 'supportedGenerationMethods': ['generateContent']} ]}
        self.assertEqual(resolve_model('test-key'), 'gemini-3.8-flash')
        self.assertNotIn('test-key', get.call_args.args[0])


class AnalysisServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import importlib
        st = types.ModuleType('streamlit')
        st.cache_data = lambda **kw: lambda func: func
        st.secrets = {'gemini': {'api_key': 'test-key'}, 'supabase': {'secret_key': 'sb_secret_test', 'url': 'https://example.supabase.co'}}
        access = types.ModuleType('access_control')
        access.is_supabase_backend_secret_key = lambda key: key == 'sb_secret_test'
        db = types.ModuleType('database_supabase')
        db.get_client = Mock()
        with patch.dict(sys.modules, {'streamlit': st, 'access_control': access, 'database_supabase': db}):
            cls.service = importlib.import_module('analysis_service')

    def setUp(self):
        self.available = patch.object(self.service, 'available_model', return_value='gemini-2.5-flash')
        self.available.start()
        self.addCleanup(self.available.stop)

    def test_existing_today_memo_never_calls_generation_or_claim(self):
        today = self.service.datetime.now(self.service.JST).date().isoformat()
        status = Mock()
        with patch.object(self.service, 'analysis_records', return_value=[{'date': today}]), \
             patch.object(self.service, '_backend_rpc') as rpc, \
             patch.object(self.service, 'generate_daily_analysis') as generate:
            result = self.service.daily_analysis({}, on_status=status)
        self.assertEqual(result['status'], 'ready')
        rpc.assert_not_called()
        generate.assert_not_called()
        status.assert_not_called()

    def test_another_worker_holds_lease_so_no_gemini_call(self):
        with patch.object(self.service, 'analysis_records', return_value=[]), \
             patch.object(self.service, 'analysis_context', return_value={}), \
             patch.object(self.service, '_backend_rpc', return_value={'claimed': False, 'status': 'processing'}), \
             patch.object(self.service, 'generate_daily_analysis') as generate:
            result = self.service.daily_analysis({})
        self.assertEqual(result['status'], 'processing')
        generate.assert_not_called()

    def test_failed_generation_keeps_old_memo_and_records_sanitized_failure(self):
        old = [{'date': '2026-06-01', 'comment': '旧メモ'}]
        with patch.object(self.service, 'analysis_records', return_value=old), \
             patch.object(self.service, 'analysis_context', return_value={}), \
             patch.object(self.service, '_backend_rpc', side_effect=[{'claimed': True, 'token': 'lease'}, {'saved': False, 'retry_at': 'later'}]) as rpc, \
             patch.object(self.service, 'generate_daily_analysis', side_effect=AnalysisUnavailable('rate_limited')):
            result = self.service.daily_analysis({})
        self.assertEqual(result['records'], old)
        self.assertEqual(result['error'], 'rate_limited')
        self.assertEqual(rpc.call_args.args[1]['p_error'], 'rate_limited')
        self.assertIsNone(rpc.call_args.args[1]['p_sections'])

    def test_success_saves_with_lease_and_rereads_persisted_memo(self):
        stored = [{'date': '2026-09-08', 'sections': SECTIONS}]
        status = Mock()
        with patch.object(self.service, 'analysis_records', side_effect=[[], stored]), \
             patch.object(self.service, 'analysis_context', return_value={'date': '2026-09-08'}), \
             patch.object(self.service, '_backend_rpc', side_effect=[{'claimed': True, 'token': 'lease'}, {'saved': True}]) as rpc, \
             patch.object(self.service, 'generate_daily_analysis', return_value=SECTIONS):
            result = self.service.daily_analysis({}, on_status=status)
        self.assertEqual(result['records'], stored)
        self.assertEqual(rpc.call_args.args[1]['p_token'], 'lease')
        self.assertEqual(rpc.call_args.args[1]['p_sections'], SECTIONS)
        self.assertEqual([c.args[0] for c in status.call_args_list], ['本日の分析メモを作成中…', '分析メモを保存中…'])


if __name__ == '__main__':
    unittest.main()
