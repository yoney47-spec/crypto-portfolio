"""Supabase Auth session helpers for the private portfolio administration UI."""

from __future__ import annotations

import time
import math
import secrets
from typing import Any, Dict, Optional, Tuple

import requests
import streamlit as st
from admin_session_store import AdminSessionStore


AUTH_SESSION_KEY = "portfolio_admin_auth"
AUTH_REFRESH_SKEW_SECONDS = 90
AUTH_REQUEST_TIMEOUT_SECONDS = 15
AUTH_HANDLE_KEY = "portfolio_admin_handle"
AUTH_BROWSER_KEY = "portfolio_admin_browser_command"


@st.cache_resource
def _session_store():
    return AdminSessionStore()


def _browser_command(action, handle=""):
    st.session_state[AUTH_BROWSER_KEY] = {
        "id": secrets.token_hex(16), "action": action, "handle": handle,
    }


def _save_new_login(session):
    old_handle = st.session_state.get(AUTH_HANDLE_KEY)
    if old_handle:
        _session_store().revoke(old_handle)
    handle, saved = _session_store().issue(session)
    st.session_state[AUTH_HANDLE_KEY] = handle
    st.session_state[AUTH_SESSION_KEY] = saved
    _browser_command("write", handle)


def _public_supabase_config() -> Tuple[str, str]:
    """Return the project URL and publishable/anon key without exposing them."""
    try:
        url = str(st.secrets["supabase"]["url"]).strip().rstrip("/")
        key = str(st.secrets["supabase"]["key"]).strip()
    except Exception as exc:  # Streamlit raises several mapping-related errors.
        raise RuntimeError("Supabaseの公開接続設定を確認してください。") from exc

    if not url.startswith("https://") or not key:
        raise RuntimeError("Supabaseの公開接続設定を確認してください。")
    return url, key


def _auth_headers(key: str, access_token: str = "") -> Dict[str, str]:
    headers = {
        "apikey": key,
        "Content-Type": "application/json",
    }
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    return headers


def _session_from_payload(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    access_token = str(payload.get("access_token") or "")
    refresh_token = str(payload.get("refresh_token") or "")
    user = payload.get("user") or {}
    user_id = str(user.get("id") or "")
    if not access_token or not refresh_token or not user_id:
        return None

    try:
        expires_at = float(payload.get("expires_at") or 0)
    except (TypeError, ValueError):
        expires_at = 0
    if not math.isfinite(expires_at) or expires_at <= 0:
        try:
            expires_at = time.time() + float(payload.get("expires_in") or 3600)
        except (TypeError, ValueError):
            expires_at = time.time() + 3600

    if not math.isfinite(expires_at):
        return None
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": expires_at,
        "user_id": user_id,
        "email": str(user.get("email") or ""),
        "is_admin": False,
    }


def _has_admin_membership(session: Dict[str, Any]) -> bool:
    """Ask PostgREST for the caller's own allow-list row; RLS is authoritative."""
    try:
        url, key = _public_supabase_config()
        response = requests.get(
            f"{url}/rest/v1/portfolio_admins",
            params={
                "select": "user_id",
                "user_id": f"eq.{session['user_id']}",
                "limit": "1",
            },
            headers=_auth_headers(key, str(session["access_token"])),
            timeout=AUTH_REQUEST_TIMEOUT_SECONDS,
        )
        if not 200 <= response.status_code < 300:
            return False
        rows = response.json()
        return bool(isinstance(rows, list) and rows)
    except (requests.RequestException, RuntimeError, TypeError, ValueError, KeyError):
        return False


def _revoke_remote_session(access_token: str) -> None:
    """Best-effort remote logout. Local tokens are cleared regardless of outcome."""
    if not access_token:
        return
    try:
        url, key = _public_supabase_config()
        requests.post(
            f"{url}/auth/v1/logout",
            params={"scope": "local"},
            headers=_auth_headers(key, access_token),
            timeout=AUTH_REQUEST_TIMEOUT_SECONDS,
        )
    except (requests.RequestException, RuntimeError):
        pass


def sign_in_admin(email: str, password: str) -> Tuple[bool, str]:
    """Create an Auth session and accept it only for an allow-listed administrator."""
    email = str(email or "").strip()
    password = str(password or "")
    if not email or not password:
        return False, "メールアドレスとパスワードを入力してください。"

    try:
        url, key = _public_supabase_config()
        response = requests.post(
            f"{url}/auth/v1/token",
            params={"grant_type": "password"},
            headers=_auth_headers(key),
            json={"email": email, "password": password},
            timeout=AUTH_REQUEST_TIMEOUT_SECONDS,
        )
        if not 200 <= response.status_code < 300:
            return False, "ログイン情報を確認してください。"

        session = _session_from_payload(response.json())
        if not session or not _has_admin_membership(session):
            if session:
                _revoke_remote_session(str(session.get("access_token") or ""))
            return False, "このアカウントには管理権限がありません。"

        session["is_admin"] = True
        _save_new_login(session)
        return True, "管理者としてログインしました。"
    except (requests.RequestException, RuntimeError, TypeError, ValueError):
        return False, "現在ログインできません。時間をおいて再度お試しください。"


def _refresh_admin_session(session: Dict[str, Any]) -> bool:
    try:
        url, key = _public_supabase_config()
        response = requests.post(
            f"{url}/auth/v1/token",
            params={"grant_type": "refresh_token"},
            headers=_auth_headers(key),
            json={"refresh_token": str(session.get("refresh_token") or "")},
            timeout=AUTH_REQUEST_TIMEOUT_SECONDS,
        )
        if not 200 <= response.status_code < 300:
            return False

        refreshed = _session_from_payload(response.json())
        if not refreshed or not _has_admin_membership(refreshed):
            return False
        refreshed["is_admin"] = True
        saved = _session_store().update(st.session_state.get(AUTH_HANDLE_KEY), refreshed)
        if not saved:
            return False
        st.session_state[AUTH_SESSION_KEY] = saved
        return True
    except (requests.RequestException, RuntimeError, TypeError, ValueError):
        return False


def is_admin_authenticated() -> bool:
    """Check the server-side ten-minute grant on every private read/write."""
    session = st.session_state.get(AUTH_SESSION_KEY)
    if not isinstance(session, dict) or not session.get("is_admin"):
        return False

    saved = _session_store().get(st.session_state.get(AUTH_HANDLE_KEY))
    if not saved or saved['user_id'] != session.get('user_id'):
        sign_out_admin()
        return False
    session = saved
    st.session_state[AUTH_SESSION_KEY] = session
    try:
        expires_at = float(session.get("expires_at") or 0)
    except (TypeError, ValueError):
        expires_at = 0

    if expires_at - time.time() > AUTH_REFRESH_SKEW_SECONDS:
        return True

    if _refresh_admin_session(session):
        return True

    sign_out_admin()
    return False


def restore_admin_session(handle) -> bool:
    """Restore only a live server grant, then recheck the JWT and RLS allow-list."""
    session = _session_store().get(handle)
    if not session:
        _browser_command("clear")
        return False
    st.session_state[AUTH_HANDLE_KEY] = handle
    st.session_state[AUTH_SESSION_KEY] = session
    if not is_admin_authenticated() or not _has_admin_membership(st.session_state[AUTH_SESSION_KEY]):
        sign_out_admin()
        return False
    # Validation can span the expiry boundary. Never restore past that boundary.
    if not is_admin_authenticated():
        return False
    _browser_command("write", handle)
    return True


def admin_login_expires_at() -> float:
    if not is_admin_authenticated():
        return 0
    return st.session_state[AUTH_SESSION_KEY]['login_expires_at']


def get_admin_access_token() -> str:
    if not is_admin_authenticated():
        return ""
    session = st.session_state.get(AUTH_SESSION_KEY) or {}
    return str(session.get("access_token") or "")


def has_current_admin_authorization() -> bool:
    """Recheck allow-list membership before a backend-privileged operation."""
    if not is_admin_authenticated():
        return False

    session = st.session_state.get(AUTH_SESSION_KEY)
    if isinstance(session, dict) and _has_admin_membership(session) and is_admin_authenticated():
        return True

    sign_out_admin()
    return False


def sign_out_admin() -> None:
    session = st.session_state.pop(AUTH_SESSION_KEY, None)
    handle = st.session_state.pop(AUTH_HANDLE_KEY, None)
    _session_store().revoke(handle)
    _browser_command("clear")
    for key in list(st.session_state):
        if key.startswith(("trade_", "goal_", "private_")):
            del st.session_state[key]
    if isinstance(session, dict):
        _revoke_remote_session(str(session.get("access_token") or ""))
