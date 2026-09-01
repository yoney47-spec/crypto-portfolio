import unittest
from datetime import datetime
from unittest.mock import Mock, patch

import database_supabase


class _Query:
    def __init__(self):
        self.payload = None

    def insert(self, payload):
        self.payload = payload
        return self

    def execute(self):
        return Mock(data=[self.payload])


class _Client:
    def __init__(self):
        self.query = _Query()

    def table(self, _name):
        return self.query


class TransactionAdminTests(unittest.TestCase):
    @patch("database_supabase.is_admin_authenticated", return_value=False)
    @patch("database_supabase.get_admin_client")
    def test_anonymous_transaction_write_is_rejected(self, get_client, _auth):
        saved = database_supabase.add_transaction(
            datetime(2026, 1, 1), "Buy", 1, 1.0, 10.0, 10.0
        )

        self.assertFalse(saved)
        get_client.assert_not_called()

    @patch("database_supabase.st.cache_data.clear")
    @patch("database_supabase.is_admin_authenticated", return_value=True)
    def test_admin_transaction_includes_fee_and_source(self, _auth, _clear):
        client = _Client()
        with patch("database_supabase.get_admin_client", return_value=client):
            saved = database_supabase.add_transaction(
                datetime(2026, 1, 1),
                "Buy",
                7,
                2.5,
                100.0,
                250.0,
                "initial purchase",
                skip_duplicate_check=True,
                fee_amount=1.2,
                fee_currency="usd",
                source="Exchange",
            )

        self.assertTrue(saved)
        self.assertEqual(client.query.payload["fee_amount"], 1.2)
        self.assertEqual(client.query.payload["fee_currency"], "USD")
        self.assertEqual(client.query.payload["source"], "Exchange")


if __name__ == "__main__":
    unittest.main()
