
import sqlite3
import toml
from database_supabase import CustomSupabaseClient
from datetime import datetime

# Connect to local SQLite
SQLITE_DB_PATH = "crypto_portfolio.db"
conn = sqlite3.connect(SQLITE_DB_PATH)
cursor = conn.cursor()

# Connect to Supabase
secrets = toml.load(".streamlit/secrets.toml")
url = secrets["supabase"]["url"]
key = secrets["supabase"]["key"]
supabase = CustomSupabaseClient(url, key)

def migrate_assets():
    print("Migrating Assets...")
    cursor.execute("SELECT id, name, symbol, api_id, icon_url, location FROM assets")
    rows = cursor.fetchall()
    
    mapping_id = {} # old_id -> new_id (if we need to re-map, but let's try to keep IDs if possible, or just map FKs)
    
    for row in rows:
        old_id, name, symbol, api_id, icon_url, location = row
        data = {
            "name": name,
            "symbol": symbol,
            "api_id": api_id,
            "icon_url": icon_url,
            "location": location
        }
        
        # Check if exists
        existing = supabase.table("assets").select("id").eq("symbol", symbol).execute()
        if existing.data:
            print(f"  Skipping {symbol} (already exists). ID: {existing.data[0]['id']}")
            mapping_id[old_id] = existing.data[0]['id']
        else:
            try:
                # Insert
                res = supabase.table("assets").insert(data).execute()
                # Postgrest returns data list
                new_id = res.data[0]['id']
                print(f"  Inserted {symbol}. New ID: {new_id}")
                mapping_id[old_id] = new_id
            except Exception as e:
                print(f"  Error inserting {symbol}: {e}")
                
    return mapping_id

def migrate_transactions(asset_map):
    print("\nMigrating Transactions...")
    cursor.execute("SELECT date, type, asset_id, quantity, price_per_unit, total_amount, notes FROM transactions")
    rows = cursor.fetchall()
    
    count = 0
    for row in rows:
        date_str, type_, asset_id, quantity, price, total, notes = row
        
        if asset_id not in asset_map:
            print(f"  Skipping transaction for unknown asset ID {asset_id}")
            continue
            
        new_asset_id = asset_map[asset_id]
        
        # Format date assuming ISO string or similar from SQLite
        # SQLite: 2026-01-05 12:00:00 -> Supabase: needs ISO8601
        
        data = {
            "date": date_str,
            "type": type_,
            "asset_id": new_asset_id,
            "quantity": quantity,
            "price_per_unit": price,
            "total_amount": total,
            "notes": notes
        }
        
        try:
            # Check for duplicates? Hard to tell exact duplicates.
            # For simplicity, we just insert. If user runs this twice, they get dupes. 
            # Ideally we check, but let's assume one-time run.
            supabase.table("transactions").insert(data).execute()
            count += 1
            if count % 10 == 0:
                print(f"  Migrated {count} transactions...")
        except Exception as e:
            print(f"  Error inserting transaction: {e}")
            
    print(f"Done. Migrated {count} transactions.")

def migrate_snapshots():
    print("\nMigrating Snapshots...")
    cursor.execute("SELECT date, total_value_jpy FROM portfolio_snapshots")
    rows = cursor.fetchall()
    
    count = 0
    for row in rows:
        date_str, val = row
        data = {
            "date": date_str, # date type in Postgres
            "total_value_jpy": val
        }
        
        try:
            # Upsert by date
            supabase.table("portfolio_snapshots").upsert(data, on_conflict="date").execute()
            count += 1
        except Exception as e:
            print(f"  Error inserting snapshot: {e}")
            
    print(f"Done. Migrated {count} snapshots.")

if __name__ == "__main__":
    try:
        asset_map = migrate_assets()
        migrate_transactions(asset_map)
        migrate_snapshots()
        print("\nMigration Complete!")
    except Exception as e:
        print(f"\nMigration Failed: {e}")
    finally:
        conn.close()
