"""Access policy helpers for the staged public read-only rollout."""

import hmac
import base64
import json
import time

import streamlit as st


# Phase 1 is intentionally fail-closed. The only public-page mutation is the
# snapshot action, and it requires a short-lived PIN grant plus a backend key.
PUBLIC_READ_ONLY = True

SNAPSHOT_UNLOCK_SECONDS = 10 * 60
SNAPSHOT_MAX_ATTEMPTS = 5
SNAPSHOT_LOCKOUT_SECONDS = 60


def is_supabase_backend_secret_key(value: str) -> bool:
    """Accept a modern sb_secret key or a legacy service_role JWT only."""
    key = str(value or "").strip()
    if key.startswith("sb_secret_") and len(key) > len("sb_secret_"):
        return True

    parts = key.split(".")
    if len(parts) != 3:
        return False

    try:
        padded_payload = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded_payload).decode("utf-8"))
        return payload.get("role") == "service_role"
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return False


def snapshot_admin_configuration_error() -> str | None:
    """Return a public-safe setup error, or None when snapshot auth is ready."""
    try:
        admin_pin = str(st.secrets.get("snapshot_admin", {}).get("pin", ""))
        secret_key = str(st.secrets.get("supabase", {}).get("secret_key", ""))
    except Exception:
        return "管理者設定の完了後に利用できます。"

    if len(admin_pin) < 12 or not is_supabase_backend_secret_key(secret_key):
        return "管理者設定の完了後に利用できます。"

    return None


def is_snapshot_admin_unlocked() -> bool:
    """Return whether this Streamlit session has a current PIN grant."""
    expires_at = float(st.session_state.get("snapshot_admin_expires_at", 0) or 0)
    if expires_at > time.time():
        return True

    st.session_state.pop("snapshot_admin_expires_at", None)
    return False


def verify_snapshot_admin_pin(candidate: str) -> tuple[bool, str]:
    """Verify the PIN with constant-time comparison and session-level throttling."""
    configuration_error = snapshot_admin_configuration_error()
    if configuration_error:
        return False, configuration_error

    now = time.time()
    locked_until = float(st.session_state.get("snapshot_admin_locked_until", 0) or 0)
    if locked_until > now:
        remaining = max(1, int(locked_until - now))
        return False, f"入力回数が多いため、{remaining}秒後に再度お試しください。"

    configured_pin = str(st.secrets["snapshot_admin"]["pin"])
    is_match = hmac.compare_digest(
        str(candidate).encode("utf-8"),
        configured_pin.encode("utf-8"),
    )

    if is_match:
        st.session_state["snapshot_admin_expires_at"] = now + SNAPSHOT_UNLOCK_SECONDS
        st.session_state.pop("snapshot_admin_attempts", None)
        st.session_state.pop("snapshot_admin_locked_until", None)
        return True, "本人確認が完了しました。"

    attempts = int(st.session_state.get("snapshot_admin_attempts", 0) or 0) + 1
    if attempts >= SNAPSHOT_MAX_ATTEMPTS:
        st.session_state["snapshot_admin_attempts"] = 0
        st.session_state["snapshot_admin_locked_until"] = now + SNAPSHOT_LOCKOUT_SECONDS
        return False, "入力回数が多いため、60秒後に再度お試しください。"

    st.session_state["snapshot_admin_attempts"] = attempts
    return False, "管理コードが一致しません。"


def is_public_read_only() -> bool:
    """Return whether the current deployment is restricted to public reads."""
    return PUBLIC_READ_ONLY


def stop_on_private_page() -> None:
    """Stop execution of a private page during the public-only phase."""
    if not is_public_read_only():
        return

    st.info("このページは管理者専用です。現在は公開ダッシュボードのみ利用できます。")
    st.page_link("app.py", label="ダッシュボードへ戻る", icon="📊")
    st.stop()
