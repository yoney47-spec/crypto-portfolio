import sqlite3
import requests
import time
from datetime import datetime
from database import DB_PATH

# New Assts to Import
NEW_ASSETS = [
    {"symbol": "QUBIC", "qty": 55976806, "api_id": "qubic-network", "location": "Qubic Wallet"},
    {"symbol": "PEPU", "qty": 208345, "api_id": "pepe-unchained", "location": "Metamask"},
]

TARGET_DATE = "01-01-2026" # DD-MM-YYYY
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
    url = f"https://api.coingecko.com/api/v3/coins/{api_id}/history"
    params = {"date": date_str, "localization": "false"}
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 429:
            time.sleep(60)
            return get_historical_price(api_id, date_str)
        response.raise_for_status()
        data = response.json()
        price = data.get("market_data", {}).get("current_price", {}).get("usd")
        return price if price else 0.0
    except Exception as e:
        print(f"Error fetching history for {api_id}: {e}")
        return 0.0

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("--- Starting Migration & Import ---")

    # 1. DB Migration: Add location column if not exists
    try:
        cursor.execute("ALTER TABLE assets ADD COLUMN location TEXT")
        conn.commit()
        print("Added 'location' column to assets table.")
    except sqlite3.OperationalError:
        print("'location' column already exists.")

    # 2. Import New Assets
    for item in NEW_ASSETS:
        symbol = item["symbol"]
        api_id = item["api_id"]
        qty = item["qty"]
        location = item["location"]

        print(f"\nProcessing {symbol} ({api_id})...")
        
        # Check if asset exists
        cursor.execute("SELECT id FROM assets WHERE api_id = ?", (api_id,))
        row = cursor.fetchone()
        
        asset_id = None
        
        if row:
            asset_id = row[0]
            print(f"Asset {symbol} already exists (ID: {asset_id}). Updating location...")
            cursor.execute("UPDATE assets SET location = ? WHERE id = ?", (location, asset_id))
            conn.commit()
        else:
            # Fetch info
            print(f"Fetching info for {api_id}...")
            info = get_coin_info(api_id)
            if not info:
                print(f"Skipping {symbol} due to info fetch failure.")
                continue
            
            name = info["name"]
            icon_url = info["image"]
            
            cursor.execute("INSERT INTO assets (symbol, name, api_id, icon_url, location) VALUES (?, ?, ?, ?, ?)", 
                           (symbol, name, api_id, icon_url, location))
            asset_id = cursor.lastrowid
            conn.commit()
            print(f"Created new asset {symbol} (ID: {asset_id}).")
            time.sleep(2)

        # Fetch Price
        print(f"Fetching price for {api_id} on {TARGET_DATE}...")
        price = get_historical_price(api_id, TARGET_DATE)
        if price == 0.0:
            print(f"Warning: Price is 0 for {symbol}.")
        else:
            print(f"Price: ${price}")
        
        total_amount = qty * price
        
        # Insert Buy Transaction
        cursor.execute("""
            INSERT INTO transactions (date, type, asset_id, quantity, price_per_unit, total_amount, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (DB_DATE, "Buy", asset_id, qty, price, total_amount, "Initial Import (2026-01-01)"))
        
        conn.commit()
        print(f"Recorded transaction for {symbol}.")
        
        time.sleep(3)

    conn.close()
    print("\n--- Completed ---")

if __name__ == "__main__":
    main()
