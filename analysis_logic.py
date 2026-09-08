"""Currency-independent, public-only observations and analysis status labels."""
from datetime import datetime, timezone

from gemini_client import AnalysisUnavailable
from portfolio_logic import JST, number


def analysis_context(data, now=None):
    now = now or datetime.now(timezone.utc)
    stamp = data.get("updated_at")
    if not isinstance(stamp, datetime) or stamp.tzinfo is None:
        raise AnalysisUnavailable("stale_prices")
    if data.get("stale") or not 0 <= (now - stamp).total_seconds() <= 900:
        raise AnalysisUnavailable("stale_prices")
    if stamp.astimezone(JST).date() != now.astimezone(JST).date():
        raise AnalysisUnavailable("stale_prices")
    rows = []
    for row in data.get("rows", []):
        quote = data.get("prices", {}).get(row["api_id"], {})
        price, held = number(quote.get("usd")), number(row.get("holdings"))
        if price is None or price <= 0 or held is None or held <= 0:
            raise AnalysisUnavailable("missing_prices")
        value = price * held
        change = number(quote.get("usd_24h_change"))
        previous = value / (1 + change / 100) if change is not None and change > -100 else None
        rows.append({"symbol": str(row["symbol"])[:30], "value": value,
                     "change_24h_percent": change, "previous": previous})
    total = sum(r["value"] for r in rows)
    if not rows or not number(total) or total <= 0:
        raise AnalysisUnavailable("missing_prices")
    rows.sort(key=lambda r: r["value"], reverse=True)
    comparable = [r for r in rows if r["previous"] is not None]
    previous_total = sum(r["previous"] for r in comparable)
    impact = sum(r["value"] - r["previous"] for r in comparable)
    drivers = sorted(comparable, key=lambda r: abs(r["value"] - r["previous"]), reverse=True)[:3]
    return {"date": now.astimezone(JST).date().isoformat(), "prices_updated_at": stamp.isoformat(),
            "basis": "USD / 現在数量を固定した24時間の価格影響", "asset_count": len(rows),
            "change_complete": len(comparable) == len(rows),
            "coverage_percent": round(sum(r["value"] for r in comparable) / total * 100, 2),
            "change_percent": round(impact / previous_total * 100, 2) if previous_total else None,
            "top_assets": [{"symbol": r["symbol"], "weight_percent": round(r["value"] / total * 100, 2),
                            "change_24h_percent": r["change_24h_percent"]} for r in rows[:5]],
            "drivers": [{"symbol": r["symbol"],
                         "contribution_percentage_points": round((r["value"] - r["previous"]) / previous_total * 100, 3)}
                        for r in drivers]}


ERROR_MESSAGES = {
    "missing_key": "Geminiの接続設定を確認する必要があります。",
    "invalid_key": "GeminiのAPIキーまたは利用権限を確認する必要があります。",
    "model_unavailable": "設定されたGeminiモデルを利用できません。",
    "request_rejected": "Geminiが生成リクエストを受け付けませんでした。",
    "rate_limited": "Geminiの利用上限に達したため、更新を待機しています。",
    "network_error": "Geminiへの接続がタイムアウトしました。",
    "provider_error": "Geminiが一時的に利用できません。",
    "invalid_response": "生成内容を確認できなかったため、保存しませんでした。",
    "storage_error": "分析メモの保存先に接続できませんでした。",
    "backend_unconfigured": "分析メモの保存設定を確認する必要があります。",
    "stale_prices": "新しい価格データを取得でき次第、分析メモを更新します。",
    "missing_prices": "一部の価格が不足しているため、分析メモの更新を待っています。",
    "processing": "本日の分析メモを生成中です。少し待ってから表示を更新してください。",
    "daily_limit": "本日は生成を3回試みました。次回は翌日の閲覧時に再試行します。",
    "date_changed": "日付が変わったため、次の閲覧時に新しい日付で生成します。",
}
