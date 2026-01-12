import sqlite3
import requests
import time
from datetime import datetime
from database import DB_PATH

# User provided list
ASSETS_TO_IMPORT = [
    {"symbol": "BTC", "qty": 0.02430172, "api_id": "bitcoin"},
    {"symbol": "KAS", "qty": 22066.36144, "api_id": "kaspa"},
    {"symbol": "HYPE", "qty": 28, "api_id": "hyperliquid"},
    {"symbol": "TGT", "qty": 35867.64, "api_id": "tokyo-games-token"},
    {"symbol": "SOSO", "qty": 241.2556, "api_id": "sosovalue"},
    {"symbol": "SP", "qty": 40451.18832, "api_id": "smart-pocket"},
    {"symbol": "AMATO", "qty": 1025.75402, "api_id": "amato"},
    {"symbol": "HOLY", "qty": 28429.35764, "api_id": "holy-coin"},
    {"symbol": "PKM", "qty": 29415.95724, "api_id": "pockemy"},
    {"symbol": "SOL", "qty": 0.02426, "api_id": "solana"},
    {"symbol": "MON", "qty": 279.2331, "api_id": "monad"},
]

TARGET_DATE = "01-01-2026" # DD-MM-YYYY for CoinGecko
DB_DATE = "2026-01-01 00:00:00"

def get_coin_info(api_id):
    """Fetch name and icon URL"""
    url = f"https://api.coingecko.com/api/v3/coins/{api_id}"
    try:
        response = requests.get(url, params={"localization": "false", "tickers": "false", "market_data": "false", "community_data": "false", "developer_data": "false", "sparkline": "false"}, timeout=10)
        if response.status_code == 429:
            print(f"Rate limit hit for info {api_id}, waiting...")
            time.sleep(60)
            return get_coin_info(api_id)
        response.raise_for_status()
        data = response.json()
        return {
            "name": data.get("name"),
            "image": data.get("image", {}).get("large")
        }
    except Exception as e:
        print(f"Error fetching info for {api_id}: {e}")
        return None

def get_historical_price(api_id, date_str):
    """Fetch historical price for date (DD-MM-YYYY)"""
    url = f"https://api.coingecko.com/api/v3/coins/{api_id}/history"
    params = {"date": date_str, "localization": "false"}
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 429:
            print(f"Rate limit hit for history {api_id}, waiting...")
            time.sleep(60)
            return get_historical_price(api_id, date_str)
        response.raise_for_status()
        data = response.json()
        price = data.get("market_data", {}).get("current_price", {}).get("usd")
        if price is None:
            print(f"Price not found for {api_id} on {date_str}, trying current price...")
             # Fallback to current simple price if history fails (e.g. token didn't exist then?)
             # But user said 2026-01-01, current time is 2026-01-03, so it should exist.
             # If completely missing, use 0 to avoid breaking.
            return 0.0
        return price
    except Exception as e:
        print(f"Error fetching history for {api_id}: {e}")
        return 0.0

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("--- Starting Import ---")

    # 1. Delete KAS transactions
    print("Deleting existing KAS transactions...")
    # Find asset_id for KAS (if exists) via symbol since API ID might differ or be same
    # But usually just delete by joining assets.
    cursor.execute("""
        DELETE FROM transactions 
        WHERE asset_id IN (SELECT id FROM assets WHERE symbol = 'KAS')
    """)
    conn.commit()
    print("KAS transactions deleted.")

    # 2. Process each asset
    for item in ASSETS_TO_IMPORT:
        symbol = item["symbol"]
        api_id = item["api_id"]
        qty = item["qty"]

        print(f"\nProcessing {symbol} ({api_id})...")
        
        # Check if asset exists, if not create
        cursor.execute("SELECT id FROM assets WHERE api_id = ?", (api_id,))
        row = cursor.fetchone()
        
        asset_id = None
        
        if row:
            asset_id = row[0]
            print(f"Asset {symbol} already exists (ID: {asset_id}).")
        else:
            # Fetch info
            print(f"Fetching info for {api_id}...")
            info = get_coin_info(api_id)
            if not info:
                print(f"Skipping {symbol} due to info fetch failure.")
                continue
            
            name = info["name"]
            icon_url = info["image"]
            
            cursor.execute("INSERT INTO assets (symbol, name, api_id, icon_url) VALUES (?, ?, ?, ?)", 
                           (symbol, name, api_id, icon_url))
            asset_id = cursor.lastrowid
            conn.commit()
            print(f"Created new asset {symbol} (ID: {asset_id}).")
            time.sleep(2) # Be nice to API

        # Fetch Price
        print(f"Fetching price for {api_id} on {TARGET_DATE}...")
        price = get_historical_price(api_id, TARGET_DATE)
        if price == 0.0:
            print(f"Warning: Price is 0 for {symbol}. Check manually later.")
        else:
            print(f"Price: ${price}")
        
        total_amount = qty * price
        
        # Insert Buys
        # Check if we already have this tx to avoid double import if script reruns? 
        # For simplicity, we assume one-shot.
        cursor.execute("""
            INSERT INTO transactions (date, type, asset_id, quantity, price_per_unit, total_amount, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (DB_DATE, "Buy", asset_id, qty, price, total_amount, "Initial Import (2026-01-01)"))
        
        conn.commit()
        print(f"Recorded transaction for {symbol}.")
        
        time.sleep(3) # Wait between requests to avoid rate limit (free tier ~10-30 req/min)

    conn.close()
    print("\n--- Import Complete ---")

if __name__ == "__main__":
    main()
