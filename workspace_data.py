"""Private workspace persistence uses the current administrator JWT on every call."""
from datetime import datetime, timezone
import streamlit as st
from admin_auth import is_admin_authenticated, AUTH_SESSION_KEY
from database_supabase import get_admin_client
from portfolio_logic import number


def _client():
    if not is_admin_authenticated():
        raise PermissionError("管理者としてログインしてください。")
    client = get_admin_client()
    if client is None:
        raise PermissionError("ログイン状態を確認してください。")
    return client


def goals():
    return _client().table("portfolio_goals").select("asset_id,target_quantity,target_weight,updated_at").execute().data or []


def save_goal(asset_id, target_quantity, target_weight):
    client = _client()
    qty, weight = number(target_quantity), number(target_weight)
    if target_quantity is not None and (qty is None or qty <= 0):
        raise ValueError("目標数量は0より大きくしてください。")
    if target_weight is not None and (weight is None or not 0 <= weight <= 100):
        raise ValueError("目標配分は0〜100%で入力してください。")
    if qty is None and weight is None:
        raise ValueError("数量か配分のいずれかを設定してください。")
    others = goals()
    if sum(number(g.get("target_weight")) or 0 for g in others if g["asset_id"] != asset_id) + (weight or 0) > 100.000001:
        raise ValueError("目標配分の合計が100%を超えています。他の目標を調整してください。")
    user_id = st.session_state[AUTH_SESSION_KEY]["user_id"]
    client.table("portfolio_goals").upsert(dict(user_id=user_id, asset_id=asset_id, target_quantity=qty,
         target_weight=weight, updated_at=datetime.now(timezone.utc).isoformat()), on_conflict="user_id,asset_id").execute()


def delete_goal(asset_id):
    _client().table("portfolio_goals").delete().eq("asset_id", asset_id).execute()


def transaction_rows():
    client = _client()
    result, offset = [], 0
    while True:
        batch = client.table("transactions").select("*,assets(symbol,name)").order("date", desc=True).order("id", desc=True).range(offset, offset + 999).execute().data or []
        for row in batch:
            asset = row.pop("assets", None) or {}
            result.append(dict(row, symbol=asset.get("symbol", "—"), asset_name=asset.get("name", "—")))
        if len(batch) < 1000:
            return result
        offset += 1000
