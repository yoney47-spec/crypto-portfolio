"""Shared CoinGecko access with process-wide caching and rate-limit protection."""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple

import requests
import streamlit as st


COINGECKO_API_BASE = "https://api.coingecko.com/api/v3"
CURRENT_PRICE_TTL_SECONDS = 10 * 60
DISPLAY_STALE_MAX_SECONDS = 6 * 60 * 60
SNAPSHOT_STALE_MAX_SECONDS = 15 * 60
RATE_LIMIT_COOLDOWN_SECONDS = 60


class CoinGeckoError(RuntimeError):
    """Base error for CoinGecko requests."""


class CoinGeckoRateLimited(CoinGeckoError):
    """Raised when CoinGecko asks the app to slow down."""

    def __init__(self, retry_after_seconds: int):
        super().__init__("CoinGecko rate limit reached")
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True)
class PriceResult:
    prices: Dict[str, Dict[str, Optional[float]]]
    source: str
    stale: bool
    updated_at: Optional[datetime]


class _MarketState:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.prices: Dict[str, Dict[str, Any]] = {}
        self.blocked_until = 0.0


@st.cache_resource(show_spinner=False)
def _shared_market_state() -> _MarketState:
    """One cache and one rate-limit gate shared by all Streamlit sessions."""
    return _MarketState()


def _canonical_ids(api_ids: Iterable[str]) -> Tuple[str, ...]:
    return tuple(sorted({str(api_id).strip() for api_id in api_ids if str(api_id).strip()}))


def _optional_number(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _demo_api_key() -> str:
    try:
        return str(st.secrets["coingecko"]["api_key"]).strip()
    except Exception:
        return ""


def coingecko_headers() -> Dict[str, str]:
    headers = {"Accept": "application/json"}
    api_key = _demo_api_key()
    if api_key:
        headers["x-cg-demo-api-key"] = api_key
    return headers


def _retry_after_seconds(response: requests.Response) -> int:
    value = response.headers.get("Retry-After")
    try:
        parsed = int(float(value))
    except (TypeError, ValueError):
        parsed = RATE_LIMIT_COOLDOWN_SECONDS
    return max(1, min(parsed, 5 * 60))


def _activate_rate_limit(response: requests.Response) -> int:
    retry_after = _retry_after_seconds(response)
    state = _shared_market_state()
    with state.lock:
        state.blocked_until = max(state.blocked_until, time.time() + retry_after)
    return retry_after


def coingecko_cooldown_remaining() -> int:
    state = _shared_market_state()
    with state.lock:
        return max(0, math.ceil(state.blocked_until - time.time()))


def coingecko_get_json(
    path: str,
    *,
    params: Mapping[str, Any],
    timeout: int = 15,
    max_attempts: int = 1,
) -> Any:
    """Fetch one CoinGecko endpoint while preventing retry storms after 429."""
    state = _shared_market_state()
    with state.lock:
        remaining = coingecko_cooldown_remaining()
        if remaining:
            raise CoinGeckoRateLimited(remaining)

        url = path if path.startswith("http") else f"{COINGECKO_API_BASE}/{path.lstrip('/')}"
        attempts = max(1, max_attempts)

        for attempt in range(attempts):
            try:
                response = requests.get(
                    url,
                    params=dict(params),
                    headers=coingecko_headers(),
                    timeout=timeout,
                )
                if response.status_code == 429:
                    raise CoinGeckoRateLimited(_activate_rate_limit(response))
                if response.status_code >= 500 and attempt < attempts - 1:
                    time.sleep(1)
                    continue
                response.raise_for_status()
                return response.json()
            except CoinGeckoRateLimited:
                raise
            except (requests.RequestException, ValueError) as exc:
                if attempt < attempts - 1:
                    time.sleep(1)
                    continue
                raise CoinGeckoError("CoinGecko request failed") from exc

    raise CoinGeckoError("CoinGecko request failed")


def _normalize_prices(
    api_ids: Tuple[str, ...], payload: Mapping[str, Any]
) -> Dict[str, Dict[str, Optional[float]]]:
    result: Dict[str, Dict[str, Optional[float]]] = {}
    for api_id in api_ids:
        item = payload.get(api_id) if isinstance(payload, Mapping) else None
        item = item if isinstance(item, Mapping) else {}
        result[api_id] = {
            "usd": _optional_number(item.get("usd")),
            "jpy": _optional_number(item.get("jpy")),
            "usd_24h_change": _optional_number(item.get("usd_24h_change")),
            "jpy_24h_change": _optional_number(item.get("jpy_24h_change")),
        }
    return result


def _parse_timestamp(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def _seed_persisted_prices(
    state: _MarketState,
    api_ids: Tuple[str, ...],
    fallback_prices: Optional[Mapping[str, Mapping[str, Any]]],
) -> None:
    if not fallback_prices:
        return

    for api_id in api_ids:
        item = fallback_prices.get(api_id)
        if not isinstance(item, Mapping):
            continue
        timestamp = _parse_timestamp(item.get("updated_at"))
        if timestamp is None:
            continue
        existing = state.prices.get(api_id)
        if existing and float(existing.get("updated_at") or 0) >= timestamp:
            continue
        state.prices[api_id] = {
            "data": {
                "usd": _optional_number(item.get("usd")),
                "jpy": _optional_number(item.get("jpy")),
                "usd_24h_change": _optional_number(item.get("usd_24h_change")),
                "jpy_24h_change": _optional_number(item.get("jpy_24h_change")),
            },
            "updated_at": timestamp,
            "source": "persisted",
        }


def _cached_result(
    state: _MarketState,
    api_ids: Tuple[str, ...],
    *,
    max_age_seconds: int,
    stale: bool,
) -> Optional[PriceResult]:
    now = time.time()
    entries = []
    for api_id in api_ids:
        entry = state.prices.get(api_id)
        if not entry or now - float(entry.get("updated_at") or 0) > max_age_seconds:
            return None
        entries.append(entry)

    if not entries:
        return None

    updated_at_epoch = min(float(entry["updated_at"]) for entry in entries)
    sources = {str(entry.get("source") or "memory") for entry in entries}
    source = sources.pop() if len(sources) == 1 else "mixed-cache"
    if not stale and source != "persisted":
        source = "memory"

    return PriceResult(
        prices={api_id: dict(state.prices[api_id]["data"]) for api_id in api_ids},
        source=source,
        stale=stale,
        updated_at=datetime.fromtimestamp(updated_at_epoch).astimezone(),
    )


def get_current_prices(
    api_ids: Iterable[str],
    *,
    fallback_prices: Optional[Mapping[str, Mapping[str, Any]]] = None,
    force_refresh: bool = False,
    max_stale_seconds: int = DISPLAY_STALE_MAX_SECONDS,
) -> PriceResult:
    """Return batched USD/JPY prices shared across pages and user sessions."""
    ids = _canonical_ids(api_ids)
    if not ids:
        return PriceResult(prices={}, source="empty", stale=False, updated_at=None)

    state = _shared_market_state()
    with state.lock:
        _seed_persisted_prices(state, ids, fallback_prices)

        if not force_refresh:
            fresh = _cached_result(
                state,
                ids,
                max_age_seconds=CURRENT_PRICE_TTL_SECONDS,
                stale=False,
            )
            if fresh:
                return fresh

        stale_result = _cached_result(
            state,
            ids,
            max_age_seconds=max_stale_seconds,
            stale=True,
        )

        try:
            payload = coingecko_get_json(
                "/simple/price",
                params={
                    "ids": ",".join(ids),
                    "vs_currencies": "usd,jpy",
                    "include_24hr_change": "true",
                },
                timeout=15,
                max_attempts=1 if stale_result else 2,
            )
            if not isinstance(payload, Mapping):
                raise CoinGeckoError("Unexpected CoinGecko response")
            prices = _normalize_prices(ids, payload)
            updated_at = time.time()
            for api_id, data in prices.items():
                state.prices[api_id] = {
                    "data": data,
                    "updated_at": updated_at,
                    "source": "live",
                }
            return PriceResult(
                prices=prices,
                source="live",
                stale=False,
                updated_at=datetime.fromtimestamp(updated_at).astimezone(),
            )
        except CoinGeckoError:
            if stale_result:
                return stale_result
            raise
