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
