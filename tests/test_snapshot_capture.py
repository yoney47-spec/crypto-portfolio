import sys
import types
import unittest
from unittest.mock import Mock, patch


def _identity_cache(func=None, **_kwargs):
    if func is None:
        return lambda wrapped: wrapped
    return func


try:
    import streamlit  # noqa: F401
except ModuleNotFoundError:
    streamlit_stub = types.ModuleType("streamlit")
    streamlit_stub.cache_data = _identity_cache
    streamlit_stub.cache_resource = _identity_cache
    streamlit_stub.error = Mock()
    streamlit_stub.secrets = {}
    streamlit_stub.session_state = {}
    sys.modules["streamlit"] = streamlit_stub

try:
    import requests  # noqa: F401
except ModuleNotFoundError:
    requests_stub = types.ModuleType("requests")
    requests_stub.get = Mock()
    requests_stub.post = Mock()
    requests_stub.exceptions = types.SimpleNamespace(RequestException=RuntimeError)
    sys.modules["requests"] = requests_stub

try:
    import postgrest  # noqa: F401
except ModuleNotFoundError:
    postgrest_stub = types.ModuleType("postgrest")
    postgrest_stub.SyncPostgrestClient = object
    sys.modules["postgrest"] = postgrest_stub

import database_supabase
import access_control


class CapturePortfolioSnapshotTests(unittest.TestCase):
    def setUp(self):
        database_supabase.st.session_state.clear()
        database_supabase.st.session_state["snapshot_admin_expires_at"] = float("inf")

    @patch("database_supabase.get_current_prices")
    @patch("database_supabase.requests.post")
    @patch("database_supabase.has_current_admin_authorization", return_value=False)
    def test_rejects_capture_without_current_pin_grant(
        self, _is_admin, post, get_prices
    ):
        database_supabase.st.session_state.pop("snapshot_admin_expires_at", None)

        result = database_supabase.capture_portfolio_snapshot()

        self.assertFalse(result["ok"])
        self.assertIn("本人確認", result["message"])
        get_prices.assert_not_called()
        post.assert_not_called()

    @patch("database_supabase.is_snapshot_admin_unlocked", return_value=False)
    @patch("database_supabase.has_current_admin_authorization", return_value=True)
    @patch("database_supabase._get_public_holdings_rows", return_value=[])
    @patch(
        "database_supabase.st.secrets",
        {
            "supabase": {
                "url": "https://example.supabase.co",
                "secret_key": "sb_secret_test",
            }
        },
    )
    def test_admin_session_bypasses_pin(
        self, holdings, _is_admin, _pin_unlocked
    ):
        result = database_supabase.capture_portfolio_snapshot()

        self.assertFalse(result["ok"])
        self.assertIn("保有資産", result["message"])
        self.assertNotIn("本人確認", result["message"])
        holdings.assert_called_once()

    @patch("database_supabase._get_public_holdings_rows")
    @patch("database_supabase.load_price_cache", return_value={})
    @patch("database_supabase.get_current_prices")
    @patch("database_supabase.requests.post")
    @patch(
        "database_supabase.st.secrets",
        {"supabase": {"url": "https://example.supabase.co", "secret_key": "sb_secret_test"}},
    )
    def test_calculates_and_saves_snapshot_with_backend_secret(
        self, post, get_prices, _load_cache, holdings
    ):
        holdings.return_value = [
            {"symbol": "BTC", "api_id": "bitcoin", "holdings": 0.1},
            {"symbol": "KAS", "api_id": "kaspa", "holdings": 1000},
        ]
        get_prices.return_value = types.SimpleNamespace(
            prices={
                "bitcoin": {"jpy": 10_000_000},
                "kaspa": {"jpy": 10},
            }
        )
        post.return_value = Mock(status_code=201)

        result = database_supabase.capture_portfolio_snapshot()

        self.assertTrue(result["ok"])
        self.assertEqual(result["total_value_jpy"], 1_010_000)
        request = post.call_args
        self.assertEqual(request.args[0], "https://example.supabase.co/rest/v1/portfolio_snapshots")
        self.assertEqual(request.kwargs["params"], {"on_conflict": "date"})
        self.assertEqual(request.kwargs["headers"]["apikey"], "sb_secret_test")
        self.assertNotIn("Authorization", request.kwargs["headers"])
        self.assertEqual(request.kwargs["json"]["total_value_jpy"], 1_010_000)

    @patch("database_supabase._get_public_holdings_rows")
    @patch("database_supabase.load_price_cache", return_value={})
    @patch("database_supabase.get_current_prices")
    @patch("database_supabase.requests.post")
    @patch(
        "database_supabase.st.secrets",
        {"supabase": {"url": "https://example.supabase.co", "secret_key": "sb_secret_test"}},
    )
    def test_does_not_save_when_a_price_is_missing(
        self, post, get_prices, _load_cache, holdings
    ):
        holdings.return_value = [
            {"symbol": "BTC", "api_id": "bitcoin", "holdings": 0.1},
            {"symbol": "KAS", "api_id": "kaspa", "holdings": 1000},
        ]
        get_prices.return_value = types.SimpleNamespace(
            prices={"bitcoin": {"jpy": 10_000_000}}
        )

        result = database_supabase.capture_portfolio_snapshot()

        self.assertFalse(result["ok"])
        self.assertIn("KAS", result["message"])
        post.assert_not_called()


class SnapshotAdminPinTests(unittest.TestCase):
    def setUp(self):
        access_control.st.session_state.clear()

    @patch("access_control.time.time", return_value=1_000)
    @patch(
        "access_control.st.secrets",
        {
            "supabase": {"secret_key": "sb_secret_test"},
            "snapshot_admin": {"pin": "strong-code-12"},
        },
    )
    def test_correct_pin_unlocks_session_for_ten_minutes(self, _time):
        verified, _ = access_control.verify_snapshot_admin_pin("strong-code-12")

        self.assertTrue(verified)
        self.assertEqual(
            access_control.st.session_state["snapshot_admin_expires_at"],
            1_000 + access_control.SNAPSHOT_UNLOCK_SECONDS,
        )

    @patch(
        "access_control.st.secrets",
        {"supabase": {"secret_key": "sb_secret_test"}},
    )
    def test_admin_flow_only_requires_backend_secret(self):
        self.assertIsNone(access_control.snapshot_backend_configuration_error())
        self.assertIsNotNone(access_control.snapshot_admin_configuration_error())

    @patch("access_control.time.time", return_value=1_000)
    @patch(
        "access_control.st.secrets",
        {
            "supabase": {"secret_key": "sb_secret_test"},
            "snapshot_admin": {"pin": "strong-code-12"},
        },
    )
    def test_five_wrong_attempts_trigger_temporary_lock(self, _time):
        for _ in range(access_control.SNAPSHOT_MAX_ATTEMPTS):
            verified, message = access_control.verify_snapshot_admin_pin("wrong-code")

        self.assertFalse(verified)
        self.assertIn("60秒", message)
        self.assertEqual(
            access_control.st.session_state["snapshot_admin_locked_until"],
            1_000 + access_control.SNAPSHOT_LOCKOUT_SECONDS,
        )


if __name__ == "__main__":
    unittest.main()
