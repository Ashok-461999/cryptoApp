"""Binance USDT-M derivatives analytics — OI, funding, L/S, CVD, liq map, order book."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import get_settings
from app.services.binance_data import normalize_pair

logger = logging.getLogger(__name__)


def _fapi_base() -> str:
    return get_settings().binance_futures_base_url.rstrip("/")


def _fapi_data(path: str, params: dict[str, Any]) -> list[dict] | dict:
    try:
        r = httpx.get(f"{_fapi_base()}{path}", params=params, timeout=12)
        r.raise_for_status()
        return r.json()
    except Exception:
        logger.debug("Futures data %s failed", path)
        return []


def get_open_interest_usdt(symbol: str) -> float:
    pair = normalize_pair(symbol)
    try:
        r = httpx.get(f"{_fapi_base()}/fapi/v1/openInterest", params={"symbol": pair}, timeout=10)
        r.raise_for_status()
        body = r.json()
        oi = float(body.get("openInterest") or 0)
        from app.services.binance_data import binance_data
        price = binance_data.get_price(pair)
        return oi * price if price > 0 else oi
    except Exception:
        return 0.0


def get_oi_change_24h_pct(symbol: str) -> float:
    pair = normalize_pair(symbol)
    rows = _fapi_data(
        "/futures/data/openInterestHist",
        {"symbol": pair, "period": "1h", "limit": 24},
    )
    if not isinstance(rows, list) or len(rows) < 2:
        return 0.0
    first = float(rows[0].get("sumOpenInterestValue") or rows[0].get("sumOpenInterest") or 0)
    last = float(rows[-1].get("sumOpenInterestValue") or rows[-1].get("sumOpenInterest") or 0)
    if first <= 0:
        return 0.0
    return round((last - first) / first * 100, 2)


def get_long_short_ratio(symbol: str) -> float:
    pair = normalize_pair(symbol)
    rows = _fapi_data(
        "/futures/data/globalLongShortAccountRatio",
        {"symbol": pair, "period": "5m", "limit": 1},
    )
    if isinstance(rows, list) and rows:
        return float(rows[-1].get("longShortRatio") or 1.0)
    return 1.0


def get_taker_buy_sell_ratio(symbol: str) -> float:
    pair = normalize_pair(symbol)
    rows = _fapi_data(
        "/futures/data/takerlongshortRatio",
        {"symbol": pair, "period": "5m", "limit": 1},
    )
    if isinstance(rows, list) and rows:
        return float(rows[-1].get("buySellRatio") or 1.0)
    return 1.0


def get_cvd_from_klines(symbol: str, limit: int = 60) -> dict[str, Any]:
    """Cumulative volume delta from taker buy vs sell on 5m klines."""
    pair = normalize_pair(symbol)
    try:
        r = httpx.get(
            f"{_fapi_base()}/fapi/v1/klines",
            params={"symbol": pair, "interval": "5m", "limit": limit},
            timeout=12,
        )
        r.raise_for_status()
        rows = r.json()
    except Exception:
        return {"cvd": 0.0, "cvd_trend": "flat", "cvd_confirming": True}

    cvd = 0.0
    for row in rows:
        vol = float(row[5])
        taker_buy = float(row[9]) if len(row) > 9 else vol * 0.5
        cvd += (2 * taker_buy - vol)

    recent = rows[-12:] if len(rows) >= 12 else rows
    rcvd = 0.0
    for row in recent:
        vol = float(row[5])
        taker_buy = float(row[9]) if len(row) > 9 else vol * 0.5
        rcvd += (2 * taker_buy - vol)

    trend = "rising" if rcvd > 0 else ("falling" if rcvd < 0 else "flat")
    return {"cvd": round(cvd, 2), "cvd_trend": trend, "cvd_recent": round(rcvd, 2)}


def get_order_book_walls(symbol: str, price: float, pct: float = 2.0) -> dict[str, Any]:
    pair = normalize_pair(symbol)
    try:
        r = httpx.get(f"{_fapi_base()}/fapi/v1/depth", params={"symbol": pair, "limit": 100}, timeout=10)
        r.raise_for_status()
        book = r.json()
    except Exception:
        return {"bid_wall": 0.0, "ask_wall": 0.0, "bid_wall_price": 0.0, "ask_wall_price": 0.0}

    lo, hi = price * (1 - pct / 100), price * (1 + pct / 100)
    bid_wall, ask_wall = 0.0, 0.0
    bid_px, ask_px = 0.0, 0.0
    for px, qty in book.get("bids") or []:
        p, q = float(px), float(qty)
        if p >= lo:
            usdt = p * q
            if usdt > bid_wall:
                bid_wall, bid_px = usdt, p
    for px, qty in book.get("asks") or []:
        p, q = float(px), float(qty)
        if p <= hi:
            usdt = p * q
            if usdt > ask_wall:
                ask_wall, ask_px = usdt, p
    return {
        "bid_wall_usdt": round(bid_wall, 0),
        "ask_wall_usdt": round(ask_wall, 0),
        "bid_wall_price": round(bid_px, 8),
        "ask_wall_price": round(ask_px, 8),
    }


def get_recent_liquidations(symbol: str, limit: int = 50) -> list[dict]:
    pair = normalize_pair(symbol)
    rows = _fapi_data("/fapi/v1/allForceOrders", {"symbol": pair, "limit": limit})
    if not isinstance(rows, list):
        return []
    out = []
    for row in rows[-20:]:
        out.append({
            "price": float(row.get("price") or 0),
            "qty": float(row.get("origQty") or 0),
            "side": row.get("side", ""),
        })
    return out


def liquidation_clusters(
    price: float,
    swing_high: float,
    swing_low: float,
    oi_usdt: float,
    recent_liqs: list[dict] | None = None,
) -> dict[str, Any]:
    """Liq clusters from swings + recent force orders + OI density."""
    above_prices = [swing_high]
    below_prices = [swing_low]
    for liq in recent_liqs or []:
        p = liq.get("price", 0)
        if p <= 0:
            continue
        if p > price:
            above_prices.append(p)
        elif p < price:
            below_prices.append(p)

    cluster_above = max(above_prices) if above_prices else price * 1.01
    cluster_below = min(below_prices) if below_prices else price * 0.99
    notional = sum(liq.get("price", 0) * liq.get("qty", 0) for liq in (recent_liqs or []))
    density = "low"
    if oi_usdt >= 500_000_000 or notional >= 50_000_000:
        density = "high"
    elif oi_usdt >= 100_000_000 or notional >= 10_000_000:
        density = "medium"
    return {
        "cluster_above": round(cluster_above, 8),
        "cluster_below": round(cluster_below, 8),
        "density": density,
        "oi_usdt": round(oi_usdt, 0),
        "recent_liq_notional_usdt": round(notional, 0),
    }


def netflow_proxy(taker: float, ls: float, oi_chg: float) -> dict[str, Any]:
    """Proxy exchange flow from taker + OI change (no on-chain data)."""
    bias = "neutral"
    if taker > 1.15 and oi_chg > 2:
        bias = "inflow_accumulation"
    elif taker < 0.85 and oi_chg > 2:
        bias = "inflow_short_build"
    elif taker < 0.85 and oi_chg < -2:
        bias = "outflow_distribution"
    elif ls > 1.8:
        bias = "crowded_long"
    elif ls < 0.6:
        bias = "crowded_short"
    return {"netflow_bias": bias, "oi_change_24h_pct": oi_chg}


def get_derivatives_snapshot(
    symbol: str,
    *,
    swing_high: float = 0,
    swing_low: float = 0,
    price: float = 0,
    funding_signed_pct: float = 0,
    direction: str = "LONG",
) -> dict[str, Any]:
    from app.services.binance_data import binance_data

    pair = normalize_pair(symbol)
    if funding_signed_pct == 0:
        funding_signed_pct = binance_data.get_signed_funding_rate(pair)
    oi_usdt = get_open_interest_usdt(pair)
    oi_chg = get_oi_change_24h_pct(pair)
    ls = get_long_short_ratio(pair)
    taker = get_taker_buy_sell_ratio(pair)
    if price <= 0:
        price = binance_data.get_price(pair)

    funding_regime = "neutral"
    if funding_signed_pct > 0.05:
        funding_regime = "extreme_long"
    elif funding_signed_pct > 0.01:
        funding_regime = "crowded_long"
    elif funding_signed_pct < -0.05:
        funding_regime = "extreme_short"
    elif funding_signed_pct < -0.01:
        funding_regime = "crowded_short"

    cvd = get_cvd_from_klines(pair)
    recent_liqs = get_recent_liquidations(pair)
    liq = liquidation_clusters(
        price, swing_high or price * 1.01, swing_low or price * 0.99, oi_usdt, recent_liqs,
    )
    walls = get_order_book_walls(pair, price)
    flow = netflow_proxy(taker, ls, oi_chg)

    d = direction.upper()
    cvd_confirming = (
        (d == "LONG" and cvd["cvd_trend"] == "rising")
        or (d == "SHORT" and cvd["cvd_trend"] == "falling")
        or cvd["cvd_trend"] == "flat"
    )

    return {
        "open_interest_usdt": oi_usdt,
        "oi_change_24h_pct": oi_chg,
        "funding_pct_8h": round(funding_signed_pct, 4),
        "funding_regime": funding_regime,
        "long_short_ratio": round(ls, 3),
        "taker_buy_sell_ratio": round(taker, 3),
        "liquidation": liq,
        "cvd": cvd["cvd"],
        "cvd_trend": cvd["cvd_trend"],
        "cvd_confirming": cvd_confirming,
        "cvd_bias": cvd["cvd_trend"],
        "order_book": walls,
        "netflow": flow,
    }
