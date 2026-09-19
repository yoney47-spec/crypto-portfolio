"""Browser reload bridge, separate from optional visual enhancements."""
from pathlib import Path
import time
import streamlit as st
from admin_auth import (
    AUTH_BROWSER_KEY, AUTH_SESSION_KEY, _browser_command,
    is_admin_authenticated, restore_admin_session, sign_out_admin,
)

_renderer = None


def sync_admin_session():
    global _renderer
    authenticated = is_admin_authenticated()
    if AUTH_BROWSER_KEY not in st.session_state:
        _browser_command('read')
    if _renderer is None:
        from streamlit.components.v2 import component
        _renderer = component('cryptofolio_admin_session',
            js=Path(__file__).with_suffix('.js').read_text())
    command = dict(st.session_state[AUTH_BROWSER_KEY])
    if authenticated:
        deadline = st.session_state[AUTH_SESSION_KEY]['login_expires_at']
        command['remaining_ms'] = max(0, (deadline - time.time()) * 1000)
    with st.container(key='admin-session-runtime'):
        result = _renderer(key='cryptofolio-admin-session', data=command,
                           on_event_change=lambda: None, height=0)
    event = result.event
    if not isinstance(event, dict) or event.get('id') != command['id']:
        return
    kind = event.get('kind')
    if command['action'] == 'read' and kind == 'loaded':
        restore_admin_session(event.get('handle'))
        st.rerun()
    elif command['action'] == 'write' and kind == 'expired':
        sign_out_admin()
        st.rerun()
    elif kind == 'storage':
        st.session_state['admin_session_storage_unavailable'] = not event.get('ok')
