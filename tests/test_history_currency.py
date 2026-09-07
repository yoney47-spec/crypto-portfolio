from datetime import date
import unittest

from portfolio_logic import composition_entries, history_series


class HistoricalCurrencyTests(unittest.TestCase):
    def setUp(self):
        self.today = date(2026, 9, 8)
        self.legacy = {'date': '2026-09-05', 'total_value_jpy': 150_000,
                       'total_value_usd': None, 'usd_jpy_rate': 150,
                       'usd_jpy_rate_date': '2026-09-04',
                       'usd_jpy_rate_source': 'ECB / Frankfurter'}

    def test_both_currencies_keep_all_dates_and_actual_usd_wins(self):
        actual = dict(self.legacy, date='2026-09-06', total_value_usd=1100)
        records = [actual, self.legacy]
        jpy = history_series(records, 'JPY', 30, self.today)
        usd = history_series(records, 'USD', 30, self.today)
        self.assertEqual([r['date'] for r in jpy], [r['date'] for r in usd])
        self.assertEqual([r['value'] for r in usd], [1000, 1100])
        self.assertEqual([r['value'] for r in jpy], [150_000, 150_000])
        self.assertTrue(usd[0]['estimated'])
        self.assertEqual(usd[0]['fx_date'], '2026-09-04')
        self.assertNotIn('estimated', usd[1])
        self.assertIsNone(self.legacy['total_value_usd'])

    def test_each_record_uses_its_own_historical_rate(self):
        other = dict(self.legacy, date='2026-09-07', usd_jpy_rate=125,
                     usd_jpy_rate_date='2026-09-07')
        usd = history_series([self.legacy, other], 'USD', 30, self.today)
        self.assertEqual([r['value'] for r in usd], [1000, 1200])

    def test_no_guess_without_valid_observation(self):
        for change in ({'usd_jpy_rate': None}, {'usd_jpy_rate': 0}, {'usd_jpy_rate': float('nan')},
                       {'usd_jpy_rate_date': None}, {'usd_jpy_rate_date': '2026-09-06'},
                       {'usd_jpy_rate_date': '2026-08-01'}):
            with self.subTest(change=change):
                self.assertEqual(history_series([dict(self.legacy, **change)], 'USD', 30, self.today), [])

    def test_zero_actual_value_is_not_replaced_with_estimate(self):
        row = dict(self.legacy, total_value_usd=0)
        usd = history_series([row], 'USD', 30, self.today)
        self.assertEqual(usd[0]['value'], 0)
        self.assertNotIn('estimated', usd[0])

    def test_period_filter_is_identical(self):
        for currency in ('JPY', 'USD'):
            self.assertEqual(history_series([self.legacy], currency, 1, self.today), [])

    def test_composition_sorts_unsorted_assets_and_combined_slice(self):
        rows = [{'symbol':str(i), 'weight':w} for i,w in enumerate([9,11,10,15,9,12,15,19])]
        before = list(rows)
        entries = composition_entries(rows)
        self.assertEqual([v for _,v in entries], [28,19,15,15,12,11])
        self.assertEqual(entries[0][0], 'その他')
        self.assertEqual(sum(v for _,v in entries), 100)
        self.assertEqual(rows, before)


if __name__ == '__main__':
    unittest.main()
