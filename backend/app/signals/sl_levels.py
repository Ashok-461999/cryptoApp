"""Structure-based stop loss — avoid stops too close to entry."""

from __future__ import annotations

SL_MIN_PCT = 0.85
SL_MIN_PCT_SCALP = 0.22  # tight scalp — keep SL near 1m swing
SL_MAX_PCT_MAJORS = 2.2
SL_MAX_PCT_MEME = 3.5
SL_MAX_PCT_SCALP = 0.60
ATR_BUFFER = 0.5
ATR_BUFFER_SCALP = 0.12


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
    scalp_tight: bool = False,
) -> float:
    """
    Widen tight stops to structure + ATR buffer.
    scalp_tight=True keeps SL very near 1m swing for quick in/out.
    """
    if entry <= 0 or proposed_stop <= 0:
        return proposed_stop

    atr = atr if atr and atr > 0 else entry * 0.008
    min_pct = SL_MIN_PCT_SCALP if scalp_tight else SL_MIN_PCT
    atr_buf = ATR_BUFFER_SCALP if scalp_tight else ATR_BUFFER
    min_dist = max(atr * atr_buf, entry * min_pct / 100)
    if scalp_tight:
        max_pct = SL_MAX_PCT_SCALP
    else:
        max_pct = SL_MAX_PCT_MEME if tier == "D" else SL_MAX_PCT_MAJORS
    max_dist = entry * max_pct / 100

    bull = direction in ("bullish", "LONG", "long")
    struct_pad = atr * (0.05 if scalp_tight else 0.15)

    if bull:
        structural = min(proposed_stop, bar_low) - struct_pad
        if not scalp_tight:
            structural = min(structural, swing_low) - struct_pad
        widest = entry - min_dist
        stop = min(structural, widest)
        floor = entry - max_dist
        return max(stop, floor)

    structural = max(proposed_stop, bar_high) + struct_pad
    if not scalp_tight:
        structural = max(structural, swing_high) + struct_pad
    widest = entry + min_dist
    stop = max(structural, widest)
    ceiling = entry + max_dist
    return min(stop, ceiling)
