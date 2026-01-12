"""
チE�Eタベ�Eス移行スクリプト - location カラム追加
既存�EチE�Eタベ�Eスに location カラムを追加しまぁE
"""

import sqlite3
from database import DB_PATH

def migrate_add_location_column():
    """assets チE�Eブルに location カラムを追加する"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # カラムが既に存在するかチェチE��
        cursor.execute("PRAGMA table_info(assets)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'location' in columns:
            print("[INFO] location カラムは既に存在しまぁE)
            return
        
        # location カラムを追加
        cursor.execute("""
            ALTER TABLE assets 
            ADD COLUMN location TEXT DEFAULT ''
        """)
        
        conn.commit()
        print("[OK] location カラムを追加しました")
        
    except sqlite3.OperationalError as e:
        print(f"[ERROR] 移行エラー: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("チE�Eタベ�Eス移衁E location カラム追加")
    print("=" * 60)
    migrate_add_location_column()
