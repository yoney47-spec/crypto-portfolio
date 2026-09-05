
import streamlit as st
import requests
import math
from postgrest import SyncPostgrestClient
from datetime import datetime, date, timezone, timedelta
import pandas as pd
from typing import Optional, List, Dict, Any, Tuple
from access_control import (
    is_public_read_only,
    is_snapshot_admin_unlocked,
    is_supabase_backend_secret_key,
)
from admin_auth import (
    get_admin_access_token,
    has_current_admin_authorization,
    is_admin_authenticated,
)
from market_data import (
    CoinGeckoError,
    CoinGeckoRateLimited,
    SNAPSHOT_STALE_MAX_SECONDS,
    get_current_prices,
)

# Japan Standard Time (UTC+9)
JST = timezone(timedelta(hours=9))

# --- Constants copied to avoid circular imports if needed, but imported is better ---
from constants import COST_FREE_TYPES, COST_BASED_TYPES, TRANSACTION_TYPES

class CustomSupabaseClient:
    def __init__(self, url: str, key: str, access_token: str = ""):
        self.url = url
        self.key = key
        self.headers = {
            "apikey": key,
            "Authorization": f"Bearer {access_token or key}",
            "Content-Type": "application/json"
        }
        self.rest_url = f"{url}/rest/v1"
        self.postgrest = SyncPostgrestClient(self.rest_url, headers=self.headers)
        
    def table(self, name: str):
        return self.postgrest.from_(name)

def init_supabase() -> Optional[CustomSupabaseClient]:
    """Initialize Supabase client using Streamlit secrets"""
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return CustomSupabaseClient(url, key)
    except Exception as e:
        st.error("データ接続を確認できませんでした。時間をおいて再読み込みしてください。")
        return None

# Global client check (can be used inside functions)
@st.cache_resource
def get_client():
    return init_supabase()


def get_admin_client() -> Optional[CustomSupabaseClient]:
    """Create a per-session PostgREST client carrying the administrator JWT."""
    access_token = get_admin_access_token()
    if not access_token:
        return None

    try:
        url = str(st.secrets["supabase"]["url"])
        key = str(st.secrets["supabase"]["key"])
        return CustomSupabaseClient(url, key, access_token=access_token)
    except Exception:
        return None


PUBLIC_HOLDINGS_VIEW = "public_portfolio_holdings"
PUBLIC_STATS_VIEW = "public_portfolio_stats"
PUBLIC_HISTORY_VIEW = "public_portfolio_history"
PUBLIC_PRICE_CACHE_VIEW = "public_price_cache"
PUBLIC_AI_COMMENTS_VIEW = "public_ai_comments"


@st.cache_data(ttl=60)
def _get_public_holdings_rows() -> List[Dict[str, Any]]:
    """Fetch the curated public holdings view without touching private tables."""
    client = get_client()
    if not client:
        return []

    try:
        result = client.table(PUBLIC_HOLDINGS_VIEW).select(
            "asset_id,name,symbol,api_id,icon_url,holdings,avg_cost,total_cost"
        ).order("symbol").execute()
        return result.data or []
    except Exception as exc:
        print(f"Public holdings load error: {exc}")
        return []


@st.cache_data(ttl=60)
def _get_public_stats() -> Dict[str, Any]:
    """Fetch aggregate counts and yearly cash-flow values safe for publication."""
    client = get_client()
    if not client:
        return {}

    try:
        result = client.table(PUBLIC_STATS_VIEW).select(
            "asset_count,transaction_count,total_investment_this_year,total_sales_this_year"
        ).limit(1).execute()
        return result.data[0] if result.data else {}
    except Exception as exc:
        print(f"Public stats load error: {exc}")
        return {}

# --- Assets ---

def get_all_assets() -> List[Tuple]:
    """
    Get all assets.
    Returns list of tuples: (id, name, symbol, api_id, icon_url, location, created_at)
    """
    if not is_admin_authenticated():
        return [
            (
                item["asset_id"],
                item["name"],
                item["symbol"],
                item["api_id"],
                item.get("icon_url", ""),
                "",
                None,
            )
            for item in _get_public_holdings_rows()
        ]

    client = get_admin_client()
    if not client: return []
    
    try:
        res = client.table("assets").select("*").order("created_at", desc=True).execute()
        # Convert to list of tuples to match SQLite output expected by app
        assets = []
        for item in res.data:
            assets.append((
                item['id'],
                item['name'],
                item['symbol'],
                item['api_id'],
                item.get('icon_url', ''),
                item.get('location', ''),
                item['created_at']
            ))
        return assets
    except Exception as e:
        st.error(f"Error fetching assets: {e}")
        return []

def get_assets_list() -> List[Tuple]:
    """Get list of (id, name, symbol) for dropdowns"""
    if not is_admin_authenticated():
        return [
            (item["asset_id"], item["name"], item["symbol"])
            for item in _get_public_holdings_rows()
        ]

    client = get_admin_client()
    if not client: return []
    
    try:
        res = client.table("assets").select("id, name, symbol").order("symbol").execute()
        return [(item['id'], item['name'], item['symbol']) for item in res.data]
    except Exception as e:
        st.error(f"Error fetching assets list: {e}")
        return []

def add_asset(name: str, symbol: str, api_id: str, icon_url: str = "", location: str = "") -> bool:
    if not is_admin_authenticated():
        return False

    client = get_admin_client()
    if not client: return False
    
    try:
        data = {
            "name": name,
            "symbol": symbol.upper(),
            "api_id": api_id,
            "icon_url": icon_url,
            "location": location
        }
        client.table("assets").insert(data).execute()
        return True
    except Exception as e:
        # Check for unique constraint violation (symbol)
        print(f"Error adding asset: {e}")
        return False

def update_asset(asset_id, name, symbol, api_id, icon_url, location) -> bool:
    if not is_admin_authenticated():
        return False

    client = get_admin_client()
    if not client: return False
    
    try:
        data = {
            "name": name,
            "symbol": symbol.upper(),
            "api_id": api_id,
            "icon_url": icon_url,
            "location": location
        }
        client.table("assets").update(data).eq("id", asset_id).execute()
        return True
    except Exception as e:
        print(f"Error updating asset: {e}")
        return False

def delete_asset(asset_id) -> Tuple[bool, str]:
    if not is_admin_authenticated():
        return False, "公開モードでは変更できません"

    client = get_admin_client()
    if not client: return False, "Client init failed"
    
    try:
        # Check for transactions
        res = client.table("transactions").select("id", count="exact").eq("asset_id", asset_id).execute()
        count = res.count
        
        if count and count > 0:
            return False, f"この資産には{count}件の取引記録があります。先に取引を削除してください。"
            
        client.table("assets").delete().eq("id", asset_id).execute()
        return True, "削除しました"
    except Exception as e:
        return False, f"削除エラー: {e}"

# --- Transactions ---

def _validated_input_metadata(metadata):
    if metadata is None:
        return {}
    from portfolio_logic import number
    fields = ("input_currency", "input_price", "input_total", "exchange_rate",
              "exchange_rate_source", "exchange_rate_date")
    data = {key: metadata.get(key) for key in fields}
    if data["input_currency"] not in ("JPY", "USD"):
        raise ValueError("Invalid input currency")
    for field in ("input_price", "input_total"):
        if number(data[field]) is None or number(data[field]) < 0:
            raise ValueError("Invalid original amount")
    if data["exchange_rate"] is not None and (number(data["exchange_rate"]) is None or number(data["exchange_rate"]) <= 0):
        raise ValueError("Invalid exchange rate")
    if data["input_currency"] == "JPY" and not all(data[k] for k in ("exchange_rate", "exchange_rate_source", "exchange_rate_date")):
        raise ValueError("JPY conversion metadata required")
    return data

def get_all_transactions(filter_type="すべて") -> List[Tuple]:
    """
    Get all transactions with joined asset info.
    Returns: list of (id, date, type, symbol, name, quantity, price_per_unit, total_amount, notes, asset_id)
    """
    if not is_admin_authenticated():
        return []

    client = get_admin_client()
    if not client: return []
    
    try:
        # Supabase doesn't support easy JOINs returning a flat structure perfectly like SQL selects without defining views.
        # We will fetch transactions and assets separately or use nested select.
        # Using nested select: select(*, assets(symbol, name))
        
        query = client.table("transactions").select("*, assets(symbol, name)").order("date", desc=True)
        
        if filter_type == "コストあり (Buy/Sell)":
            query = query.in_("type", COST_BASED_TYPES)
        elif filter_type == "コストなし (報酬等)":
            query = query.in_("type", COST_FREE_TYPES)
            
        res = query.execute()
        
        transactions = []
        for t in res.data:
            # Flatten structure
            asset = t.get('assets') or {}
            transactions.append((
                t['id'],
                t['date'], # ISO string
                t['type'],
                asset.get('symbol', 'UNKNOWN'),
                asset.get('name', 'Unknown'),
                t['quantity'],
                t['price_per_unit'],
                t['total_amount'],
                t['notes'],
                t['asset_id']
            ))
        return transactions
    except Exception as e:
        st.error(f"Error fetching transactions: {e}")
        return []


def get_transaction_records(filter_type: str = "すべて") -> List[Dict[str, Any]]:
    """Return administrator-only transaction rows as dictionaries for the new UI."""
    if not is_admin_authenticated():
        return []

    client = get_admin_client()
    if not client:
        return []

    try:
        query = client.table("transactions").select(
            "id,date,type,asset_id,quantity,price_per_unit,total_amount,notes,"
            "fee_amount,fee_currency,source,created_at,updated_at,"
            "input_currency,input_price,input_total,exchange_rate,exchange_rate_source,exchange_rate_date,assets(symbol,name)"
        ).order("date", desc=True)

        if filter_type == "コストあり":
            query = query.in_("type", COST_BASED_TYPES)
        elif filter_type == "報酬・その他":
            query = query.in_("type", COST_FREE_TYPES)

        rows = []
        for item in query.execute().data or []:
            asset = item.pop("assets", None) or {}
            item["symbol"] = asset.get("symbol", "UNKNOWN")
            item["asset_name"] = asset.get("name", "Unknown")
            rows.append(item)
        return rows
    except Exception as exc:
        print(f"Transaction records load error: {exc}")
        return []

def add_transaction(
    date_obj,
    trans_type,
    asset_id,
    quantity,
    price_per_unit,
    total_amount,
    notes="",
    skip_duplicate_check=False,
    fee_amount=0,
    fee_currency="USD",
    source="",
    input_metadata=None,
) -> bool:
    if not is_admin_authenticated():
        return False

    client = get_admin_client()
    if not client: return False
    
    # Check duplicate
    if not skip_duplicate_check:
        is_dup, _ = check_duplicate_transactions(date_obj, asset_id, quantity)
        if is_dup:
             st.warning("類似した取引が存在します。内容を確認してから保存してください。")
             return False

    try:
        # Convert date to ISO string with JST timezone
        # Treat the input datetime as JST (user's local time)
        if isinstance(date_obj, datetime):
            # Add JST timezone info if naive datetime
            if date_obj.tzinfo is None:
                date_obj = date_obj.replace(tzinfo=JST)
            date_str = date_obj.isoformat()
        elif isinstance(date_obj, date):
            # Convert date to datetime at midnight JST
            dt = datetime.combine(date_obj, datetime.min.time())
            dt = dt.replace(tzinfo=JST)
            date_str = dt.isoformat()
        else:
            date_str = str(date_obj)

        data = {
            "date": date_str,
            "type": trans_type,
            "asset_id": asset_id,
            "quantity": quantity,
            "price_per_unit": price_per_unit,
            "total_amount": total_amount,
            "notes": notes,
            "fee_amount": fee_amount,
            "fee_currency": str(fee_currency or "USD").upper(),
            "source": str(source or "").strip() or None,
        }
        data.update(_validated_input_metadata(input_metadata))
        client.table("transactions").insert(data).execute()
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error("保存できませんでした。入力内容を保持しています。接続とログイン状態を確認してください。")
        return False

def update_transaction(
    transaction_id,
    date_obj,
    trans_type,
    asset_id,
    quantity,
    price_per_unit,
    total_amount,
    notes="",
    fee_amount=0,
    fee_currency="USD",
    source="",
    input_metadata=None,
) -> bool:
    if not is_admin_authenticated():
        return False

    client = get_admin_client()
    if not client: return False
    
    try:
        # Convert date to ISO string with JST timezone
        if isinstance(date_obj, datetime):
            if date_obj.tzinfo is None:
                date_obj = date_obj.replace(tzinfo=JST)
            date_str = date_obj.isoformat()
        elif isinstance(date_obj, date):
            dt = datetime.combine(date_obj, datetime.min.time())
            dt = dt.replace(tzinfo=JST)
            date_str = dt.isoformat()
        else:
            date_str = str(date_obj)
            
        data = {
            "date": date_str,
            "type": trans_type,
            "asset_id": asset_id,
            "quantity": quantity,
            "price_per_unit": price_per_unit,
            "total_amount": total_amount,
            "notes": notes,
            "fee_amount": fee_amount,
            "fee_currency": str(fee_currency or "USD").upper(),
            "source": str(source or "").strip() or None,
        }
        data.update(_validated_input_metadata(input_metadata))
        client.table("transactions").update(data).eq("id", transaction_id).execute()
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error("更新できませんでした。入力内容を保持しています。接続とログイン状態を確認してください。")
        return False

def delete_transaction(transaction_id) -> bool:
    if not is_admin_authenticated():
        return False

    client = get_admin_client()
    if not client: return False
    try:
        client.table("transactions").delete().eq("id", transaction_id).execute()
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"削除エラー: {e}")
        return False

def check_duplicate_transactions(date_obj, asset_id, quantity, tolerance_minutes=5):
    """
    Simple check if same asset and quantity exists around the time.
    """
    if not is_admin_authenticated():
        return False, []

    client = get_admin_client()
    if not client: return False, []
    
    try:
        # We can't easily do date range math in simple Postgrest filter query without custom function.
        # So we fetch all transactions for that asset with that quantity, and filter in Python.
        # This is safe because user won't have infinite transactions for exactly same qty of same asset.
        
        res = client.table("transactions")\
            .select("*, assets(symbol)")\
            .eq("asset_id", asset_id)\
            .eq("quantity", quantity)\
            .execute()
            
        similar = []
        target_ts = pd.to_datetime(date_obj).timestamp()
        
        for t in res.data:
            existing_ts = pd.to_datetime(t['date']).timestamp()
            diff = abs(target_ts - existing_ts)
            if diff <= tolerance_minutes * 60:
                # Add to similar
                asset = t.get('assets') or {}
                # Format similar to resemble SQLite result tuple: (id, date, type, symbol, quantity)
                similar.append((
                    t['id'], t['date'], t['type'], asset.get('symbol', ''), t['quantity']
                ))
        
        return len(similar) > 0, similar
        
    except Exception as e:
        print(f"Error check duplicate: {e}")
        return False, []

# --- Aggregation / Dashboard Logic ---

def get_portfolio_data() -> Tuple[List[Tuple], int, int]:
    """
    Calculate current portfolio holdings.
    Returns: (portfolio_list, asset_count, transaction_count)
    portfolio_list item: (id, symbol, name, api_id, icon_url, location, holdings)
    """
    if is_public_read_only():
        rows = _get_public_holdings_rows()
        stats = _get_public_stats()
        portfolio = [
            (
                item["asset_id"],
                item["symbol"],
                item["name"],
                item["api_id"],
                item.get("icon_url", ""),
                "",
                float(item.get("holdings") or 0),
            )
            for item in rows
            if float(item.get("holdings") or 0) > 0.00000001
        ]
        portfolio.sort(key=lambda item: item[6], reverse=True)
        return (
            portfolio,
            int(stats.get("asset_count") or len(rows)),
            int(stats.get("transaction_count") or 0),
        )

    client = get_client()
    if not client: return [], 0, 0
    
    assets = get_all_assets()
    
    # Try fetching from balances table first (Performance Optimization)
    balances_map = {}
    used_balances_table = False
    
    try:
        # Attempt to fetch from balances table
        # If table doesn't exist, this will raise an exception and we fall back to calculation
        res = client.table("balances").select("*").execute()
        for item in res.data:
            balances_map[item['asset_id']] = float(item['amount'])
        used_balances_table = True
    except Exception:
        # Fallback to transaction calculation
        used_balances_table = False
        
    transaction_count = 0
    
    if not used_balances_table:
        all_trans = get_all_transactions("すべて")
        transaction_count = len(all_trans)
        
        # Calculate holdings in Python
        for t in all_trans:
            # (id, date, type, symbol, name, quantity, price, total, notes, asset_id)
            t_type = t[2]
            qty = t[5]
            aid = t[9]
            
            current_qty = balances_map.get(aid, 0.0)
            
            if t_type in ['Buy', 'Airdrop', 'Staking Reward', 'Interest', 'Gift']:
                current_qty += qty
            elif t_type in ['Sell', 'Transfer']:
                current_qty -= qty
                
            balances_map[aid] = current_qty
    else:
        # If using balances table, efficiently get transaction count
        try:
            res = client.table("transactions").select("id", count="exact", head=True).execute()
            transaction_count = res.count if res.count is not None else 0
        except:
            transaction_count = 0
        
    # Build result
    portfolio = []
    for a in assets:
        aid = a[0]
        qty = balances_map.get(aid, 0.0)
        if qty > 0.00000001: # Filter zero balance
            # (id, symbol, name, api_id, icon_url, location, holdings)
            # asset tuple: (0:id, 1:name, 2:symbol, 3:api_id, 4:icon, 5:loc, 6:created)
            portfolio.append((
                a[0], # id
                a[2], # symbol
                a[1], # name
                a[3], # api_id
                a[4], # icon_url
                a[5], # location
                qty   # holdings
            ))
            
    # Sort by holdings descending (roughly proxies value importance if not checking price here)
    portfolio.sort(key=lambda x: x[6], reverse=True)
    
    return portfolio, len(assets), transaction_count

def calculate_cost_basis() -> Dict:
    """
    Calculate avg cost basis.
    Returns: { asset_id: {avg_cost, holdings, total_cost} }
    """
    if is_public_read_only():
        return {
            item["asset_id"]: {
                "avg_cost": float(item.get("avg_cost") or 0),
                "holdings": float(item.get("holdings") or 0),
                "total_cost": float(item.get("total_cost") or 0),
            }
            for item in _get_public_holdings_rows()
        }

    # Simply reuse transaction data logic
    # We need all transactions again? Yes. 
    # Optimally we cache transactions in st.session_state if heavy.
    
    all_trans = get_all_transactions("すべて")
    # item: (id, date, type, symbol, name, quantity, price, total, notes, asset_id)
    
    data = {} # asset_id -> {total_cost, total_bought, total_sold}
    
    for t in all_trans:
        t_type = t[2]
        qty = t[5]
        total = t[7]
        aid = t[9]
        
        if aid not in data:
            data[aid] = {'cost': 0.0, 'bought': 0.0, 'sold': 0.0}
            
        if t_type == 'Buy':
            data[aid]['cost'] += total
            data[aid]['bought'] += qty
        elif t_type == 'Sell':
            data[aid]['sold'] += qty
            
    cost_basis = {}
    for aid, vals in data.items():
        bought = vals['bought']
        cost = vals['cost']
        sold = vals['sold']
        
        if bought > 0:
            avg_cost = cost / bought
            holdings = bought - sold
            # Note: This is simple average cost. 
            # If current holdings < 0 (impossible theoretically but maybe data error), we clamp?
            # Or just calc as is.
            
            cost_basis[aid] = {
                'avg_cost': avg_cost,
                'holdings': holdings,
                'total_cost': avg_cost * holdings 
            }
            
    return cost_basis

def get_statistics(start_date=None, end_date=None):
    """
    Get aggregated stats (Total Inv, Total Sales, etc.) with date filter.
    """
    all_trans = get_all_transactions("すべて")
    
    # Filter by date in Python
    filtered = []
    for t in all_trans:
        # t[1] is iso formatted date string or datetime
        d_val = pd.to_datetime(t[1])
        # Remove timezone info for comparison (Supabase returns tz-aware timestamps)
        if d_val.tzinfo is not None:
            d_val = d_val.tz_localize(None)
        
        if start_date:
            start_dt = pd.to_datetime(start_date)
            if start_dt.tzinfo is not None:
                start_dt = start_dt.tz_localize(None)
            if d_val < start_dt:
                continue
        if end_date:
            end_dt = pd.to_datetime(end_date)
            if end_dt.tzinfo is not None:
                end_dt = end_dt.tz_localize(None)
            if d_val > end_dt:
                continue
        filtered.append(t)
        
    total_investment = 0.0
    total_sales = 0.0
    # Holdings calculation similar to get_portfolio_data but for filtered transactions
    holdings_map = {} 
    
    for t in filtered:
        t_type = t[2]
        qty = t[5]
        total = t[7]
        aid = t[9]
        
        if t_type == 'Buy':
            total_investment += total
        elif t_type == 'Sell':
            total_sales += total
            
        current_qty = holdings_map.get(aid, 0.0)
        if t_type in ['Buy', 'Airdrop', 'Staking Reward', 'Interest', 'Gift']:
            current_qty += qty
        elif t_type in ['Sell', 'Transfer']:
            current_qty -= qty
        holdings_map[aid] = current_qty

    # Build holdings list for stats
    # Expected: list of (symbol, name, api_id, icon_url, holdings) desc
    # Need to map asset details.
    assets = get_all_assets()
    asset_dict = {a[0]: a for a in assets} # id -> asset tuple
    
    holdings_list = []
    for aid, msg_qty in holdings_map.items():
        if msg_qty > 0 and aid in asset_dict:
            a = asset_dict[aid]
            # (symbol, name, api_id, icon_url, quantity)
            # asset tuple: (0:id, 1:name, 2:symbol, 3:api_id, 4:icon, ...)
            holdings_list.append((
                a[2], a[1], a[3], a[4], msg_qty
            ))
            
    holdings_list.sort(key=lambda x: x[4], reverse=True)
    
    return {
        "total_investment": total_investment,
        "total_sales": total_sales,
        "transaction_count": len(filtered),
        "holdings": holdings_list
    }

def get_current_year_investment_sales():
    """Specific helper for app.py dashboard logic (current year P/L)."""
    if is_public_read_only():
        stats = _get_public_stats()
        return (
            float(stats.get("total_investment_this_year") or 0),
            float(stats.get("total_sales_this_year") or 0),
        )

    current_year = datetime.now().year
    
    # Fetch all transactions is easier than custom SQL
    all_trans = get_all_transactions("すべて")
    
    inv = 0.0
    sales = 0.0
    
    for t in all_trans:
        d = pd.to_datetime(t[1])
        if d.year == current_year:
            t_type = t[2]
            total = t[7]
            if t_type == 'Buy':
                inv += total
            elif t_type == 'Sell':
                sales += total
                
    return inv, sales

# --- Snapshots ---

def save_portfolio_snapshot(total_value_jpy: float) -> bool:
    if is_public_read_only():
        return False

    client = get_client()
    if not client: return False
    
    try:
        # Use JST (Japan Standard Time) for the date instead of system local time
        today = datetime.now(JST).date().isoformat()
        data = {
            "date": today,
            "total_value_jpy": total_value_jpy
        }
        client.table("portfolio_snapshots").upsert(data, on_conflict="date").execute()
        return True
    except Exception as e:
        st.error(f"スナップショット保存エラー: {e}")
        return False


def capture_portfolio_snapshot() -> Dict[str, Any]:
    """
    Calculate and save today's snapshot from the trusted Streamlit backend.

    The browser never supplies a portfolio value. Holdings are loaded from the
    curated public view, current JPY prices come from CoinGecko, and the upsert
    uses a backend-only Supabase secret key after either a current administrator
    session or the fallback UI PIN check is verified.
    """
    if not has_current_admin_authorization() and not is_snapshot_admin_unlocked():
        return {
            "ok": False,
            "message": "管理者としてログインするか、管理コードで本人確認してから保存してください。",
        }

    try:
        supabase_url = str(st.secrets["supabase"]["url"]).rstrip("/")
        secret_key = str(st.secrets["supabase"]["secret_key"])
    except Exception:
        return {
            "ok": False,
            "message": "管理者用の保存設定を確認してください。",
        }

    if not is_supabase_backend_secret_key(secret_key):
        return {
            "ok": False,
            "message": "管理者用の保存設定を確認してください。",
        }

    try:
        holdings_rows = _get_public_holdings_rows()
        active_holdings = []

        for item in holdings_rows:
            try:
                holdings = float(item.get("holdings") or 0)
            except (TypeError, ValueError):
                holdings = 0

            if holdings > 0:
                active_holdings.append(
                    {
                        "symbol": str(item.get("symbol") or "UNKNOWN"),
                        "api_id": str(item.get("api_id") or ""),
                        "holdings": holdings,
                    }
                )

        if not active_holdings:
            return {
                "ok": False,
                "message": "記録できる保有資産がありません。",
            }

        missing_api_ids = [item["symbol"] for item in active_holdings if not item["api_id"]]
        if missing_api_ids:
            return {
                "ok": False,
                "message": f"価格IDが未設定の銘柄があります: {', '.join(missing_api_ids)}",
            }

        api_ids = sorted({item["api_id"] for item in active_holdings})
        try:
            price_result = get_current_prices(
                api_ids,
                fallback_prices=load_price_cache(),
                max_stale_seconds=SNAPSHOT_STALE_MAX_SECONDS,
            )
            prices = price_result.prices
        except CoinGeckoRateLimited:
            return {
                "ok": False,
                "message": "価格更新が混み合っています。1分ほど待って再度お試しください。",
            }
        except CoinGeckoError:
            return {
                "ok": False,
                "message": "現在価格を取得できませんでした。少し時間をおいて再度お試しください。",
            }

        missing_prices = []
        total_value = 0.0
        for item in active_holdings:
            try:
                price_jpy = float(prices.get(item["api_id"], {}).get("jpy"))
            except (AttributeError, TypeError, ValueError):
                price_jpy = 0

            if not math.isfinite(price_jpy) or price_jpy <= 0:
                missing_prices.append(item["symbol"])
                continue

            total_value += item["holdings"] * price_jpy

        if missing_prices:
            return {
                "ok": False,
                "message": f"現在価格を確認できない銘柄があります: {', '.join(missing_prices)}",
            }

        total_value = round(total_value)
        if not math.isfinite(total_value) or total_value <= 0:
            return {
                "ok": False,
                "message": "総資産額を正しく計算できませんでした。",
            }

        today = datetime.now(JST).date().isoformat()
        headers = {
            "apikey": secret_key,
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=representation",
        }

        # Legacy service-role keys are JWTs. Modern sb_secret keys must stay in
        # the apikey header and must not be sent as Bearer tokens.
        if secret_key.count(".") == 2:
            headers["Authorization"] = f"Bearer {secret_key}"

        from portfolio_logic import number
        usd_values = [number(prices.get(item["api_id"], {}).get("usd")) for item in active_holdings]
        usd_total = sum(item["holdings"] * price for item, price in zip(active_holdings, usd_values)) if all(p is not None and p > 0 for p in usd_values) else None
        save_response = requests.post(
            f"{supabase_url}/rest/v1/portfolio_snapshots",
            params={"on_conflict": "date"},
            headers=headers,
            json={
                "date": today,
                "total_value_jpy": total_value,
                "total_value_usd": round(usd_total, 8) if usd_total is not None else None,
                "prices_updated_at": price_result.updated_at.isoformat() if getattr(price_result, "updated_at", None) else None,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            timeout=15,
        )

        if save_response.status_code not in (200, 201):
            return {
                "ok": False,
                "message": "スナップショットを保存できませんでした。",
            }

        return {
            "ok": True,
            "date": today,
            "total_value_jpy": total_value,
            "action": "updated",
        }
    except (requests.RequestException, ValueError, TypeError):
        return {
            "ok": False,
            "message": "スナップショットを保存できませんでした。少し時間をおいて再度お試しください。",
        }

def get_portfolio_history(days: int = 365, currency: str = "JPY") -> List[Tuple]:
    """Returns list of (date_str, value)"""
    client = get_client()
    if not client: return []
    
    try:
        source = PUBLIC_HISTORY_VIEW if is_public_read_only() else "portfolio_snapshots"
        field = "total_value_usd" if currency == "USD" else "total_value_jpy"
        query = client.table(source).select(f"date,{field}").order("date", desc=True)
        # ALL期間 (days >= 9999) の場合はlimitを適用しない
        if days < 9999:
            query = query.gte("date", (datetime.now(JST).date() - timedelta(days=days - 1)).isoformat())
        res = query.execute()
        
        data = []
        if res.data:
            for item in res.data:
                if item.get(field) is not None:
                    data.append((item['date'], item[field]))
            
            # Reverse to get Oldest first for charting
            data.reverse()
            
        return data
    except Exception as e:
        print(f"Error fetching history: {e}")
        return []

def get_latest_snapshot() -> Optional[Dict]:
    """
    Get latest snapshot info.
    Returns: {date: str, total_value_jpy: float}
    """
    client = get_client()
    if not client: return None
    
    try:
        source = PUBLIC_HISTORY_VIEW if is_public_read_only() else "portfolio_snapshots"
        res = client.table(source)\
            .select("date, total_value_jpy")\
            .order("date", desc=True)\
            .limit(1)\
            .execute()
            
        if res.data:
            item = res.data[0]
            return {
                'date': item['date'],
                'total_value_jpy': item['total_value_jpy']
            }
        return None
    except Exception as e:
        print(f"Latest snapshot error: {e}")
        return None

def get_snapshot_count() -> int:
    """Get total number of snapshots"""
    client = get_client()
    if not client: return 0
    
    try:
        source = PUBLIC_HISTORY_VIEW if is_public_read_only() else "portfolio_snapshots"
        res = client.table(source).select("date", count="exact", head=True).execute()
        return res.count if res.count is not None else 0
    except Exception as e:
        print(f"Snapshot count error: {e}")
        return 0

# --- Price Cache (for API rate limit fallback) ---

def save_price_cache(prices_data: Dict) -> bool:
    """
    価格データをSupabaseにキャッシュとして保存
    prices_data: {api_id: {usd, jpy, usd_24h_change, jpy_24h_change}}
    """
    if is_public_read_only():
        return False

    client = get_client()
    if not client or not prices_data:
        return False
    
    try:
        now = datetime.now(JST).isoformat()
        
        # 各通貨の価格をupsert
        for api_id, data in prices_data.items():
            if data.get("usd") is not None:
                cache_data = {
                    "api_id": api_id,
                    "price_usd": data.get("usd"),
                    "price_jpy": data.get("jpy"),
                    "usd_24h_change": data.get("usd_24h_change"),
                    "jpy_24h_change": data.get("jpy_24h_change"),
                    "updated_at": now
                }
                client.table("price_cache").upsert(cache_data, on_conflict="api_id").execute()
        
        return True
    except Exception as e:
        print(f"Price cache save error: {e}")
        return False

def load_price_cache() -> Dict:
    """
    Supabaseから価格キャッシュを読み込み
    Returns: {api_id: {usd, jpy, usd_24h_change, jpy_24h_change, updated_at}}
    """
    client = get_client()
    if not client:
        return {}
    
    try:
        source = PUBLIC_PRICE_CACHE_VIEW if is_public_read_only() else "price_cache"
        res = client.table(source).select(
            "api_id,price_usd,price_jpy,usd_24h_change,updated_at,jpy_24h_change"
        ).execute()
        
        result = {}
        for item in res.data:
            result[item["api_id"]] = {
                "usd": item.get("price_usd"),
                "jpy": item.get("price_jpy"),
                "usd_24h_change": item.get("usd_24h_change"),
                "jpy_24h_change": item.get("jpy_24h_change"),
                "updated_at": item.get("updated_at"),
            }
        return result
    except Exception as e:
        print(f"Price cache load error: {e}")
        return {}


def is_cache_valid(cache_data: Dict, max_age_minutes: int = 5) -> bool:
    """
    キャッシュが有効期限内かチェック
    
    Args:
        cache_data: キャッシュデータ（updated_atを含む）
        max_age_minutes: キャッシュの有効期限（分）
    
    Returns:
        True if cache is still valid
    """
    if not cache_data:
        return False
    
    # 任意のエントリのupdated_atをチェック
    for api_id, data in cache_data.items():
        updated_at = data.get("updated_at")
        if updated_at:
            try:
                # ISO形式のタイムスタンプをパース
                if isinstance(updated_at, str):
                    cache_time = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                else:
                    cache_time = updated_at
                
                # タイムゾーン情報がない場合はJSTとして扱う
                if cache_time.tzinfo is None:
                    cache_time = cache_time.replace(tzinfo=JST)
                
                now = datetime.now(JST)
                age = (now - cache_time).total_seconds() / 60  # 分単位
                
                return age < max_age_minutes
            except Exception as e:
                print(f"Cache time parse error: {e}")
                return False
    
    return False


def load_price_cache_if_valid(max_age_minutes: int = 5) -> Optional[Dict]:
    """
    有効期限内のキャッシュがあれば読み込む
    
    Args:
        max_age_minutes: キャッシュの有効期限（分）
    
    Returns:
        キャッシュデータ、または期限切れ/存在しない場合はNone
    """
    cache = load_price_cache()
    if is_cache_valid(cache, max_age_minutes):
        return cache
    return None

# --- AI Comments ---

def save_ai_comment(date_str: str, comment: str, portfolio_summary: Dict = None) -> bool:
    """
    AIコメントを保存（同日は上書き）
    
    Args:
        date_str: 日付文字列 (YYYY-MM-DD)
        comment: AIが生成したコメント
        portfolio_summary: ポートフォリオのサマリーデータ（オプション）
    """
    if is_public_read_only():
        return False

    client = get_client()
    if not client:
        return False
    
    try:
        import json
        data = {
            "date": date_str,
            "comment": comment,
            "portfolio_summary": json.dumps(portfolio_summary) if portfolio_summary else None
        }
        client.table("ai_comments").upsert(data, on_conflict="date").execute()
        return True
    except Exception as e:
        print(f"AI comment save error: {e}")
        return False


def get_latest_ai_comment() -> Optional[Dict]:
    """
    最新のAIコメントを取得
    
    Returns:
        {'date': str, 'comment': str, 'portfolio_summary': dict} or None
    """
    client = get_client()
    if not client:
        return None
    
    try:
        source = PUBLIC_AI_COMMENTS_VIEW if is_public_read_only() else "ai_comments"
        fields = "date,comment,created_at" if is_public_read_only() else "date,comment,portfolio_summary,created_at"
        res = client.table(source)\
            .select(fields)\
            .order("date", desc=True)\
            .limit(1)\
            .execute()
        
        if res.data:
            item = res.data[0]
            import json
            summary = None
            if item.get('portfolio_summary'):
                try:
                    summary = json.loads(item['portfolio_summary'])
                except:
                    summary = item['portfolio_summary']
            
            return {
                'date': item['date'],
                'comment': item['comment'],
                'portfolio_summary': summary,
                'created_at': item.get('created_at')
            }
        return None
    except Exception as e:
        print(f"AI comment load error: {e}")
        return None


def get_today_ai_comment() -> Optional[Dict]:
    """
    今日のAIコメントを取得（存在しない場合はNone）
    """
    today = datetime.now(JST).date().isoformat()
    
    client = get_client()
    if not client:
        return None
    
    try:
        source = PUBLIC_AI_COMMENTS_VIEW if is_public_read_only() else "ai_comments"
        fields = "date,comment" if is_public_read_only() else "date,comment,portfolio_summary"
        res = client.table(source)\
            .select(fields)\
            .eq("date", today)\
            .execute()
        
        if res.data:
            item = res.data[0]
            import json
            summary = None
            if item.get('portfolio_summary'):
                try:
                    summary = json.loads(item['portfolio_summary'])
                except:
                    summary = item['portfolio_summary']
            
            return {
                'date': item['date'],
                'comment': item['comment'],
                'portfolio_summary': summary
            }
        return None
    except Exception as e:
        print(f"Today AI comment load error: {e}")
        return None
