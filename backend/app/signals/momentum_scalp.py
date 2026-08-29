"""1m dip-top scalp — buy the dip, sell the top on fast-moving coins."""

from __future__ import annotations

import pandas as pd

from app.signals.indicators import ensure_ohlcv
from app.signals.schemas import SetupResult, T1_R

SETUP_NAME = "dip_top_scalp"
LOOKBACK = 12
DIP_ZONE = 0.30
TOP_ZONE = 0.70
MIN_RANGE_PCT = 0.20
MIN_FAST_24H_PCT = 2.5
MIN_WICK_RATIO = 0.30


def _range_context(d: pd.DataFrame) -> dict | None:
    if len(d) < LOOKBACK + 2:
        return None
    bar = d.iloc[-1]
    entry = float(bar["close"])
    if entry <= 0:
        return None
    window = d.tail(LOOKBACK)
    rolling_high = float(window["high"].max())
    rolling_low = float(window["low"].min())
    rng = rolling_high - rolling_low
    if rng <= 0:
        return None
    range_pct = rng / entry * 100
    if range_pct < MIN_RANGE_PCT:
        return None
    position = (entry - rolling_low) / rng
    full_range = float(bar["high"]) - float(bar["low"])
    if full_range <= 0:
        return None
    return {
        "entry": entry,
        "bar": bar,
        "rolling_high": rolling_high,
        "rolling_low": rolling_low,
        "range_pct": range_pct,
        "position": position,
        "full_range": full_range,
        "window": window,
    }


def _buy_dip(ctx: dict, change_24h_pct: float) -> SetupResult:
    name = SETUP_NAME
    if ctx["position"] > DIP_ZONE:
        return SetupResult(setup_name=name, fired=False, reason="not in dip zone")
    if abs(change_24h_pct) < MIN_FAST_24H_PCT:
        return SetupResult(setup_name=name, fired=False, reason="24h move too slow")

    bar = ctx["bar"]
    entry = ctx["entry"]
    o, h, l, c = float(bar["open"]), float(bar["high"]), float(bar["low"]), float(bar["close"])
    lower_wick = min(o, c) - l
    wick_ratio = lower_wick / ctx["full_range"]
    green = c > o
    if not green and wick_ratio < MIN_WICK_RATIO:
        return SetupResult(setup_name=name, fired=False, reason="no dip bounce candle")

    stop = ctx["rolling_low"] - entry * 0.0002
    if stop >= entry:
        stop = entry * (1 - 0.0022)
    risk = entry - stop
    if risk <= 0:
        return SetupResult(setup_name=name, fired=False, reason="invalid stop")
    targets = [entry + risk * T1_R, entry + risk * (T1_R + 0.25)]
    dip_pct = (ctx["rolling_high"] - entry) / entry * 100
    return SetupResult(
        setup_name=name,
        fired=True,
        direction="bullish",
        entry=entry,
        stop_loss=stop,
        targets=targets,
        reason=f"BUY DIP · 1m low zone · dipped {dip_pct:.2f}% · 24h {change_24h_pct:+.1f}%",
        sl_basis="1m_dip_low",
        metadata={"scalp_type": "buy_dip", "range_pct": ctx["range_pct"], "volume_confirmed": True},
    )


def _sell_top(ctx: dict, change_24h_pct: float) -> SetupResult:
    name = SETUP_NAME
    if ctx["position"] < TOP_ZONE:
        return SetupResult(setup_name=name, fired=False, reason="not in top zone")
    if abs(change_24h_pct) < MIN_FAST_24H_PCT:
        return SetupResult(setup_name=name, fired=False, reason="24h move too slow")

    bar = ctx["bar"]
    entry = ctx["entry"]
    o, h, l, c = float(bar["open"]), float(bar["high"]), float(bar["low"]), float(bar["close"])
    upper_wick = h - max(o, c)
    wick_ratio = upper_wick / ctx["full_range"]
    red = c < o
    if not red and wick_ratio < MIN_WICK_RATIO:
        return SetupResult(setup_name=name, fired=False, reason="no top rejection candle")

    stop = ctx["rolling_high"] + entry * 0.0002
    if stop <= entry:
        stop = entry * (1 + 0.0022)
    risk = stop - entry
    if risk <= 0:
        return SetupResult(setup_name=name, fired=False, reason="invalid stop")
    targets = [entry - risk * T1_R, entry - risk * (T1_R + 0.25)]
    pump_pct = (entry - ctx["rolling_low"]) / entry * 100
    return SetupResult(
        setup_name=name,
        fired=True,
        direction="bearish",
        entry=entry,
        stop_loss=stop,
        targets=targets,
        reason=f"SELL TOP · 1m high zone · pumped {pump_pct:.2f}% · 24h {change_24h_pct:+.1f}%",
        sl_basis="1m_top_high",
        metadata={"scalp_type": "sell_top", "range_pct": ctx["range_pct"], "volume_confirmed": True},
    )


def dip_top_scalp(df: pd.DataFrame, change_24h_pct: float = 0.0) -> list[SetupResult]:
    """Return 0–2 setups: buy dip (long) and/or sell top (short) on 1m."""
    d = ensure_ohlcv(df)
    ctx = _range_context(d)
    if not ctx:
        return []
    out: list[SetupResult] = []
    buy = _buy_dip(ctx, change_24h_pct)
    if buy.fired:
        out.append(buy)
    sell = _sell_top(ctx, change_24h_pct)
    if sell.fired:
        out.append(sell)
    return out


def momentum_scalp(df: pd.DataFrame, change_24h_pct: float = 0.0) -> SetupResult:
    """Backward-compat — returns first dip/top signal or empty."""
    hits = dip_top_scalp(df, change_24h_pct)
    if hits:
        return hits[0]
    return SetupResult(setup_name=SETUP_NAME, fired=False, reason="no dip/top on 1m")
