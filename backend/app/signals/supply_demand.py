"""Supply & demand zone retest — rally-base-rally / drop-base-drop."""

from __future__ import annotations

import pandas as pd

from app.signals.indicators import add_standard_indicators, ensure_ohlcv
from app.signals.schemas import SetupResult

ZONE_LOOKBACK = 30
IMPULSE_ATR_MULT = 1.2
BASE_MAX_BARS = 4


def _targets(entry: float, stop: float, multiples: tuple[float, ...] = (4.0, 6.0)) -> list[float]:
    risk = abs(entry - stop)
    if risk <= 0:
        return []
    sign = 1 if entry > stop else -1
    return [entry + sign * risk * m for m in multiples]


def _find_demand_zone(d: pd.DataFrame) -> tuple[float, float] | None:
    """Last down/neutral candle before bullish impulse."""
    atr_val = float(d["atr_14"].iloc[-1]) if not pd.isna(d["atr_14"].iloc[-1]) else 0.0
    if atr_val <= 0:
        return None
    for i in range(len(d) - BASE_MAX_BARS - 4, max(BASE_MAX_BARS, len(d) - ZONE_LOOKBACK), -1):
        base = d.iloc[i - BASE_MAX_BARS : i]
        impulse = d.iloc[i : i + 3]
        if len(base) < 2 or len(impulse) < 2:
            continue
        base_range = float(base["high"].max()) - float(base["low"].min())
        impulse_move = float(impulse["close"].iloc[-1]) - float(base["low"].min())
        if base_range <= atr_val * 0.8 and impulse_move >= atr_val * IMPULSE_ATR_MULT:
            zone_top = float(base["high"].max())
            zone_bot = float(base["low"].min())
            return zone_bot, zone_top
    return None


def _find_supply_zone(d: pd.DataFrame) -> tuple[float, float] | None:
    atr_val = float(d["atr_14"].iloc[-1]) if not pd.isna(d["atr_14"].iloc[-1]) else 0.0
    if atr_val <= 0:
        return None
    for i in range(len(d) - BASE_MAX_BARS - 4, max(BASE_MAX_BARS, len(d) - ZONE_LOOKBACK), -1):
        base = d.iloc[i - BASE_MAX_BARS : i]
        impulse = d.iloc[i : i + 3]
        if len(base) < 2 or len(impulse) < 2:
            continue
        base_range = float(base["high"].max()) - float(base["low"].min())
        impulse_move = float(base["high"].max()) - float(impulse["close"].iloc[-1])
        if base_range <= atr_val * 0.8 and impulse_move >= atr_val * IMPULSE_ATR_MULT:
            zone_top = float(base["high"].max())
            zone_bot = float(base["low"].min())
            return zone_bot, zone_top
    return None


def supply_demand(df: pd.DataFrame) -> SetupResult:
    name = "supply_demand"
    if len(df) < ZONE_LOOKBACK + 5:
        return SetupResult(setup_name=name, fired=False, reason="insufficient bars")

    d = add_standard_indicators(ensure_ohlcv(df))
    bar = d.iloc[-1]
    prev = d.iloc[-2]
    atr_val = float(bar["atr_14"]) if not pd.isna(bar["atr_14"]) else 0.0
    vol_ok = float(bar["volume"]) > float(d["volume"].tail(20).mean()) * 1.1

    demand = _find_demand_zone(d.iloc[:-1])
    if demand:
        zone_bot, zone_top = demand
        touched = float(bar["low"]) <= zone_top and float(prev["low"]) <= zone_top
        rejected = float(bar["close"]) > zone_top and float(bar["close"]) > float(bar["open"])
        if touched and rejected and vol_ok:
            entry = float(bar["close"])
            stop = zone_bot - atr_val * 0.1
            return SetupResult(
                setup_name=name,
                fired=True,
                direction="bullish",
                entry=entry,
                stop_loss=stop,
                targets=_targets(entry, stop),
                reason="demand zone retest — buy from base",
                sl_basis="demand_zone",
                metadata={"zone_type": "demand", "volume_confirmed": vol_ok},
            )

    supply = _find_supply_zone(d.iloc[:-1])
    if supply:
        zone_bot, zone_top = supply
        touched = float(bar["high"]) >= zone_bot and float(prev["high"]) >= zone_bot
        rejected = float(bar["close"]) < zone_bot and float(bar["close"]) < float(bar["open"])
        if touched and rejected and vol_ok:
            entry = float(bar["close"])
            stop = zone_top + atr_val * 0.1
            return SetupResult(
                setup_name=name,
                fired=True,
                direction="bearish",
                entry=entry,
                stop_loss=stop,
                targets=_targets(entry, stop),
                reason="supply zone retest — sell from base",
                sl_basis="supply_zone",
                metadata={"zone_type": "supply", "volume_confirmed": vol_ok},
            )

    return SetupResult(setup_name=name, fired=False, reason="no supply/demand retest")
