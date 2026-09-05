"""Cached public data and optional market lookups. No private records are cached globally."""
from datetime import datetime, timezone
import requests
import streamlit as st

from database_supabase import get_client, load_price_cache
from market_data import get_current_prices, coingecko_get_json, CoinGeckoError
from portfolio_logic import build_portfolio, number, JST


@st.cache_data(ttl=60, show_spinner=False)
def public_data():
    client = get_client()
    if client is None:
        return {"error": "データに接続できません。再読み込みをお試しください。"}
    try:
        holdings = client.table("public_portfolio_holdings").select("*").order("symbol").execute().data or []
        stats = client.table("public_portfolio_stats").select("*").execute().data or [{}]
        history, offset = [], 0
        while True:
            batch = client.table("public_portfolio_history").select("*").order("date").range(offset, offset + 999).execute().data or []
            history.extend(batch)
            if len(batch) < 1000:
                break
            offset += 1000
        return {"holdings": holdings, "stats": stats[0], "history": history}
    except Exception:
        return {"error": "保有資産を取得できませんでした。しばらくして再読み込みしてください。"}


def portfolio(currency):
    raw = public_data()
    if raw.get("error"):
        return raw
    holdings = [(r["asset_id"], r["symbol"], r["name"], r["api_id"], r.get("icon_url"), "", r["holdings"]) for r in raw["holdings"]]
    costs = {r["asset_id"]: r for r in raw["holdings"]}
    ids = sorted({r[3] for r in holdings if r[3]})
    prices, updated, source, stale, price_error = {}, None, "unavailable", False, None
    if ids:
        try:
            result = get_current_prices(ids, fallback_prices=load_price_cache())
            prices, updated, source, stale = result.prices, result.updated_at, result.source, result.stale
        except CoinGeckoError:
            price_error = "価格を更新できませんでした。少し時間をおいて再読み込みしてください。"
    data = build_portfolio(holdings, prices, costs, currency)
    return dict(data, history=raw["history"], stats=raw["stats"], prices=prices,
                updated_at=updated, source=source, stale=stale, price_error=price_error)


@st.cache_data(ttl=3600, show_spinner=False, max_entries=256)
def exchange_rate(day: str):
    """ECB daily reference, with the actual observation date (incl. holidays)."""
    try:
        response = requests.get("https://api.frankfurter.dev/v2/rate/USD/JPY",
                                params={"date": day, "providers": "ECB"}, timeout=10)
        response.raise_for_status()
        data = response.json()
        rate = number(data.get("rate"))
        observed = str(data.get("date", ""))[:10]
        if rate is not None and rate > 0 and observed and observed <= day:
            return {"rate": rate, "date": observed, "source": "ECB / Frankfurter"}
    except (requests.RequestException, ValueError, TypeError, AttributeError):
        pass
    return None


@st.cache_data(ttl=900, show_spinner=False, max_entries=128)
def coin_history(api_id: str, currency: str, days: int):
    try:
        data = coingecko_get_json(f"coins/{api_id}/market_chart", params={"vs_currency": currency.lower(), "days": days}, timeout=10)
        return [{"date": datetime.fromtimestamp(t / 1000, timezone.utc).astimezone(JST).isoformat(), "value": p} for t, p in data.get("prices", []) if number(p) is not None]
    except (CoinGeckoError, ValueError, TypeError):
        return []


@st.cache_data(ttl=3600, show_spinner=False, max_entries=100)
def search_coins(query: str):
    if len(query.strip()) < 2:
        return []
    data = coingecko_get_json("search", params={"query": query.strip()}, timeout=10)
    return [{"api_id": c["id"], "name": c["name"], "symbol": c["symbol"].upper(), "icon_url": c.get("large") or c.get("thumb", "")} for c in data.get("coins", [])[:30]]


@st.cache_data(ttl=3600, show_spinner=False)
def market_overview():
    try:
        return coingecko_get_json("global", params={}, timeout=10).get("data", {})
    except CoinGeckoError:
        return {}
