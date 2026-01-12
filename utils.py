"""
共通ユーティリティ関数
"""

import re
from typing import Optional

def sanitize_symbol(symbol: str, max_length: int = 10) -> str:
    """
    通貨シンボルをサニタイズ
    
    Args:
        symbol: 入力シンボル
        max_length: 最大文字数
        
    Returns:
        サニタイズされたシンボル (大文字英数字のみ)
    """
    if not symbol:
        return ""
    # 英数字のみ抽出して大文字化
    clean = ''.join(c for c in symbol.upper() if c.isalnum())
    return clean[:max_length]


def validate_quantity(quantity: float) -> tuple[bool, Optional[str]]:
    """
    数量の妥当性をチェック
    
    Args:
        quantity: チェックする数量
        
    Returns:
        (有効かどうか, エラーメッセージ)
    """
    if quantity <= 0:
        return False, "数量は0より大きい値を入力してください"
    
    if quantity > 1e15:  # 1千兆以上
        return False, "数量が大きすぎます"
    
    return True, None


def validate_price(price: float) -> tuple[bool, Optional[str]]:
    """
    価格の妥当性をチェック
    
    Args:
        price: チェックする価格
        
    Returns:
        (有効かどうか, エラーメッセージ)
    """
    if price < 0:
        return False, "価格は0以上の値を入力してください"
    
    if price > 1e12:  # 1兆ドル以上
        return False, "価格が大きすぎます"
    
    return True, None


def validate_api_id(api_id: str) -> tuple[bool, Optional[str]]:
    """
    CoinGecko API IDの妥当性をチェック
    
    Args:
        api_id: チェックするAPI ID
        
    Returns:
        (有効かどうか, エラーメッセージ)
    """
    if not api_id:
        return False, "API IDを入力してください"
    
    # 小文字英数字とハイフンのみ許可
    if not re.match(r'^[a-z0-9-]+$', api_id):
        return False, "API IDは小文字英数字とハイフンのみ使用できます"
    
    if len(api_id) > 50:
        return False, "API IDが長すぎます"
    
    return True, None


# チャート用カラーパレット (共通定義)
CHART_COLORS = [
    '#00d9ff', '#7000ff', '#ff00aa', '#00ff9d', '#ffcc00', 
    '#ff4b4b', '#2e2e2e', '#575757', '#888888', '#aaaaaa'
]

# API設定
API_RETRY_COUNT = 3
API_TIMEOUT = 10
API_BASE_DELAY = 0.5
