"""
Gemini API クライアント - ポートフォリオコメント生成
"""

import streamlit as st
import google.generativeai as genai
from typing import Optional, Dict
from datetime import datetime


def init_gemini() -> bool:
    """Gemini APIを初期化"""
    try:
        api_key = st.secrets.get("gemini", {}).get("api_key")
        if not api_key:
            return False
        genai.configure(api_key=api_key)
        return True
    except Exception as e:
        print(f"Gemini init error: {e}")
        return False


def generate_portfolio_comment(portfolio_data: Dict) -> Optional[str]:
    """
    ポートフォリオデータからAIコメントを生成
    
    Args:
        portfolio_data: {
            'total_value': float,          # 総資産 (USD)
            'total_value_jpy': float,      # 総資産 (JPY)
            'change_percent': float,       # 前日比 %
            'change_amount': float,        # 前日比 金額
            'asset_count': int,            # 保有銘柄数
            'top_assets': [                # 上位保有銘柄
                {'symbol': str, 'percent': float, 'change_24h': float}, ...
            ],
            'top_performer': {'symbol': str, 'change': float},   # 急上昇
            'worst_performer': {'symbol': str, 'change': float}, # 急下落
        }
    
    Returns:
        生成されたコメント (200-300文字程度) または None
    """
    if not init_gemini():
        print("Gemini API not configured")
        return None
    
    try:
        # ポートフォリオデータからプロンプト用テキストを作成
        total_value = portfolio_data.get('total_value', 0)
        total_value_jpy = portfolio_data.get('total_value_jpy', 0)
        change_percent = portfolio_data.get('change_percent', 0)
        change_amount = portfolio_data.get('change_amount', 0)
        asset_count = portfolio_data.get('asset_count', 0)
        top_assets = portfolio_data.get('top_assets', [])
        top_performer = portfolio_data.get('top_performer', {})
        worst_performer = portfolio_data.get('worst_performer', {})
        
        # 上位銘柄のテキスト
        top_assets_text = ""
        for i, asset in enumerate(top_assets[:5], 1):
            top_assets_text += f"  {i}. {asset['symbol']}: 構成比 {asset['percent']:.1f}%, 24h変動 {asset['change_24h']:+.1f}%\n"
        
        prompt = f"""あなたは暗号資産投資に詳しいアナリストです。
以下のポートフォリオデータを分析し、200〜300文字程度で簡潔なコメントを日本語で作成してください。

【ポートフォリオデータ】
- 総資産: ${total_value:,.0f} USD (約 ¥{total_value_jpy:,.0f})
- 前日比: {change_percent:+.1f}% (${change_amount:+,.0f})
- 保有銘柄数: {asset_count}銘柄

【上位保有銘柄】
{top_assets_text}
【本日の注目銘柄】
- 急上昇: {top_performer.get('symbol', '-')} ({top_performer.get('change', 0):+.1f}%)
- 急下落: {worst_performer.get('symbol', '-')} ({worst_performer.get('change', 0):+.1f}%)

【コメントに含める内容】
1. ポートフォリオ全体の簡単な評価（前日比の変動について）
2. 主要銘柄の動向についての一言
3. 簡潔なアドバイスや見通し（1文程度）

※絵文字は使用せず、簡潔で読みやすい文章にしてください。
※200〜300文字に収めてください。
"""

        # Gemini 2.0 Flash モデルを使用
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                max_output_tokens=500,
                temperature=0.7,
            )
        )
        
        if response and response.text:
            comment = response.text.strip()
            # 長すぎる場合は切り詰め（安全策）
            if len(comment) > 500:
                comment = comment[:497] + "..."
            return comment
        
        return None
        
    except Exception as e:
        print(f"Gemini generation error: {e}")
        return None


def test_gemini_connection() -> bool:
    """Gemini API接続テスト"""
    if not init_gemini():
        return False
    
    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content("Say 'Hello' in Japanese")
        return response is not None and response.text is not None
    except Exception as e:
        print(f"Gemini test error: {e}")
        return False
