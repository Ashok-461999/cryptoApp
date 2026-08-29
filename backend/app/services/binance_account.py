"""Binance Futures balance & PnL for the app UI."""

from __future__ import annotations

from app.services.binance_trading_client import binance_trading
from app.services.trade_executor import is_auto_trade_enabled


def fetch_binance_ui() -> dict | None:
    """Return live Binance wallet/PnL when API keys are configured."""
    if not binance_trading.is_configured():
        return None
    try:
        if not binance_trading.ping():
            return None
        summary = binance_trading.get_wallet_summary()
        summary["source"] = "binance_futures"
        summary["auto_execute"] = is_auto_trade_enabled()
        return summary
    except Exception:
        return None
