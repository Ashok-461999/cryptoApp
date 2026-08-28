"""Fibonacci golden-pocket retest — structure-aligned scalp."""

import pandas as pd

from app.signals.indicators import add_standard_indicators, ensure_ohlcv
from app.signals.schemas import SetupResult

SWING_LOOKBACK = 48
FIB_GOLDEN = 0.618
FIB_MID = 0.5


def _targets(entry: float, stop: float, multiples: tuple[float, ...] = (4.0, 6.0)) -> list[float]:
    risk = abs(entry - stop)
    if risk <= 0:
        return []
    sign = 1 if entry > stop else -1
    return [entry + sign * risk * m for m in multiples]


def fibonacci_retrace(df: pd.DataFrame) -> SetupResult:
    """Golden pocket (0.618) retest after clear impulse leg — trend-following only."""
    name = "fibonacci_retrace"
    if len(df) < SWING_LOOKBACK + 5:
        return SetupResult(setup_name=name, fired=False, reason="insufficient bars")

    d = add_standard_indicators(ensure_ohlcv(df))
    window = d.iloc[-SWING_LOOKBACK:]
    bar = d.iloc[-1]
    prev = d.iloc[-2]

    swing_high = float(window["high"].max())
    swing_low = float(window["low"].min())
    rng = swing_high - swing_low
    if rng <= 0:
        return SetupResult(setup_name=name, fired=False, reason="no swing range")

    high_idx = int(window["high"].values.argmax())
    low_idx = int(window["low"].values.argmin())
    tol = rng * 0.01
    vol_ok = float(bar["volume"]) > float(window["volume"].mean()) * 1.15

    impulse_up = low_idx < high_idx
    fib_618 = swing_high - rng * FIB_GOLDEN
    fib_50 = swing_high - rng * FIB_MID
    touched_fib = (
        float(prev["low"]) <= fib_618 + tol
        and float(bar["low"]) <= fib_618 + tol
        and float(bar["close"]) > fib_50
        and float(bar["close"]) > float(bar["open"])
        and float(bar["close"]) > float(prev["close"])
    )

    if impulse_up and touched_fib and vol_ok:
        entry = float(bar["close"])
        stop = min(float(bar["low"]), swing_low) - float(bar["atr_14"] or 0) * 0.1
        return SetupResult(
            setup_name=name,
            fired=True,
            direction="bullish",
            entry=entry,
            stop_loss=stop,
            targets=_targets(entry, stop),
            reason="fib 0.618 golden pocket bounce (bullish impulse)",
            sl_basis="fib_swing_low",
            metadata={
                "fib_618": fib_618,
                "volume_confirmed": vol_ok,
                "impulse": "up",
            },
        )

    impulse_down = high_idx < low_idx
    fib_618_bear = swing_low + rng * FIB_GOLDEN
    fib_50_bear = swing_low + rng * FIB_MID
    touched_fib_bear = (
        float(prev["high"]) >= fib_618_bear - tol
        and float(bar["high"]) >= fib_618_bear - tol
        and float(bar["close"]) < fib_50_bear
        and float(bar["close"]) < float(bar["open"])
        and float(bar["close"]) < float(prev["close"])
    )

    if impulse_down and touched_fib_bear and vol_ok:
        entry = float(bar["close"])
        stop = max(float(bar["high"]), swing_high) + float(bar["atr_14"] or 0) * 0.1
        return SetupResult(
            setup_name=name,
            fired=True,
            direction="bearish",
            entry=entry,
            stop_loss=stop,
            targets=_targets(entry, stop),
            reason="fib 0.618 golden pocket rejection (bearish impulse)",
            sl_basis="fib_swing_high",
            metadata={
                "fib_618": fib_618_bear,
                "volume_confirmed": vol_ok,
                "impulse": "down",
            },
        )

    return SetupResult(setup_name=name, fired=False, reason="no fib retest at golden pocket")
