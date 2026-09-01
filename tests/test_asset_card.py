import unittest

from components.asset_card import build_admin_asset_card


class AdminAssetCardTests(unittest.TestCase):
    def test_missing_change_stays_compact_and_balanced(self):
        html = build_admin_asset_card(
            name="Tokyo Games Token",
            symbol="TGT",
            icon_url="https://example.com/tgt.png",
            price_text="$0.00007751",
            change_value=None,
        )

        self.assertNotIn("\n", html)
        self.assertIn("24時間データなし", html)
        self.assertEqual(html.count("<div"), html.count("</div>"))

    def test_database_text_is_html_escaped(self):
        html = build_admin_asset_card(
            name="Asset <script>",
            symbol="A&B",
            icon_url='https://example.com/x.png?label="bad"',
            price_text="$1.00",
            change_value=-1.25,
        )

        self.assertNotIn("<script>", html)
        self.assertIn("Asset &lt;script&gt;", html)
        self.assertIn("A&amp;B", html)
        self.assertIn("negative", html)


if __name__ == "__main__":
    unittest.main()
