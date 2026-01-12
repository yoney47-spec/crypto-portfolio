"""
暗号資産ポートフォリオアプリ - データベーススキーマ定義
"""

import sqlite3
from datetime import datetime
from pathlib import Path

# データベースファイルのパス
DB_PATH = Path(__file__).parent / "crypto_portfolio.db"


def init_database():
    """データベースを初期化し、テーブルを作成する"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Users テーブル (将来的な拡張用)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 2. Assets テーブル (通貨マスタ)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            symbol TEXT NOT NULL UNIQUE,
            api_id TEXT NOT NULL,
            icon_url TEXT,
            location TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 3. Transactions テーブル (取引履歴)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TIMESTAMP NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('Buy', 'Sell', 'Airdrop', 'Staking Reward', 'Interest', 'Gift')),
            asset_id INTEGER NOT NULL,
            quantity REAL NOT NULL,
            price_per_unit REAL NOT NULL,
            total_amount REAL NOT NULL,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (asset_id) REFERENCES assets(id)
        )
    """)
    
    # 4. PortfolioSnapshots テーブル (資産推移記録)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS portfolio_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE NOT NULL UNIQUE,
            total_value_jpy REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # インデックスの作成 (パフォーマンス向上のため)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_transactions_date 
        ON transactions(date DESC)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_transactions_asset 
        ON transactions(asset_id)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_snapshots_date 
        ON portfolio_snapshots(date DESC)
    """)
    
    # 複合インデックス追加 (大量データ対応)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_transactions_asset_date 
        ON transactions(asset_id, date DESC)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_transactions_type_date 
        ON transactions(type, date DESC)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_transactions_asset_type 
        ON transactions(asset_id, type)
    """)
    
    conn.commit()
    conn.close()
    print(f"[OK] データベースを初期化しました: {DB_PATH}")


def insert_sample_assets():
    """サンプルの暗号資産データを投入する"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    sample_assets = [
        ("Bitcoin", "BTC", "bitcoin", "https://assets.coingecko.com/coins/images/1/small/bitcoin.png"),
        ("Ethereum", "ETH", "ethereum", "https://assets.coingecko.com/coins/images/279/small/ethereum.png"),
        ("Ripple", "XRP", "ripple", "https://assets.coingecko.com/coins/images/44/small/xrp-symbol-white-128.png"),
        ("Cardano", "ADA", "cardano", "https://assets.coingecko.com/coins/images/975/small/cardano.png"),
        ("Solana", "SOL", "solana", "https://assets.coingecko.com/coins/images/4128/small/solana.png"),
        ("Polkadot", "DOT", "polkadot", "https://assets.coingecko.com/coins/images/12171/small/polkadot.png"),
        ("Dogecoin", "DOGE", "dogecoin", "https://assets.coingecko.com/coins/images/5/small/dogecoin.png"),
        ("Polygon", "MATIC", "matic-network", "https://assets.coingecko.com/coins/images/4713/small/matic-token-icon.png"),
    ]
    
    try:
        cursor.executemany("""
            INSERT OR IGNORE INTO assets (name, symbol, api_id, icon_url)
            VALUES (?, ?, ?, ?)
        """, sample_assets)
        
        conn.commit()
        print(f"[OK] {cursor.rowcount}件のサンプル資産データを投入しました")
    except sqlite3.IntegrityError as e:
        print(f"[WARNING] データ投入エラー: {e}")
    finally:
        conn.close()


def migrate_database():
    """
    既存のデータベースを新しいスキーマに移行する
    CHECK制約を更新して新しい取引タイプをサポート
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # 既存のtransactionsテーブルがあるか確認
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='transactions'
        """)
        
        if cursor.fetchone():
            print("[INFO] transactionsテーブルが見つかりました。マイグレーションを実行します...")
            
            # 1. 一時テーブルを作成（新しいスキーマで）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transactions_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TIMESTAMP NOT NULL,
                    type TEXT NOT NULL CHECK(type IN ('Buy', 'Sell', 'Airdrop', 'Staking Reward', 'Interest', 'Gift')),
                    asset_id INTEGER NOT NULL,
                    quantity REAL NOT NULL,
                    price_per_unit REAL NOT NULL,
                    total_amount REAL NOT NULL,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (asset_id) REFERENCES assets(id)
                )
            """)
            
            # 2. 既存データを新テーブルにコピー
            cursor.execute("""
                INSERT INTO transactions_new 
                (id, date, type, asset_id, quantity, price_per_unit, total_amount, notes, created_at)
                SELECT id, date, type, asset_id, quantity, price_per_unit, total_amount, notes, created_at
                FROM transactions
            """)
            
            # 3. 古いテーブルを削除
            cursor.execute("DROP TABLE transactions")
            
            # 4. 新しいテーブルをリネーム
            cursor.execute("ALTER TABLE transactions_new RENAME TO transactions")
            
            # 5. インデックスを再作成
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_transactions_date 
                ON transactions(date DESC)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_transactions_asset 
                ON transactions(asset_id)
            """)
            
            # 複合インデックス追加
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_transactions_asset_date 
                ON transactions(asset_id, date DESC)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_transactions_type_date 
                ON transactions(type, date DESC)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_transactions_asset_type 
                ON transactions(asset_id, type)
            """)
            
            conn.commit()
            print("[OK] マイグレーションが完了しました")
        else:
            print("[INFO] transactionsテーブルが見つかりません。新規作成します")
            
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] マイグレーションエラー: {e}")
        raise
    finally:
        conn.close()


def get_connection():
    """データベース接続を取得する"""
    return sqlite3.connect(DB_PATH)


if __name__ == "__main__":
    # データベースの初期化
    init_database()
    
    # サンプルデータの投入
    insert_sample_assets()
