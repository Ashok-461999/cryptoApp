"""Structure reversal — CHoCH after liquidity sweep (no lagging EMA)."""

import pandas as pd

from app.signals.indicators import add_standard_indicators, ensure_ohlcv
from app.signals.schemas import SetupResult

SWING = 10


def _targets_scalp(entry: float, stop: float) -> list[float]:
    risk = abs(entry - stop)
    if risk <= 0:
        return []
    sign = 1 if entry > stop else -1
    return [entry + sign * risk * 4.0, entry + sign * risk * 6.0]


def structure_reversal(df: pd.DataFrame) -> SetupResult:
    """
  CHoCH reversal scalp:
  - Price sweeps prior swing high/low (stop hunt)
  - Closes back with displacement (body > 60% of range)
  - Breaks prior micro structure in reversal direction
  """
    name = "structure_reversal"
    if len(df) < SWING + 8:
        return SetupResult(setup_name=name, fired=False, reason="insufficient bars")

    d = add_standard_indicators(ensure_ohlcv(df))
    bar = d.iloc[-1]
    prev = d.iloc[-2]
    window = d.iloc[-(SWING + 2) : -2]
    swing_high = float(window["high"].max())
    swing_low = float(window["low"].min())

    body = abs(float(bar["close"]) - float(bar["open"]))
    full_range = float(bar["high"]) - float(bar["low"])
    if full_range <= 0:
        return SetupResult(setup_name=name, fired=False, reason="flat bar")

    displacement = body / full_range >= 0.55
    vol_ok = bar["volume"] > bar.get("vol_sma_20", bar["volume"]) * 1.2

    # Bearish reversal: sweep highs, displacement down, break prev low
    if (
        float(bar["high"]) > swing_high
        and float(bar["close"]) < swing_high
        and float(bar["close"]) < float(prev["low"])
        and displacement
        and vol_ok
    ):
        entry = float(bar["close"])
        stop = float(bar["high"]) + full_range * 0.1
        return SetupResult(
            setup_name=name, fired=True, direction="bearish",
            entry=entry, stop_loss=stop,
            targets=_targets_scalp(entry, stop),
            reason="bearish CHoCH — sweep + structure break down",
            sl_basis="sweep_high",
            metadata={"displacement": True, "structure_break": True, "volume_confirmed": vol_ok},
        )

    # Bullish reversal: sweep lows, displacement up, break prev high
    if (
        float(bar["low"]) < swing_low
        and float(bar["close"]) > swing_low
        and float(bar["close"]) > float(prev["high"])
        and displacement
        and vol_ok
    ):
        entry = float(bar["close"])
        stop = float(bar["low"]) - full_range * 0.1
        return SetupResult(
            setup_name=name, fired=True, direction="bullish",
            entry=entry, stop_loss=stop,
            targets=_targets_scalp(entry, stop),
            reason="bullish CHoCH — sweep + structure break up",
            sl_basis="sweep_low",
            metadata={"displacement": True, "structure_break": True, "volume_confirmed": vol_ok},
        )

    return SetupResult(setup_name=name, fired=False, reason="no structure reversal")
