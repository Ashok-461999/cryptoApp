"""Binance Futures fee estimates for scalp PnL (net after round-trip taker fees)."""

from __future__ import annotations

from app.config import Settings, get_settings


def taker_fee_rate(settings: Settings | None = None) -> float:
    """Per-side taker fee as a fraction (0.0004 = 0.04%)."""
    s = settings or get_settings()
    return s.binance_taker_fee_pct / 100.0


def round_trip_fee_usdt(notional_usdt: float, settings: Settings | None = None) -> float:
    """Entry + exit taker fees on notional."""
    if notional_usdt <= 0:
        return 0.0
    rate = taker_fee_rate(settings)
    return notional_usdt * rate * 2.0


def gross_tp_for_net_profit(
    net_profit_usdt: float,
    notional_usdt: float,
    settings: Settings | None = None,
) -> float:
    """Gross price-move profit needed so net (after fees) ≈ target."""
    s = settings or get_settings()
    fees = round_trip_fee_usdt(notional_usdt, s)
    return max(net_profit_usdt + fees + s.fee_buffer_usdt, net_profit_usdt)


def net_profit_after_fees(gross_profit_usdt: float, notional_usdt: float, settings: Settings | None = None) -> float:
    return max(0.0, gross_profit_usdt - round_trip_fee_usdt(notional_usdt, settings))


def passes_fee_gate(tp_net_usdt: float, notional_usdt: float, settings: Settings | None = None) -> bool:
    """Reject scalps where round-trip fees eat the edge."""
    s = settings or get_settings()
    fees = round_trip_fee_usdt(notional_usdt, s) + estimated_entry_drag_usdt(notional_usdt, s)
    if tp_net_usdt <= 0:
        return False
    return tp_net_usdt >= fees * s.min_net_profit_to_fee_ratio


def estimated_entry_drag_usdt(notional_usdt: float, settings: Settings | None = None) -> float:
    """One-side taker fee + slippage drag seen on market fills (e.g. -0.09 on ~$21)."""
    if notional_usdt <= 0:
        return 0.0
    s = settings or get_settings()
    fee = notional_usdt * taker_fee_rate(s)
    slip = notional_usdt * (s.slippage_pct / 100.0)
    return fee + slip + s.fee_buffer_usdt


def tp_price_from_rr(
    entry: float,
    stop: float,
    direction_sign: int,
    rr: float,
    notional_usdt: float,
    settings: Settings | None = None,
) -> tuple[float, float, float, float]:
    """Return (t1, t2, tp_gross_usdt, tp_net_usdt) using SL-distance R:R + fee cushion."""
    s = settings or get_settings()
    risk_dist = abs(entry - stop)
    if risk_dist <= 0 or entry <= 0:
        return entry, entry, 0.0, 0.0
    fees = round_trip_fee_usdt(notional_usdt, s)
    drag = estimated_entry_drag_usdt(notional_usdt, s)
    cost_dist = (fees + drag) / notional_usdt * entry if notional_usdt > 0 else 0.0
    t1 = entry + direction_sign * (risk_dist * rr + cost_dist)
    t2 = entry + direction_sign * (risk_dist * rr * 1.08 + cost_dist)
    stop_frac = risk_dist / entry
    tp_gross = notional_usdt * stop_frac * rr if notional_usdt > 0 else 0.0
    tp_net = max(0.0, tp_gross - fees - drag)
    return t1, t2, tp_gross, tp_net
