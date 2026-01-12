"""
ポートフォリオスナップショット管理モジュール
日次の総資産額を記録し、資産推移を追跡する
"""

import sqlite3
from datetime import date, datetime
from database import DB_PATH


def save_portfolio_snapshot(total_value_jpy: float) -> bool:
    """
    現在の総資産額をスナップショットとして保存
    同じ日のスナップショットは上書きされる
    
    Args:
        total_value_jpy: 総資産額（JPY換算）
        
    Returns:
        成功した場合はTrue
    """
    try:
        today = date.today().isoformat()
        
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # UPSERTで同じ日は上書き
            cursor.execute("""
                INSERT INTO portfolio_snapshots (date, total_value_jpy)
                VALUES (?, ?)
                ON CONFLICT(date) DO UPDATE SET
                    total_value_jpy = excluded.total_value_jpy,
                    created_at = CURRENT_TIMESTAMP
            """, (today, total_value_jpy))
            
            conn.commit()
            
        return True
    except Exception as e:
        print(f"[ERROR] スナップショット保存失敗: {str(e)}")
        return False


def get_portfolio_history(days: int = 365) -> list:
    """
    過去のスナップショット履歴を取得
    
    Args:
        days: 取得する日数（デフォルト365日）
        
    Returns:
        [(date, total_value_jpy), ...] のリスト
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT date, total_value_jpy
                FROM portfolio_snapshots
                ORDER BY date DESC
                LIMIT ?
            """, (days,))
            
            results = cursor.fetchall()
            
        # 日付順に並び替え（古い→新）
        return list(reversed(results))
    except Exception as e:
        print(f"[ERROR] スナップショット取得失敗: {str(e)}")
        return []


def get_latest_snapshot() -> dict:
    """
    最新のスナップショット情報を取得
    
    Returns:
        {date: str, total_value_jpy: float} または None
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT date, total_value_jpy, created_at
                FROM portfolio_snapshots
                ORDER BY date DESC
                LIMIT 1
            """)
            
            result = cursor.fetchone()
            
        if result:
            return {
                'date': result[0],
                'total_value_jpy': result[1],
                'created_at': result[2]
            }
        return None
    except Exception as e:
        print(f"[ERROR] 最新スナップショット取得失敗: {str(e)}")
        return None


def get_snapshot_count() -> int:
    """スナップショットの総数を取得"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM portfolio_snapshots")
            return cursor.fetchone()[0]
    except:
        return 0
