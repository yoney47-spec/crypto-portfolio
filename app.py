"""Shared Streamlit entrypoint; widget state survives navigation between every page."""
from pathlib import Path
import streamlit as st
from admin_auth import is_admin_authenticated

st.set_page_config(page_title="CryptoFolio", page_icon="◒", layout="wide", initial_sidebar_state="auto")
st.markdown(f"<style>{Path(__file__).with_name('styles').joinpath('main.css').read_text()}</style>", unsafe_allow_html=True)

pages = [
    st.Page("pages/0_dashboard.py", title="ダッシュボード", default=True),
    st.Page("pages/1_assets.py", title="保有資産", url_path="assets"),
    st.Page("pages/2_transactions.py", title="取引", url_path="transactions"),
    st.Page("pages/3_settings.py", title="設定", url_path="settings"),
    st.Page("pages/4_goals.py", title="目標", url_path="goals"),
]
page = st.navigation(pages, position="hidden")
admin = is_admin_authenticated()
from components.shell import render_shell
render_shell(admin)
page.run()
