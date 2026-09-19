from datetime import datetime, timezone
import unittest
from unittest.mock import Mock

from dashboard_refresh import refresh_dashboard


class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.state = {}
        self.now = 1000
        self.fetch = Mock(return_value=dict(rows=[{'symbol':'BTC'}], total=123,
            updated_at=datetime.fromtimestamp(1000, timezone.utc), stale=False))

    def read(self, currency='JPY', view_id='first'):
        return refresh_dashboard(self.state, currency, view_id, self.fetch, clock=lambda:self.now)

    def test_minute_ticks_do_not_make_extra_network_reads(self):
        first = self.read()
        for self.now in range(1060, 1601, 60):
            self.assertIs(self.read(), first)
        self.fetch.assert_called_once_with('JPY')
        self.now = 1660
        self.read()
        self.assertEqual(self.fetch.call_count, 2)

    def test_initial_cached_price_refreshes_after_its_actual_expiry(self):
        self.fetch.return_value['updated_at'] = datetime.fromtimestamp(500, timezone.utc)
        self.assertEqual(self.read()['next_check'], 1101)
        self.now = 1120
        self.read()
        self.assertEqual(self.fetch.call_count, 2)

    def test_full_page_entry_reads_again_and_currencies_are_isolated(self):
        self.read()
        self.read(view_id='navigation')
        self.assertEqual(self.fetch.call_count, 2)
        self.fetch.return_value = dict(total=1, updated_at=None)
        self.read('USD')
        self.assertEqual(self.state['JPY']['data']['total'], 123)
        self.assertEqual(self.state['USD']['data']['total'], 1)

    def test_failure_preserves_previous_values_without_retry_storm(self):
        first = self.read()
        self.fetch.return_value = {'error':'offline'}
        self.now = 1660
        failed = self.read()
        self.assertTrue(failed['failed'])
        self.assertEqual(failed['data'], first['data'])
        for self.now in range(1720, 2260, 60):
            self.read()
        self.assertEqual(self.fetch.call_count, 2)

    def test_initial_failure_is_not_retried_each_minute(self):
        self.fetch.return_value = {'error':'offline'}
        self.assertEqual(self.read()['data']['error'], 'offline')
        self.now = 1060
        self.read()
        self.fetch.assert_called_once()

    def test_valid_empty_portfolio_replaces_old_values(self):
        self.read()
        self.fetch.return_value = {'rows':[], 'total':None}
        self.now = 1660
        self.assertEqual(self.read()['data']['rows'], [])

    def test_stale_prices_wait_ten_minutes_before_retry(self):
        self.fetch.return_value.update(stale=True,updated_at=datetime.fromtimestamp(100, timezone.utc))
        self.assertEqual(self.read()['next_check'], 1600)


if __name__ == '__main__':
    unittest.main()
