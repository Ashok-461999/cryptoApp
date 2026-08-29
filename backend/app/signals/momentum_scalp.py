"""1m dip-top scalp — BUY the dip (long), SELL the top (short). Never chase."""

from __future__ import annotations

import pandas as pd

from app.signals.indicators import ensure_ohlcv
from app.signals.schemas import SetupResult, T1_R

SETUP_NAME = "dip_top_scalp"
LOOKBACK = 12
DIP_ZONE = 0.32  # bottom 32% = buy dip zone
TOP_ZONE = 0.68  # top 32% = sell top zone
MIN_RANGE_PCT = 0.22
MIN_FAST_24H_PCT = 2.5
MIN_WICK_RATIO = 0.32
# Reject buy when price is still at highs / sell when still at lows (anti chase)
MIN_OPPOSITE_RANGE_PCT = 0.25  # must be away from opposite end of range


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
        return SetupResult(setup_name=name, fired=False, reason="not in dip zone — won't buy top")
    dist_from_high_pct = (ctx["rolling_high"] - ctx["entry"]) / ctx["entry"] * 100
    if dist_from_high_pct < MIN_OPPOSITE_RANGE_PCT:
        return SetupResult(setup_name=name, fired=False, reason="too close to range high — not a dip")
    if abs(change_24h_pct) < MIN_FAST_24H_PCT:
        return SetupResult(setup_name=name, fired=False, reason="24h move too slow")

    bar = ctx["bar"]
    entry = ctx["entry"]
    o, h, l, c = float(bar["open"]), float(bar["high"]), float(bar["low"]), float(bar["close"])
    lower_wick = min(o, c) - l
    wick_ratio = lower_wick / ctx["full_range"]
    close_pos = (c - l) / ctx["full_range"]
    green = c > o
    # Bounce off lows: green candle or hammer + close not stuck at bottom
    if not ((green and close_pos >= 0.40) or wick_ratio >= MIN_WICK_RATIO):
        return SetupResult(setup_name=name, fired=False, reason="no dip bounce — wait for rejection")

    stop = min(ctx["rolling_low"], l) - entry * 0.0003
    if stop >= entry:
        stop = entry * (1 - 0.0025)
    risk = entry - stop
    if risk <= 0:
        return SetupResult(setup_name=name, fired=False, reason="invalid stop")
    targets = [entry + risk * T1_R, entry + risk * (T1_R + 0.5)]
    dip_pct = (ctx["rolling_high"] - entry) / entry * 100
    return SetupResult(
        setup_name=name,
        fired=True,
        direction="bullish",
        entry=entry,
        stop_loss=stop,
        targets=targets,
        reason=f"BUY DIP · long at range low ({ctx['position']*100:.0f}%) · dipped {dip_pct:.2f}%",
        sl_basis="below_1m_swing_low",
        metadata={"scalp_type": "buy_dip", "range_pct": ctx["range_pct"], "zone": ctx["position"]},
    )


def _sell_top(ctx: dict, change_24h_pct: float) -> SetupResult:
    name = SETUP_NAME
    if ctx["position"] < TOP_ZONE:
        return SetupResult(setup_name=name, fired=False, reason="not in top zone — won't sell dip")
    dist_from_low_pct = (ctx["entry"] - ctx["rolling_low"]) / ctx["entry"] * 100
    if dist_from_low_pct < MIN_OPPOSITE_RANGE_PCT:
        return SetupResult(setup_name=name, fired=False, reason="too close to range low — not a top")
    if abs(change_24h_pct) < MIN_FAST_24H_PCT:
        return SetupResult(setup_name=name, fired=False, reason="24h move too slow")

    bar = ctx["bar"]
    entry = ctx["entry"]
    o, h, l, c = float(bar["open"]), float(bar["high"]), float(bar["low"]), float(bar["close"])
    upper_wick = h - max(o, c)
    wick_ratio = upper_wick / ctx["full_range"]
    close_pos = (c - l) / ctx["full_range"]
    red = c < o
    if not ((red and close_pos <= 0.60) or wick_ratio >= MIN_WICK_RATIO):
        return SetupResult(setup_name=name, fired=False, reason="no top rejection — wait for fade")

    stop = max(ctx["rolling_high"], h) + entry * 0.0003
    if stop <= entry:
        stop = entry * (1 + 0.0025)
    risk = stop - entry
    if risk <= 0:
        return SetupResult(setup_name=name, fired=False, reason="invalid stop")
    targets = [entry - risk * T1_R, entry - risk * (T1_R + 0.5)]
    pump_pct = (entry - ctx["rolling_low"]) / entry * 100
    return SetupResult(
        setup_name=name,
        fired=True,
        direction="bearish",
        entry=entry,
        stop_loss=stop,
        targets=targets,
        reason=f"SELL TOP · short at range high ({ctx['position']*100:.0f}%) · pumped {pump_pct:.2f}%",
        sl_basis="above_1m_swing_high",
        metadata={"scalp_type": "sell_top", "range_pct": ctx["range_pct"], "zone": ctx["position"]},
    )


def dip_top_scalp(df: pd.DataFrame, change_24h_pct: float = 0.0) -> list[SetupResult]:
    """Return 0–1 setup: buy dip OR sell top on 1m (never both, never chase)."""
    d = ensure_ohlcv(df)
    ctx = _range_context(d)
    if not ctx:
        return []
    buy = _buy_dip(ctx, change_24h_pct)
    sell = _sell_top(ctx, change_24h_pct)
    if buy.fired and not sell.fired:
        return [buy]
    if sell.fired and not buy.fired:
        return [sell]
    return []


def momentum_scalp(df: pd.DataFrame, change_24h_pct: float = 0.0) -> SetupResult:
    """Backward-compat — returns first dip/top signal or empty."""
    hits = dip_top_scalp(df, change_24h_pct)
    if hits:
        return hits[0]
    return SetupResult(setup_name=SETUP_NAME, fired=False, reason="no dip/top on 1m")
