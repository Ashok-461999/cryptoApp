"""Market structure helpers — swings, BOS/CHoCH, structure+fib+sweep confluence."""

from __future__ import annotations

import pandas as pd

from app.signals.fibonacci import SWING_LOOKBACK
from app.signals.indicators import add_standard_indicators, ensure_ohlcv
from app.signals.schemas import SetupResult

SWING = 14
FIB_GOLDEN = 0.618


def _targets(entry: float, stop: float, multiples: tuple[float, ...] = (4.0, 6.0)) -> list[float]:
    risk = abs(entry - stop)
    if risk <= 0:
        return []
    sign = 1 if entry > stop else -1
    return [entry + sign * risk * m for m in multiples]


def swing_high_low(df: pd.DataFrame, lookback: int = SWING) -> tuple[float, float]:
    window = df.iloc[-(lookback + 1) : -1]
    return float(window["high"].max()), float(window["low"].min())


def structure_fib_sweep(df: pd.DataFrame) -> SetupResult:
    """
    High-confluence scalp: liquidity sweep + golden fib pocket + CHoCH.
    All three must align on the same 5m bar.
    """
    name = "structure_fib_sweep"
    if len(df) < SWING_LOOKBACK + 5:
        return SetupResult(setup_name=name, fired=False, reason="insufficient bars")

    d = add_standard_indicators(ensure_ohlcv(df))
    bar = d.iloc[-1]
    prev = d.iloc[-2]
    swing_high, swing_low = swing_high_low(d, SWING)
    window = d.iloc[-SWING_LOOKBACK:]
    leg_high = float(window["high"].max())
    leg_low = float(window["low"].min())
    rng = leg_high - leg_low
    if rng <= 0:
        return SetupResult(setup_name=name, fired=False, reason="no swing leg")

    body = abs(float(bar["close"]) - float(bar["open"]))
    full_range = float(bar["high"]) - float(bar["low"])
    if full_range <= 0:
        return SetupResult(setup_name=name, fired=False, reason="flat bar")

    displacement = body / full_range >= 0.45
    vol_ok = float(bar["volume"]) > float(window["volume"].mean()) * 1.2
    if not displacement or not vol_ok:
        return SetupResult(setup_name=name, fired=False, reason="no impulse after sweep")

    fib_tol = rng * 0.012
    meta = {
        "displacement": True,
        "volume_confirmed": vol_ok,
        "structure_break": True,
        "confluence": ["liquidity_sweep", "fibonacci", "market_structure"],
    }

    fib_bull = leg_high - rng * FIB_GOLDEN
    swept_low = float(bar["low"]) < swing_low and float(prev["low"]) >= swing_low
    fib_touch_bull = float(bar["low"]) <= fib_bull + fib_tol
    choch_up = float(bar["close"]) > float(prev["high"])
    if swept_low and fib_touch_bull and choch_up and float(bar["close"]) > float(bar["open"]):
        entry = float(bar["close"])
        stop = min(float(bar["low"]), swing_low) - float(bar["atr_14"] or 0) * 0.1
        return SetupResult(
            setup_name=name,
            fired=True,
            direction="bullish",
            entry=entry,
            stop_loss=stop,
            targets=_targets(entry, stop),
            reason="sweep lows + fib 0.618 + CHoCH up",
            sl_basis="sweep_low_fib",
            metadata=meta,
        )

    fib_bear = leg_low + rng * FIB_GOLDEN
    swept_high = float(bar["high"]) > swing_high and float(prev["high"]) <= swing_high
    fib_touch_bear = float(bar["high"]) >= fib_bear - fib_tol
    choch_down = float(bar["close"]) < float(prev["low"])
    if swept_high and fib_touch_bear and choch_down and float(bar["close"]) < float(bar["open"]):
        entry = float(bar["close"])
        stop = max(float(bar["high"]), swing_high) + float(bar["atr_14"] or 0) * 0.1
        return SetupResult(
            setup_name=name,
            fired=True,
            direction="bearish",
            entry=entry,
            stop_loss=stop,
            targets=_targets(entry, stop),
            reason="sweep highs + fib 0.618 + CHoCH down",
            sl_basis="sweep_high_fib",
            metadata=meta,
        )

    return SetupResult(setup_name=name, fired=False, reason="no structure+fib+sweep confluence")
