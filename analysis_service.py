"""Generate once per JST day, using server secrets and a database lease."""
from datetime import datetime

import requests
import streamlit as st

from access_control import is_supabase_backend_secret_key
from analysis_logic import analysis_context
from database_supabase import get_client
from gemini_client import DEFAULT_MODEL, AnalysisUnavailable, generate_daily_analysis, resolve_model
from portfolio_logic import JST


@st.cache_data(ttl=3600, show_spinner=False)
def available_model(api_key, preferred):
    return resolve_model(api_key, preferred)


def analysis_records():
    try:
        client = get_client()
        return client.table("public_ai_comments").select("date,comment,created_at,sections,model,prices_updated_at").order("date", desc=True).limit(8).execute().data or []
    except Exception:
        raise AnalysisUnavailable("storage_error") from None


def _backend_rpc(name, payload):
    settings = st.secrets.get("supabase", {})
    key = str(settings.get("secret_key", ""))
    if not is_supabase_backend_secret_key(key):
        raise AnalysisUnavailable("backend_unconfigured")
    headers = {"apikey": key, "Content-Type": "application/json"}
    if key.count(".") == 2:
        headers["Authorization"] = f"Bearer {key}"
    try:
        response = requests.post(f"{str(settings['url']).rstrip('/')}/rest/v1/rpc/{name}",
                                 headers=headers, json=payload, timeout=(5, 15))
        if response.status_code != 200:
            raise AnalysisUnavailable("storage_error")
        return response.json()
    except (requests.exceptions.RequestException, ValueError, KeyError):
        raise AnalysisUnavailable("storage_error") from None


def daily_analysis(data):
    """Public viewers can trigger a bounded server job, never submit its input."""
    records, context, lease = [], None, None
    try:
        records = analysis_records()
        today = datetime.now(JST).date().isoformat()
        if records and records[0]["date"] == today:
            return {"records": records, "status": "ready"}
        context = analysis_context(data)
        config = st.secrets.get("gemini", {})
        key = str(config.get("api_key", "")).strip()
        if not key:
            raise AnalysisUnavailable("missing_key")
        model = str(config.get("model") or DEFAULT_MODEL).strip()
        if model.startswith("gemini-2.0-"):
            model = DEFAULT_MODEL
        model = available_model(key, model)
        lease = _backend_rpc("claim_daily_analysis", {"p_model": model})
        if not lease.get("claimed"):
            return {"records": analysis_records(), "status": lease.get("status", "processing"),
                    "error": lease.get("error_code"), "retry_at": lease.get("retry_at"), "context": context}
        sections = generate_daily_analysis(context, key, model)
        result = _backend_rpc("finish_daily_analysis", {"p_token": lease["token"], "p_sections": sections,
                              "p_context": context, "p_error": None})
        if not result.get("saved"):
            raise AnalysisUnavailable("date_changed")
        return {"records": analysis_records(), "status": "ready", "context": context}
    except AnalysisUnavailable as exc:
        retry_at = None
        if lease and lease.get("claimed"):
            try:
                result = _backend_rpc("finish_daily_analysis", {"p_token": lease["token"],
                                      "p_sections": None, "p_context": None, "p_error": exc.code})
                retry_at = result.get("retry_at")
            except AnalysisUnavailable:
                pass
        return {"records": records, "status": "failed", "error": exc.code,
                "retry_at": retry_at, "context": context}
