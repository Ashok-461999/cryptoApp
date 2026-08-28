"""Order flow scalp — delta shift + absorption after liquidity event."""

from __future__ import annotations

import pandas as pd

from app.signals.indicators import add_standard_indicators, ensure_ohlcv
from app.signals.market_structure import swing_high_low
from app.signals.schemas import SetupResult

DELTA_LOOKBACK = 5


def _targets(entry: float, stop: float, multiples: tuple[float, ...] = (4.0, 6.0)) -> list[float]:
    risk = abs(entry - stop)
    if risk <= 0:
        return []
    sign = 1 if entry > stop else -1
    return [entry + sign * risk * m for m in multiples]


def _bar_delta(row: pd.Series) -> float:
    o, c, v = float(row["open"]), float(row["close"]), float(row["volume"])
    if c > o:
        return v
    if c < o:
        return -v
    return 0.0


def _cumulative_delta(d: pd.DataFrame, n: int = DELTA_LOOKBACK) -> float:
    return sum(_bar_delta(d.iloc[i]) for i in range(len(d) - n, len(d)))


def _delta_flip(d: pd.DataFrame) -> str | None:
    """Recent bars show aggressive buying or selling pressure."""
    if len(d) < DELTA_LOOKBACK + 2:
        return None
    recent = _cumulative_delta(d)
    prior = sum(_bar_delta(d.iloc[i]) for i in range(len(d) - DELTA_LOOKBACK * 2, len(d) - DELTA_LOOKBACK))
    bar = d.iloc[-1]
    body_pct = abs(float(bar["close"]) - float(bar["open"])) / max(
        float(bar["high"]) - float(bar["low"]), 1e-9
    )
    vol_spike = float(bar["volume"]) > float(d["volume"].tail(20).mean()) * 1.3
    if recent > 0 and recent > abs(prior) * 1.2 and body_pct >= 0.4 and vol_spike:
        return "bullish"
    if recent < 0 and abs(recent) > abs(prior) * 1.2 and body_pct >= 0.4 and vol_spike:
        return "bearish"
    return None


def _absorption(d: pd.DataFrame) -> str | None:
    """High volume, small body — absorption at level."""
    bar = d.iloc[-1]
    full_range = float(bar["high"]) - float(bar["low"])
    if full_range <= 0:
        return None
    body_pct = abs(float(bar["close"]) - float(bar["open"])) / full_range
    vol_spike = float(bar["volume"]) > float(d["volume"].tail(20).mean()) * 1.5
    if not vol_spike or body_pct > 0.35:
        return None
    lower_wick = min(float(bar["open"]), float(bar["close"])) - float(bar["low"])
    upper_wick = float(bar["high"]) - max(float(bar["open"]), float(bar["close"]))
    if lower_wick / full_range >= 0.5:
        return "bullish"
    if upper_wick / full_range >= 0.5:
        return "bearish"
    return None


def order_flow(df: pd.DataFrame) -> SetupResult:
    """
    Order flow entry after liquidity sweep:
    - Sweep of swing high/low
    - Delta flip or absorption confirms institutional response
    """
    name = "order_flow"
    if len(df) < 25:
        return SetupResult(setup_name=name, fired=False, reason="insufficient bars")

    d = add_standard_indicators(ensure_ohlcv(df))
    bar = d.iloc[-1]
    prev = d.iloc[-2]
    swing_high, swing_low = swing_high_low(d)
    atr_val = float(bar["atr_14"]) if not pd.isna(bar["atr_14"]) else 0.0

    flow = _delta_flip(d) or _absorption(d)
    if not flow:
        return SetupResult(setup_name=name, fired=False, reason="no order flow shift")

    meta = {"volume_confirmed": True, "order_flow": flow}

    if (
        flow == "bullish"
        and float(bar["low"]) < swing_low
        and float(bar["close"]) > swing_low
        and float(bar["close"]) > float(prev["high"])
    ):
        entry = float(bar["close"])
        stop = min(float(bar["low"]), swing_low) - max(atr_val * 0.35, entry * 0.006)
        return SetupResult(
            setup_name=name,
            fired=True,
            direction="bullish",
            entry=entry,
            stop_loss=stop,
            targets=_targets(entry, stop),
            reason="order flow buy — sweep lows + delta/absorption",
            sl_basis="order_flow_low",
            metadata={**meta, "structure_break": True, "displacement": True},
        )

    if (
        flow == "bearish"
        and float(bar["high"]) > swing_high
        and float(bar["close"]) < swing_high
        and float(bar["close"]) < float(prev["low"])
    ):
        entry = float(bar["close"])
        stop = max(float(bar["high"]), swing_high) + max(atr_val * 0.35, entry * 0.006)
        return SetupResult(
            setup_name=name,
            fired=True,
            direction="bearish",
            entry=entry,
            stop_loss=stop,
            targets=_targets(entry, stop),
            reason="order flow sell — sweep highs + delta/absorption",
            sl_basis="order_flow_high",
            metadata={**meta, "structure_break": True, "displacement": True},
        )

    return SetupResult(setup_name=name, fired=False, reason="no order flow at liquidity")
