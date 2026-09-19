import sys
import types
import unittest
from unittest.mock import MagicMock, Mock, patch


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
from admin_session_store import AdminSessionStore


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
        self.store = AdminSessionStore(clock=lambda: admin_auth.time.time())
        store_patch = patch('admin_auth._session_store', return_value=self.store)
        store_patch.start()
        self.addCleanup(store_patch.stop)

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
        original = {
            "access_token": "old-access",
            "refresh_token": "old-refresh",
            "expires_at": 1_010,
            "user_id": "user-one",
            "is_admin": True,
        }
        handle, saved = self.store.issue(original)
        self.session_state[admin_auth.AUTH_SESSION_KEY] = saved
        self.session_state[admin_auth.AUTH_HANDLE_KEY] = handle
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
        self.assertEqual(self.session_state[admin_auth.AUTH_SESSION_KEY]['login_expires_at'], 1600)

    def grant(self):
        session = dict(access_token='access', refresh_token='refresh', expires_at=9999,
                       user_id='owner', is_admin=True)
        return self.store.issue(session)

    @patch('admin_auth.time.time', return_value=1000)
    @patch('admin_auth._has_admin_membership', return_value=True)
    def test_reload_restores_live_session_without_extending_deadline(self, membership, clock):
        handle, _ = self.grant()
        with patch.object(admin_auth.st, 'session_state', self.session_state):
            for now in [1100, 1200, 1599]:
                clock.return_value = now
                self.session_state.clear()  # A new Streamlit websocket after reload.
                self.assertTrue(admin_auth.restore_admin_session(handle))
                self.assertEqual(admin_auth.admin_login_expires_at(), 1600)
                command = self.session_state[admin_auth.AUTH_BROWSER_KEY]
                self.assertEqual(command['handle'], handle)
                self.assertNotIn('access_token', command)
                self.assertNotIn('refresh_token', command)
        self.assertEqual(membership.call_count, 3)

    @patch('admin_auth.time.time', return_value=1000)
    @patch('admin_auth._has_admin_membership')
    def test_expired_or_forged_resume_handle_is_rejected_before_network(self, membership, clock):
        handle, _ = self.grant()
        clock.return_value = 1600
        with patch.object(admin_auth.st, 'session_state', self.session_state):
            for candidate in [handle, 'A'*43, None, {}, '<script>']:
                self.assertFalse(admin_auth.restore_admin_session(candidate))
                self.assertFalse(admin_auth.is_admin_authenticated())
        membership.assert_not_called()

    @patch('admin_auth.time.time', return_value=1000)
    @patch('admin_auth._revoke_remote_session')
    @patch('admin_auth._has_admin_membership', return_value=True)
    def test_deadline_is_enforced_for_existing_tab_and_access_token(self, membership, revoke, clock):
        handle, _ = self.grant()
        with patch.object(admin_auth.st, 'session_state', self.session_state):
            self.assertTrue(admin_auth.restore_admin_session(handle))
            self.session_state['private_rows'] = ['private data']
            clock.return_value = 1600
            self.assertEqual(admin_auth.get_admin_access_token(), '')
            self.assertNotIn('private_rows', self.session_state)
            self.assertIsNone(self.store.get(handle))
            self.assertEqual(self.session_state[admin_auth.AUTH_BROWSER_KEY]['action'], 'clear')

    @patch('admin_auth.time.time', return_value=1000)
    @patch('admin_auth._revoke_remote_session')
    @patch('admin_auth._has_admin_membership', return_value=True)
    def test_logout_revokes_restoration_and_other_streamlit_sessions(self, membership, revoke, clock):
        handle, _ = self.grant()
        with patch.object(admin_auth.st, 'session_state', self.session_state):
            self.assertTrue(admin_auth.restore_admin_session(handle))
            other_tab = dict(self.session_state)
            admin_auth.sign_out_admin()
            self.assertFalse(admin_auth.restore_admin_session(handle))
        with patch.object(admin_auth.st, 'session_state', other_tab):
            self.assertFalse(admin_auth.is_admin_authenticated())

    @patch('admin_auth.time.time', return_value=1000)
    @patch('admin_auth._revoke_remote_session')
    @patch('admin_auth._has_admin_membership', return_value=False)
    def test_removed_admin_cannot_restore(self, membership, revoke, clock):
        handle, _ = self.grant()
        with patch.object(admin_auth.st, 'session_state', self.session_state):
            self.assertFalse(admin_auth.restore_admin_session(handle))
            self.assertNotIn(admin_auth.AUTH_SESSION_KEY, self.session_state)
        self.assertIsNone(self.store.get(handle))

    @patch('admin_auth.time.time', return_value=1000)
    @patch('admin_auth._revoke_remote_session')
    def test_validation_crossing_deadline_does_not_restore(self, revoke, clock):
        handle, _ = self.grant()
        def slow_membership(_session):
            clock.return_value = 1600
            return True
        with patch.object(admin_auth.st, 'session_state', self.session_state), patch('admin_auth._has_admin_membership', side_effect=slow_membership):
            self.assertFalse(admin_auth.restore_admin_session(handle))
            self.assertFalse(admin_auth.is_admin_authenticated())

    @patch('admin_auth.time.time', return_value=1000)
    def test_session_store_isolated_copies_and_failed_updates_cannot_revive_grants(self, clock):
        handle, session = self.grant()
        second, _ = self.grant()
        session['access_token'] = 'mutated'
        session['login_expires_at'] = 999999
        self.assertEqual(self.store.get(handle)['access_token'], 'access')
        saved = self.store.update(handle, session)
        self.assertEqual(saved['login_expires_at'], 1600)
        self.assertEqual(self.store.get(second)['access_token'], 'access')
        self.store.revoke(handle)
        self.assertIsNone(self.store.update(handle, session))
        clock.return_value = 1600
        self.assertIsNone(self.store.update(second, session))

    @patch('admin_auth.time.time', return_value=1000)
    @patch('admin_auth._has_admin_membership', return_value=True)
    @patch('admin_auth._revoke_remote_session')
    def test_browser_bridge_round_trip_and_late_restore_event_after_logout(self, revoke, membership, clock):
        from components import admin_session as bridge
        handle, _ = self.grant()
        renderer = Mock(return_value=types.SimpleNamespace(event=None))
        class Rerun(Exception): pass
        with patch.object(admin_auth.st, 'session_state', self.session_state), \
             patch.object(bridge, '_renderer', renderer), \
             patch.object(bridge.st, 'container', MagicMock(), create=True), \
             patch.object(bridge.st, 'rerun', Mock(side_effect=Rerun), create=True):
            bridge.sync_admin_session()
            read_command = renderer.call_args.kwargs['data']
            self.assertEqual(read_command['action'], 'read')
            event = dict(id=read_command['id'], kind='loaded', handle=handle)
            renderer.return_value.event = event
            with self.assertRaises(Rerun):
                bridge.sync_admin_session()
            renderer.return_value.event = None
            bridge.sync_admin_session()
            write_command = renderer.call_args.kwargs['data']
            self.assertEqual(write_command['action'], 'write')
            self.assertEqual(write_command['remaining_ms'], 600000)
            self.assertEqual(set(write_command), {'id', 'action', 'handle', 'remaining_ms'})
            admin_auth.sign_out_admin()
            renderer.return_value.event = event  # Late initial read must never restore.
            bridge.sync_admin_session()
            self.assertFalse(admin_auth.is_admin_authenticated())
            self.assertEqual(renderer.call_args.kwargs['data']['action'], 'clear')

    @patch("admin_auth.sign_out_admin")
    @patch("admin_auth._has_admin_membership", return_value=False)
    @patch("admin_auth.is_admin_authenticated", return_value=True)
    def test_privileged_operation_rechecks_allow_list(
        self, _authenticated, _membership, sign_out
    ):
        self.session_state[admin_auth.AUTH_SESSION_KEY] = {
            "access_token": "access-one",
            "user_id": "user-one",
            "is_admin": True,
        }

        with patch.object(admin_auth.st, "session_state", self.session_state):
            authorized = admin_auth.has_current_admin_authorization()

        self.assertFalse(authorized)
        sign_out.assert_called_once()


if __name__ == "__main__":
    unittest.main()
