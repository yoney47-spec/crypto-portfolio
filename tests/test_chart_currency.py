import unittest

from components.chart_format import format_chart_currency


class ChartCurrencyTests(unittest.TestCase):
    def test_jpy_uses_yen_symbol(self):
        self.assertEqual(format_chart_currency(694_215, "¥"), "¥694,215")

    def test_usd_uses_dollar_symbol(self):
        self.assertEqual(format_chart_currency(4_283.38, "$"), "$4,283")


if __name__ == "__main__":
    unittest.main()
