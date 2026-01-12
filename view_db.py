"""
繝・・繧ｿ繝吶・繧ｹ縺ｮ蜀・ｮｹ繧堤｢ｺ隱阪☆繧九Θ繝ｼ繝・ぅ繝ｪ繝・ぅ繧ｹ繧ｯ繝ｪ繝励ヨ
"""

import sqlite3
from database import DB_PATH
import pandas as pd


def show_all_tables():
    """縺吶∋縺ｦ縺ｮ繝・・繝悶Ν縺ｮ蜀・ｮｹ繧定｡ｨ遉ｺ縺吶ｋ"""
    conn = sqlite3.connect(DB_PATH)
    
    print("=" * 80)
    print("繝・・繧ｿ繝吶・繧ｹ蜀・ｮｹ遒ｺ隱・)
    print("=" * 80)
    print()
    
    # 繝・・繝悶Ν荳隕ｧ繧貞叙蠕・
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    for (table_name,) in tables:
        # 繧ｻ繧ｭ繝･繝ｪ繝・ぅ: 繝・・繝悶Ν蜷阪・讀懆ｨｼ
        if not table_name.replace('_', '').isalnum():
            print(f"笞・・ 繧ｹ繧ｭ繝・・: 荳肴ｭ｣縺ｪ繝・・繝悶Ν蜷・'{table_name}'")
            continue
            
        print(f"\n縲須table_name}縲・)
        print("-" * 80)
        
        # 讀懆ｨｼ貂医∩縺ｮ繝・・繝悶Ν蜷阪ｒ菴ｿ逕ｨ
        df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
        
        if len(df) == 0:
            print("(繝・・繧ｿ縺ｪ縺・")
        else:
            print(df.to_string(index=False))
        
        print()
    
    conn.close()


def show_schema():
    """繝・・繧ｿ繝吶・繧ｹ繧ｹ繧ｭ繝ｼ繝槭ｒ陦ｨ遉ｺ縺吶ｋ"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("=" * 80)
    print("繝・・繧ｿ繝吶・繧ｹ繧ｹ繧ｭ繝ｼ繝・)
    print("=" * 80)
    print()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    for (table_name,) in tables:
        # 繧ｻ繧ｭ繝･繝ｪ繝・ぅ: 繝・・繝悶Ν蜷阪・讀懆ｨｼ (闍ｱ謨ｰ蟄励→繧｢繝ｳ繝繝ｼ繧ｹ繧ｳ繧｢縺ｮ縺ｿ險ｱ蜿ｯ)
        if not table_name.replace('_', '').isalnum():
            print(f"笞・・ 繧ｹ繧ｭ繝・・: 荳肴ｭ｣縺ｪ繝・・繝悶Ν蜷・'{table_name}'")
            continue
            
        print(f"\n縲須table_name}縲・)
        print("-" * 80)
        
        # 讀懆ｨｼ貂医∩縺ｮ繝・・繝悶Ν蜷阪ｒ菴ｿ逕ｨ
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        
        for col in columns:
            col_id, name, col_type, not_null, default_val, pk = col
            pk_str = " [PRIMARY KEY]" if pk else ""
            null_str = " NOT NULL" if not_null else ""
            default_str = f" DEFAULT {default_val}" if default_val else ""
            print(f"  {name}: {col_type}{pk_str}{null_str}{default_str}")
        
        print()
    
    conn.close()


if __name__ == "__main__":
    show_schema()
    show_all_tables()
