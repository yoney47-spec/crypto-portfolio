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
    requests_stub.RequestException = RuntimeError
    requests_stub.exceptions = types.SimpleNamespace(RequestException=RuntimeError)
    sys.modules["requests"] = requests_stub

import market_data


def _response(status_code, payload=None, headers=None):
    response = Mock()
    response.status_code = status_code
    response.headers = headers or {}
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


class SharedMarketDataTests(unittest.TestCase):
    def setUp(self):
        self.state = market_data._MarketState()

    @patch("market_data._demo_api_key", return_value="")
    @patch("market_data.time.time", return_value=1_000)
    @patch("market_data.requests.get")
    def test_current_prices_are_shared_across_id_order(self, get, _time, _key):
        get.return_value = _response(
            200,
            {
                "bitcoin": {
                    "usd": 60_000,
                    "jpy": 9_000_000,
                    "usd_24h_change": 1.2,
                    "jpy_24h_change": 1.1,
                },
                "kaspa": {
                    "usd": 0.1,
                    "jpy": 15,
                    "usd_24h_change": -0.5,
                    "jpy_24h_change": -0.6,
                },
            },
        )

        with patch("market_data._shared_market_state", return_value=self.state):
            first = market_data.get_current_prices(["kaspa", "bitcoin"])
            second = market_data.get_current_prices(["bitcoin", "kaspa"])

        self.assertEqual(first.source, "live")
        self.assertEqual(second.source, "memory")
        self.assertFalse(second.stale)
        self.assertEqual(second.prices["bitcoin"]["jpy"], 9_000_000)
        get.assert_called_once()
        self.assertEqual(
            get.call_args.kwargs["params"]["vs_currencies"],
            "usd,jpy",
        )

    @patch("market_data._demo_api_key", return_value="")
    @patch("market_data.time.time", return_value=1_100)
    @patch("market_data.requests.get")
    def test_429_uses_stale_prices_and_opens_circuit_breaker(self, get, _time, _key):
        self.state.prices["bitcoin"] = {
            "data": {
                "usd": 59_000.0,
                "jpy": 8_900_000.0,
                "usd_24h_change": 1.0,
                "jpy_24h_change": 0.9,
            },
            "updated_at": 1_000.0,
            "source": "live",
        }
        get.return_value = _response(429)

        with patch("market_data._shared_market_state", return_value=self.state):
            result = market_data.get_current_prices(
                ["bitcoin"],
                force_refresh=True,
            )
            with self.assertRaises(market_data.CoinGeckoRateLimited):
                market_data.coingecko_get_json("/ping", params={})

        self.assertTrue(result.stale)
        self.assertEqual(result.prices["bitcoin"]["usd"], 59_000.0)
        self.assertEqual(self.state.blocked_until, 1_160.0)
        get.assert_called_once()

    @patch("market_data._demo_api_key", return_value="")
    @patch("market_data.time.time", return_value=2_000)
    @patch("market_data.requests.get")
    def test_snapshot_rejects_cache_older_than_fifteen_minutes(self, get, _time, _key):
        self.state.prices["bitcoin"] = {
            "data": {
                "usd": 59_000.0,
                "jpy": 8_900_000.0,
                "usd_24h_change": 1.0,
                "jpy_24h_change": 0.9,
            },
            "updated_at": 1_000.0,
            "source": "live",
        }
        get.return_value = _response(429)

        with patch("market_data._shared_market_state", return_value=self.state):
            with self.assertRaises(market_data.CoinGeckoRateLimited):
                market_data.get_current_prices(
                    ["bitcoin"],
                    force_refresh=True,
                    max_stale_seconds=market_data.SNAPSHOT_STALE_MAX_SECONDS,
                )

        get.assert_called_once()


if __name__ == "__main__":
    unittest.main()
