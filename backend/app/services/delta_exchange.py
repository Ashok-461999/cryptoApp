"""Delta Exchange India — options chain, Greeks, GEX, max pain (public API)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

_CACHE: dict[str, dict] = {}
_CACHE_AT: dict[str, datetime] = {}
_TTL_SEC = 30

_SYMBOL_MAP = {"BTCUSDT": "BTC", "PAXGUSDT": "GOLD", "ETHUSDT": "ETH", "SOLUSDT": "SOL"}


def _base_url() -> str:
    return get_settings().delta_exchange_base_url.rstrip("/")


def _underlying(symbol: str) -> str | None:
    s = symbol.upper().replace("USDT", "")
    if s in ("BTC", "ETH", "SOL"):
        return s
    return _SYMBOL_MAP.get(symbol.upper())


def pick_atm_straddle(tickers: list[dict], spot: float) -> dict[str, Any] | None:
    """Nearest-expiry ATM call + put for a long straddle on Delta."""
    if not tickers or spot <= 0:
        return None
    expiry = _nearest_expiry(tickers)
    if not expiry:
        return None
    pool = [t for t in tickers if str(t.get("symbol", "")).endswith(f"-{expiry}")]
    strikes = sorted({_f(t.get("strike_price")) for t in pool if _f(t.get("strike_price")) > 0})
    if not strikes:
        return None
    atm = min(strikes, key=lambda k: abs(k - spot))
    call_t = put_t = None
    for t in pool:
        if _f(t.get("strike_price")) != atm:
            continue
        ctype = (t.get("contract_type") or "").lower()
        if "call" in ctype:
            call_t = t
        elif "put" in ctype:
            put_t = t
    if not call_t or not put_t:
        return None
    call_sym = str(call_t.get("symbol") or "")
    put_sym = str(put_t.get("symbol") or "")
    call_prem = _f(call_t.get("mark_price") or call_t.get("close"))
    put_prem = _f(put_t.get("mark_price") or put_t.get("close"))
    return {
        "strategy": "Long Straddle",
        "action": "BUY_BOTH",
        "strike": round(atm, 2),
        "expiry": expiry,
        "spot": round(spot, 2),
        "exchange": "Delta Exchange India",
        "legs": [
            {
                "side": "BUY",
                "type": "CALL",
                "symbol": call_sym,
                "product_id": call_t.get("product_id"),
                "premium": round(call_prem, 2),
                "qty": 1,
            },
            {
                "side": "BUY",
                "type": "PUT",
                "symbol": put_sym,
                "product_id": put_t.get("product_id"),
                "premium": round(put_prem, 2),
                "qty": 1,
            },
        ],
        "total_premium": round(call_prem + put_prem, 2),
        "instruction": f"BUY 1× {call_sym} + BUY 1× {put_sym} (same strike {atm:.0f}, expiry {expiry})",
    }


def _fetch_tickers(underlying: str) -> list[dict]:
    try:
        r = httpx.get(
            f"{_base_url()}/v2/tickers",
            params={
                "underlying_asset_symbols": underlying,
                "contract_types": "call_options,put_options",
            },
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict):
            result = data.get("result")
            return result if isinstance(result, list) else []
        return data if isinstance(data, list) else []
    except Exception:
        logger.debug("Delta tickers failed for %s", underlying)
        return []


def _f(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _nearest_expiry(tickers: list[dict]) -> str | None:
    expiries: set[str] = set()
    for t in tickers:
        sym = t.get("symbol") or ""
        parts = sym.split("-")
        if len(parts) >= 4:
            expiries.add(parts[-1])
    return sorted(expiries)[0] if expiries else None


def _max_pain(calls: list[dict], puts: list[dict], strikes: list[float]) -> float:
    if not strikes:
        return 0.0
    best_strike, best_pain = strikes[0], float("inf")
    for spot in strikes:
        pain = 0.0
        for c in calls:
            k = _f(c.get("strike_price"))
            oi = _f(c.get("oi"))
            if spot > k:
                pain += (spot - k) * oi
        for p in puts:
            k = _f(p.get("strike_price"))
            oi = _f(p.get("oi"))
            if spot < k:
                pain += (k - spot) * oi
        if pain < best_pain:
            best_pain, best_strike = pain, spot
    return best_strike


def _compute_gex(tickers: list[dict], spot: float) -> dict[str, Any]:
    """Net gamma exposure map — dealer hedging magnet zones."""
    by_strike: dict[float, float] = {}
    call_oi: dict[float, float] = {}
    put_oi: dict[float, float] = {}
    iv_samples: list[float] = []

    for t in tickers:
        strike = _f(t.get("strike_price"))
        if strike <= 0:
            continue
        oi = _f(t.get("oi"))
        greeks = t.get("greeks") or {}
        gamma = _f(greeks.get("gamma"))
        iv = _f(t.get("mark_vol"))
        if iv > 0:
            iv_samples.append(iv)
        ctype = (t.get("contract_type") or "").lower()
        sign = 1.0 if "call" in ctype else -1.0
        gex = sign * gamma * oi * spot * spot * 0.01
        by_strike[strike] = by_strike.get(strike, 0.0) + gex
        if "call" in ctype:
            call_oi[strike] = call_oi.get(strike, 0.0) + oi
        else:
            put_oi[strike] = put_oi.get(strike, 0.0) + oi

    strikes = sorted(by_strike.keys())
    net_gex = sum(by_strike.values())
    zero_gamma = spot
    cum = 0.0
    for k in strikes:
        prev = cum
        cum += by_strike[k]
        if prev <= 0 < cum or prev >= 0 > cum:
            zero_gamma = k
            break

    call_wall = max(call_oi, key=call_oi.get) if call_oi else spot
    put_wall = max(put_oi, key=put_oi.get) if put_oi else spot
    mp = _max_pain(
        [t for t in tickers if "call" in (t.get("contract_type") or "").lower()],
        [t for t in tickers if "put" in (t.get("contract_type") or "").lower()],
        strikes,
    )
    iv_pct = round(min(100, max(0, (sum(iv_samples) / len(iv_samples) * 100))) if iv_samples else 50, 1)

    return {
        "zero_gamma": round(zero_gamma, 2),
        "net_gex": round(net_gex, 2),
        "net_gex_sign": "positive" if net_gex >= 0 else "negative",
        "call_wall": round(call_wall, 2),
        "put_wall": round(put_wall, 2),
        "max_pain": round(mp, 2),
        "iv_percentile": iv_pct,
        "spot": round(spot, 2),
        "strikes_tracked": len(strikes),
    }


def _detect_whale_flow(tickers: list[dict], spot: float) -> dict[str, Any]:
    """Large OTM blocks + unusual volume strikes."""
    whales: list[dict] = []
    for t in tickers:
        vol = _f(t.get("volume"))
        oi = _f(t.get("oi"))
        strike = _f(t.get("strike_price"))
        if strike <= 0:
            continue
        otm = abs(strike - spot) / spot > 0.02
        notional = vol * _f(t.get("close") or t.get("mark_price"))
        if otm and (notional >= 500_000 or vol >= 50):
            ctype = t.get("contract_type", "")
            whales.append({
                "symbol": t.get("symbol"),
                "strike": strike,
                "side": "call" if "call" in str(ctype).lower() else "put",
                "volume": vol,
                "notional_usd": round(notional, 0),
            })
    bias = "neutral"
    if whales:
        calls = sum(1 for w in whales if w["side"] == "call")
        puts = sum(1 for w in whales if w["side"] == "put")
        if calls > puts:
            bias = "bullish"
        elif puts > calls:
            bias = "bearish"
    return {"whale_blocks": whales[:5], "flow_bias": bias, "count": len(whales)}


def _fetch_recent_trades(product_id: int, limit: int = 20) -> list[dict]:
    try:
        r = httpx.get(
            f"{_base_url()}/v2/trades/{product_id}",
            params={"page_size": limit},
            timeout=12,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("result") or []
    except Exception:
        return []


def get_options_snapshot(symbol: str) -> dict[str, Any]:
    """GEX / options map for BTC, ETH, SOL (Delta Exchange)."""
    und = _underlying(symbol)
    if not und or und == "GOLD":
        return {"available": False, "reason": "Options on Delta for BTC/ETH/SOL only"}

    cache_key = und
    now = datetime.now(timezone.utc)
    if cache_key in _CACHE:
        at = _CACHE_AT.get(cache_key)
        if at and (now - at).total_seconds() < _TTL_SEC:
            return dict(_CACHE[cache_key])

    tickers = _fetch_tickers(und)
    if not tickers:
        return {"available": False, "reason": "Delta API unavailable"}

    expiry = _nearest_expiry(tickers)
    if expiry:
        tickers = [t for t in tickers if str(t.get("symbol", "")).endswith(expiry)]

    spot = 0.0
    for t in tickers[:5]:
        g = t.get("greeks") or {}
        if g.get("spot"):
            spot = _f(g["spot"])
            break
    if spot <= 0:
        spot = _f(tickers[0].get("mark_price")) if tickers else 0

    gex = _compute_gex(tickers, spot) if spot > 0 else {}
    flow = _detect_whale_flow(tickers, spot)
    atm_straddle = pick_atm_straddle(tickers, spot) if spot > 0 else None
    from app.services.delta_client import delta_client
    if delta_client.is_configured():
        fills = delta_client.get_fills(30)
        for f in fills:
            size = _f(f.get("size"))
            price = _f(f.get("price"))
            if size * price >= 500_000:
                flow["whale_blocks"].append({
                    "symbol": f.get("product_symbol", ""),
                    "strike": _f(f.get("strike_price")),
                    "side": f.get("side", ""),
                    "volume": size,
                    "notional_usd": round(size * price, 0),
                    "source": "account_fills",
                })
    out = {
        "available": True,
        "exchange": "Delta Exchange India",
        "underlying": und,
        "expiry": expiry or "nearest",
        "options": gex,
        "options_flow": flow,
        "atm_straddle": atm_straddle,
        "strategy_hint": _options_strategy_hint(gex, flow),
        "summary": (
            f"Zero γ {gex.get('zero_gamma', 0):.0f} · "
            f"Call wall {gex.get('call_wall', 0):.0f} · Put wall {gex.get('put_wall', 0):.0f} · "
            f"Max pain {gex.get('max_pain', 0):.0f}"
        ) if gex else "",
    }
    _CACHE[cache_key] = out
    _CACHE_AT[cache_key] = now
    return dict(out)


def _options_strategy_hint(gex: dict, flow: dict) -> str:
    iv = gex.get("iv_percentile", 50)
    if iv < 30:
        return "Long Straddle — IV cheap"
    if iv > 80:
        return "Iron Condor — IV expensive"
    if flow.get("flow_bias") == "bullish":
        return "Directional Long Call — whale flow bullish"
    if flow.get("flow_bias") == "bearish":
        return "Directional Long Put — whale flow bearish"
    return "Directional ATM/ITM when sweep + structure align"
