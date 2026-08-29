"""Validated SL/TP for 1m buy-dip / sell-top scalps."""

from __future__ import annotations

from app.config import Settings, get_settings
from app.services.trading_fees import tp_price_from_rr


def validate_scalp_levels(entry: float, stop: float, tp: float, direction: str) -> bool:
    """LONG: SL below entry, TP above. SHORT: SL above entry, TP below."""
    if entry <= 0 or stop <= 0 or tp <= 0:
        return False
    d = direction.upper()
    if d == "LONG":
        return stop < entry < tp
    if d == "SHORT":
        return tp < entry < stop
    return False


def build_scalp_targets(
    entry: float,
    stop: float,
    direction: str,
    rr: float,
    notional_usdt: float,
    settings: Settings | None = None,
) -> tuple[float, float, float, float] | None:
    """1:1 / 1:2 targets from SL distance — never inverted."""
    d = direction.upper()
    risk = abs(entry - stop)
    if risk <= 0 or entry <= 0:
        return None
    if d == "LONG" and stop >= entry:
        return None
    if d == "SHORT" and stop <= entry:
        return None

    sign = 1 if d == "LONG" else -1
    t1, t2, tp_gross, tp_net = tp_price_from_rr(entry, stop, sign, rr, notional_usdt, settings)
    if not validate_scalp_levels(entry, stop, t1, d):
        t1 = entry + sign * risk * rr
        t2 = entry + sign * risk * rr * 1.08
    if not validate_scalp_levels(entry, stop, t1, d):
        return None
    return t1, t2, tp_gross, tp_net
