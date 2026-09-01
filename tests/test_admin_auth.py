import sys
import types
import unittest
from unittest.mock import Mock, patch


def _identity_cache(func=None, **_kwargs):
    if func is None:
        return lambda wrapped: wrapped
    return func


_identity_cache.clear = Mock()

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

import admin_auth


AUTH_CONFIG = {
    "supabase": {
        "url": "https://example.supabase.co",
        "key": "sb_publishable_test",
    }
}


def _response(status_code, payload):
    response = Mock(status_code=status_code)
    response.json.return_value = payload
    return response


class AdminAuthTests(unittest.TestCase):
    def setUp(self):
        self.session_state = {}

    @patch("admin_auth.st.secrets", AUTH_CONFIG)
    @patch("admin_auth.requests.get")
    @patch("admin_auth.requests.post")
    def test_login_requires_allow_list_membership(self, post, get):
        post.return_value = _response(
            200,
            {
                "access_token": "access-one",
                "refresh_token": "refresh-one",
                "expires_in": 3600,
                "user": {"id": "user-one", "email": "owner@example.com"},
            },
        )
        get.return_value = _response(200, [{"user_id": "user-one"}])

        with patch.object(admin_auth.st, "session_state", self.session_state):
            ok, _ = admin_auth.sign_in_admin("owner@example.com", "long-password")

        self.assertTrue(ok)
        self.assertTrue(self.session_state[admin_auth.AUTH_SESSION_KEY]["is_admin"])
        self.assertEqual(
            get.call_args.kwargs["headers"]["Authorization"], "Bearer access-one"
        )

    @patch("admin_auth._revoke_remote_session")
    @patch("admin_auth.st.secrets", AUTH_CONFIG)
    @patch("admin_auth.requests.get")
    @patch("admin_auth.requests.post")
    def test_non_admin_session_is_rejected_and_revoked(self, post, get, revoke):
        post.return_value = _response(
            200,
            {
                "access_token": "access-two",
                "refresh_token": "refresh-two",
                "expires_in": 3600,
                "user": {"id": "user-two", "email": "reader@example.com"},
            },
        )
        get.return_value = _response(200, [])

        with patch.object(admin_auth.st, "session_state", self.session_state):
            ok, message = admin_auth.sign_in_admin("reader@example.com", "long-password")

        self.assertFalse(ok)
        self.assertIn("管理権限", message)
        self.assertNotIn(admin_auth.AUTH_SESSION_KEY, self.session_state)
        revoke.assert_called_once_with("access-two")

    @patch("admin_auth.time.time", return_value=1_000)
    @patch("admin_auth.st.secrets", AUTH_CONFIG)
    @patch("admin_auth.requests.get")
    @patch("admin_auth.requests.post")
    def test_expiring_session_is_refreshed(self, post, get, _time):
        self.session_state[admin_auth.AUTH_SESSION_KEY] = {
            "access_token": "old-access",
            "refresh_token": "old-refresh",
            "expires_at": 1_010,
            "user_id": "user-one",
            "is_admin": True,
        }
        post.return_value = _response(
            200,
            {
                "access_token": "new-access",
                "refresh_token": "new-refresh",
                "expires_in": 3600,
                "user": {"id": "user-one", "email": "owner@example.com"},
            },
        )
        get.return_value = _response(200, [{"user_id": "user-one"}])

        with patch.object(admin_auth.st, "session_state", self.session_state):
            authenticated = admin_auth.is_admin_authenticated()

        self.assertTrue(authenticated)
        self.assertEqual(
            self.session_state[admin_auth.AUTH_SESSION_KEY]["access_token"],
            "new-access",
        )
        self.assertEqual(post.call_args.kwargs["params"], {"grant_type": "refresh_token"})


if __name__ == "__main__":
    unittest.main()
