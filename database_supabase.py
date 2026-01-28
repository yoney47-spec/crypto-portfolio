
import streamlit as st
import requests
from postgrest import SyncPostgrestClient
from datetime import datetime, date, timezone, timedelta
import pandas as pd
from typing import Optional, List, Dict, Any, Tuple

# Japan Standard Time (UTC+9)
JST = timezone(timedelta(hours=9))

# --- Constants copied to avoid circular imports if needed, but imported is better ---
from constants import COST_FREE_TYPES, COST_BASED_TYPES, TRANSACTION_TYPES

class CustomSupabaseClient:
    def __init__(self, url: str, key: str):
        self.url = url
        self.key = key
        self.headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
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
        st.error(f"Failed to initialize Supabase: {e}")
        return None

# Global client check (can be used inside functions)
def get_client():
    return init_supabase()

# --- Assets ---

def get_all_assets() -> List[Tuple]:
    """
    Get all assets.
    Returns list of tuples: (id, name, symbol, api_id, icon_url, location, created_at)
    """
    client = get_client()
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
    client = get_client()
    if not client: return []
    
    try:
        res = client.table("assets").select("id, name, symbol").order("symbol").execute()
        return [(item['id'], item['name'], item['symbol']) for item in res.data]
    except Exception as e:
        st.error(f"Error fetching assets list: {e}")
        return []

def add_asset(name: str, symbol: str, api_id: str, icon_url: str = "", location: str = "") -> bool:
    client = get_client()
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
    client = get_client()
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
    client = get_client()
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

def get_all_transactions(filter_type="すべて") -> List[Tuple]:
    """
    Get all transactions with joined asset info.
    Returns: list of (id, date, type, symbol, name, quantity, price_per_unit, total_amount, notes, asset_id)
    """
    client = get_client()
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

def add_transaction(date_obj, trans_type, asset_id, quantity, price_per_unit, total_amount, notes="", skip_duplicate_check=False) -> bool:
    client = get_client()
    if not client: return False
    
    # Check duplicate
    if not skip_duplicate_check:
        is_dup, _ = check_duplicate_transactions(date_obj, asset_id, quantity)
        if is_dup:
             st.warning("⚠️ 類似した取引が存在します (重複警告)")
             pass

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
            "notes": notes
        }
        client.table("transactions").insert(data).execute()
        return True
    except Exception as e:
        st.error(f"登録エラー: {e}")
        return False

def update_transaction(transaction_id, date_obj, trans_type, asset_id, quantity, price_per_unit, total_amount, notes="") -> bool:
    client = get_client()
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
            "notes": notes
        }
        client.table("transactions").update(data).eq("id", transaction_id).execute()
        return True
    except Exception as e:
        st.error(f"更新エラー: {e}")
        return False

def delete_transaction(transaction_id) -> bool:
    client = get_client()
    if not client: return False
    try:
        client.table("transactions").delete().eq("id", transaction_id).execute()
        return True
    except Exception as e:
        st.error(f"削除エラー: {e}")
        return False

def check_duplicate_transactions(date_obj, asset_id, quantity, tolerance_minutes=5):
    """
    Simple check if same asset and quantity exists around the time.
    """
    client = get_client()
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
    client = get_client()
    if not client: return [], 0, 0
    
    assets = get_all_assets()
    all_trans = get_all_transactions("すべて")
    
    # Calculate holdings in Python
    # trans item: (id, date, type, symbol, name, quantity, price_per_unit, total_amount, notes, asset_id)
    # asset item: (id, name, symbol, api_id, icon_url, location, created_at)
    
    holdings_map = {} # asset_id -> quantity
    
    for t in all_trans:
        # unpack t
        # (id, date, type, symbol, name, quantity, price, total, notes, asset_id) = t
        # Index 2 is type, 5 is quantity, 9 is asset_id
        t_type = t[2]
        qty = t[5]
        aid = t[9]
        
        current_qty = holdings_map.get(aid, 0.0)
        
        if t_type in ['Buy', 'Airdrop', 'Staking Reward', 'Interest', 'Gift']:
            current_qty += qty
        elif t_type in ['Sell', 'Transfer']:
            current_qty -= qty
            
        holdings_map[aid] = current_qty
        
    # Build result
    portfolio = []
    for a in assets:
        aid = a[0]
        qty = holdings_map.get(aid, 0.0)
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
            
    # Sort by holdings descending? The original SQL did logic, typically value matters but logic was DESC holdings
    # SQL: ORDER BY holdings DESC
    portfolio.sort(key=lambda x: x[6], reverse=True)
    
    return portfolio, len(assets), len(all_trans)

def calculate_cost_basis() -> Dict:
    """
    Calculate avg cost basis.
    Returns: { asset_id: {avg_cost, holdings, total_cost} }
    """
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
    """Specific helper for app.py dashboard logic (current year P/L)"""""
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

def get_portfolio_history(days: int = 365) -> List[Tuple]:
    """Returns list of (date_str, value)"""
    client = get_client()
    if not client: return []
    
    try:
        res = client.table("portfolio_snapshots").select("date, total_value_jpy").order("date", desc=True).limit(days).execute()
        
        data = []
        if res.data:
            for item in res.data:
                data.append((item['date'], item['total_value_jpy']))
            
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
        res = client.table("portfolio_snapshots")\
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
        res = client.table("portfolio_snapshots").select("date", count="exact", head=True).execute()
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
    Returns: {api_id: {usd, jpy, usd_24h_change, jpy_24h_change}}
    """
    client = get_client()
    if not client:
        return {}
    
    try:
        res = client.table("price_cache").select("*").execute()
        
        result = {}
        for item in res.data:
            result[item["api_id"]] = {
                "usd": item.get("price_usd"),
                "jpy": item.get("price_jpy"),
                "usd_24h_change": item.get("usd_24h_change"),
                "jpy_24h_change": item.get("usd_24h_change"),  # 同じ値を使用
            }
        return result
    except Exception as e:
        print(f"Price cache load error: {e}")
        return {}
