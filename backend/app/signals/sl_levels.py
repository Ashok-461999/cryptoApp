"""Structure-based stop loss — avoid stops too close to entry."""

from __future__ import annotations

SL_MIN_PCT = 0.85
SL_MAX_PCT_MAJORS = 2.2
SL_MAX_PCT_MEME = 3.5
ATR_BUFFER = 0.5


def normalize_stop_loss(
    entry: float,
    direction: str,
    proposed_stop: float,
    bar_low: float,
    bar_high: float,
    swing_low: float,
    swing_high: float,
    atr: float,
    *,
    tier: str = "C",
) -> float:
    """
    Widen tight stops to structure + ATR buffer.
    LONG: stop below min(bar low, swing low) with min 0.6% from entry.
    """
    if entry <= 0 or proposed_stop <= 0:
        return proposed_stop

    atr = atr if atr and atr > 0 else entry * 0.008
    min_dist = max(atr * ATR_BUFFER, entry * SL_MIN_PCT / 100)
    max_pct = SL_MAX_PCT_MEME if tier == "D" else SL_MAX_PCT_MAJORS
    max_dist = entry * max_pct / 100

    bull = direction in ("bullish", "LONG", "long")

    if bull:
        structural = min(proposed_stop, bar_low, swing_low) - atr * 0.15
        widest = entry - min_dist
        stop = min(structural, widest)
        floor = entry - max_dist
        return max(stop, floor)

    structural = max(proposed_stop, bar_high, swing_high) + atr * 0.15
    widest = entry + min_dist
    stop = max(structural, widest)
    ceiling = entry + max_dist
    return min(stop, ceiling)
