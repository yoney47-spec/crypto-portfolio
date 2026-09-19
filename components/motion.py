"""Optional local motion; native widgets and readable HTML remain the fallback."""
from contextlib import contextmanager
from pathlib import Path
import streamlit as st

from components.ui_markup import loading_markup, success_markup

_renderer = None

def install_motion():
    # JS-only component is a documented v2 use case. Never send portfolio data,
    # credentials, or authentication state to it. It only enhances rendered DOM.
    global _renderer
    if _renderer is None:
        from streamlit.components.v2 import component
        _renderer = component('cryptofolio_motion', js=Path(__file__).with_name('motion.js').read_text(), isolate_styles=False)
    with st.container(key='motion-runtime'):
        _renderer(key='cryptofolio-motion', height=0)


@contextmanager
def loading(label, kind='cards'):
    placeholder = st.empty()
    def update(message):
        placeholder.markdown(loading_markup(message, kind), unsafe_allow_html=True)
    update(label)
    try:
        yield update
    finally:
        placeholder.empty()


def saved_notice(message):
    st.markdown(success_markup(message), unsafe_allow_html=True)
