"""Access policy helpers for the staged public read-only rollout."""

import streamlit as st


# Phase 1 is intentionally fail-closed. Admin access will be introduced in the
# next phase; until then, no browser session is allowed to mutate portfolio data.
PUBLIC_READ_ONLY = True


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
