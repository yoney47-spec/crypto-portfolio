"""
暗号資産ポートフォリオアプリ - 定数定義
"""

# 取引タイプの定義
TRANSACTION_TYPES = {
    "Buy": {
        "label": "購入 (Buy)",
        "icon": "🟢",
        "color": "#4CAF50",
        "is_cost_free": False,
        "description": "暗号資産を購入した取引"
    },
    "Sell": {
        "label": "売却 (Sell)",
        "icon": "🔴",
        "color": "#F44336",
        "is_cost_free": False,
        "description": "暗号資産を売却した取引"
    },
    "Transfer": {
        "label": "移動 (Transfer)",
        "icon": "📤",
        "color": "#607D8B",
        "is_cost_free": True,
        "description": "別ウォレット/取引所への移動（ポートフォリオから除外）"
    },
    "Airdrop": {
        "label": "エアドロップ (Airdrop)",
        "icon": "🎁",
        "color": "#9C27B0",
        "is_cost_free": True,
        "description": "プロジェクトからの無償配布"
    },
    "Staking Reward": {
        "label": "ステーキング報酬 (Staking Reward)",
        "icon": "💰",
        "color": "#FF9800",
        "is_cost_free": True,
        "description": "ステーキングによる報酬"
    },
    "Interest": {
        "label": "利息 (Interest)",
        "icon": "📈",
        "color": "#03A9F4",
        "is_cost_free": True,
        "description": "レンディングやDeFiプロトコルからの利息"
    },
    "Gift": {
        "label": "贈与 (Gift)",
        "icon": "🎀",
        "color": "#E91E63",
        "is_cost_free": True,
        "description": "他者からの贈与"
    }
}

# 取引タイプのリスト（検証用）
VALID_TRANSACTION_TYPES = list(TRANSACTION_TYPES.keys())

# コストゼロ取引のリスト
COST_FREE_TYPES = [t for t, v in TRANSACTION_TYPES.items() if v["is_cost_free"]]

# コストあり取引のリスト
COST_BASED_TYPES = [t for t, v in TRANSACTION_TYPES.items() if not v["is_cost_free"]]


def get_transaction_type_info(transaction_type):
    """
    取引タイプの情報を取得
    
    Args:
        transaction_type (str): 取引タイプ
        
    Returns:
        dict: 取引タイプの情報、見つからない場合はNone
    """
    return TRANSACTION_TYPES.get(transaction_type)


def is_cost_free_transaction(transaction_type):
    """
    コストゼロの取引かどうかを判定
    
    Args:
        transaction_type (str): 取引タイプ
        
    Returns:
        bool: コストゼロの場合True
    """
    info = get_transaction_type_info(transaction_type)
    return info["is_cost_free"] if info else False
