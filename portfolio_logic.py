"""Pure display and portfolio arithmetic; no network, UI state, or credentials."""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

JST = timezone(timedelta(hours=9))
MASK = "••••••"


def number(value: Any) -> float | None:
    try:
        result = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def money(value: Any, currency: str = "JPY", *, price: bool = False, masked: bool = False, signed: bool = False) -> str:
    if masked:
        return MASK
    val = number(value)
    if val is None:
        return "—"
    sign = ("−" if val < 0 else "+") if signed else ("−" if val < 0 else "")
    val = abs(val)
    decimals = 0 if currency == "JPY" else 2
    if price and 0 < val < 1:
        decimals = min(12, max(decimals, 3 - math.floor(math.log10(val))))
    elif price and val < 100 and currency == "USD":
        decimals = max(decimals, 4 if val < 1 else 2)
    body = f"{val:,.{decimals}f}"
    if price and decimals > 2:
        body = body.rstrip("0").rstrip(".")
    if val and float(body.replace(",", "")) == 0:
        body = f"<{10 ** -decimals:.{decimals}f}"
    return f"{sign}{'¥' if currency == 'JPY' else '$'}{body}"


def quantity(value: Any, *, masked: bool = False) -> str:
    if masked:
        return MASK
    val = number(value)
    return "—" if val is None else f"{val:,.8f}".rstrip("0").rstrip(".")


def percent(value: Any, *, signed: bool = True) -> str:
    val = number(value)
    if val is None:
        return "—"
    return f"{val:+.2f}%" if signed else f"{val:.1f}%"


def tone(value: Any) -> str:
    val = number(value)
    return "positive" if val is not None and val > 0 else "negative" if val is not None and val < 0 else "neutral"


def build_portfolio(holdings, prices: dict, costs: dict, currency: str) -> dict:
    """24h is the price effect on current quantities, excluding quantity changes."""
    rows = []
    for aid, symbol, name, api_id, icon, location, held in holdings:
        held = number(held)
        if held is None or held <= 0:
            continue
        data = prices.get(api_id, {})
        price = number(data.get(currency.lower()))
        if price is not None and price < 0:
            price = None
        value = held * price if price is not None else None
        change = number(data.get(f"{currency.lower()}_24h_change"))
        previous = value / (1 + change / 100) if value is not None and change is not None and change > -100 else None
        contribution = value - previous if previous is not None else None
        cost = costs.get(aid, {})
        usd_price = number(data.get("usd"))
        reference_cost = number(cost.get("total_cost"))
        reference_pl_usd = held * usd_price - reference_cost if usd_price is not None and reference_cost is not None else None
        rows.append(dict(id=aid, symbol=symbol, name=name, api_id=api_id, icon_url=icon,
                         location=location, holdings=held, price=price, value=value,
                         change=change, previous=previous, contribution=contribution,
                         reference_pl_usd=reference_pl_usd, avg_cost=number(cost.get("avg_cost"))))
    rows.sort(key=lambda r: r["value"] if r["value"] is not None else -1, reverse=True)
    known = [r for r in rows if r["value"] is not None]
    total = sum(r["value"] for r in known) if known else None
    previous_rows = [r for r in rows if r["previous"] is not None]
    previous_total = sum(r["previous"] for r in previous_rows)
    change_amount = sum(r["contribution"] for r in previous_rows) if previous_rows else None
    change_percent = change_amount / previous_total * 100 if previous_total > 0 else None
    complete = bool(rows) and len(known) == len(rows)
    for row in rows:
        row["weight"] = row["value"] / total * 100 if row["value"] is not None and total else None
    return dict(rows=rows, total=total, complete=complete,
                missing=[r["symbol"] for r in rows if r["value"] is None],
                change_amount=change_amount, change_percent=change_percent,
                change_complete=bool(rows) and len(previous_rows) == len(rows))


def history_series(records: list[dict], currency: str, days: int, today: date | None = None) -> list[dict]:
    today = today or datetime.now(JST).date()
    cutoff = today - timedelta(days=days - 1)
    result = []
    for row in records:
        try:
            day = date.fromisoformat(str(row["date"])[:10])
        except (ValueError, KeyError):
            continue
        value = number(row.get(f"total_value_{currency.lower()}"))
        if value is not None and value >= 0 and cutoff <= day <= today:
            result.append({"date": day.isoformat(), "value": value})
    return sorted(result, key=lambda r: r["date"])


def year_to_date(records: list[dict], current: float | None, flows: dict, currency: str, today: date | None = None) -> dict:
    """Year-end marked value plus external cash flows, never current FX on old data."""
    today = today or datetime.now(JST).date()
    baseline_day = date(today.year, 1, 1) - timedelta(days=1)
    field = f"total_value_{currency.lower()}"
    base = next((number(r.get(field)) for r in records if str(r.get("date")) == baseline_day.isoformat()), None)
    if base is None:
        return {"amount": None, "reason": "前年末の評価額記録がないため、年初来損益は未計算です。"}
    net_flow = number(flows.get(f"net_flow_{currency.lower()}"))
    if current is None or net_flow is None or flows.get(f"unknown_{currency.lower()}", True):
        return {"amount": None, "reason": "価格または期中の入出金評価に不足があるため、年初来損益は未計算です。"}
    return {"amount": current - base - net_flow, "reason": "前年末評価額と期中の購入・売却・出庫を反映。手数料を除く参考損益。"}


def convert_trade(quantity_value, input_price, currency: str, rate=None) -> dict:
    """Validate before persistence; preserve the original currency and conversion."""
    try:
        qty, price = Decimal(str(quantity_value)), Decimal(str(input_price))
        fx = Decimal("1") if currency == "USD" else Decimal(str(rate))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("数量・単価・為替レートを正しい数値で入力してください。") from None
    if currency not in ("JPY", "USD") or not all(v.is_finite() for v in (qty, price, fx)):
        raise ValueError("入力通貨または数値を確認してください。")
    if qty <= 0 or price < 0 or fx <= 0:
        raise ValueError("数量と為替レートは0より大きく、単価は0以上で入力してください。")
    usd = price / fx
    result = dict(quantity=float(qty), price_per_unit=float(usd), total_amount=float(qty * usd),
                  input_currency=currency, input_price=float(price), input_total=float(qty * price),
                  exchange_rate=float(fx))
    if not all(math.isfinite(v) for v in result.values() if isinstance(v, float)):
        raise ValueError("数値が大きすぎます。")
    return result


def goal_progress(held, target, weight=None, target_weight=None) -> dict:
    held, target, weight, target_weight = map(number, (held, target, weight, target_weight))
    ratio = held / target if held is not None and target is not None and target > 0 else None
    return {"ratio": ratio, "remaining": max(0, target - held) if ratio is not None else None,
            "weight_gap": target_weight - weight if target_weight is not None and weight is not None else None}
