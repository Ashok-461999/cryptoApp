"""Binance Futures balance & PnL for the app UI."""

from __future__ import annotations

from app.config import Settings, get_settings
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


def get_live_capital_usdt(settings: Settings | None = None) -> float:
    """Use real Binance equity for sizing — never the ₹20k reference capital."""
    s = settings or get_settings()
    ui = fetch_binance_ui()
    if ui and float(ui.get("equity_usdt") or 0) > 0:
        return float(ui["equity_usdt"])
    return s.crypto_capital_usdt


def get_available_usdt(settings: Settings | None = None) -> float:
    s = settings or get_settings()
    if binance_trading.is_configured():
        try:
            bal = binance_trading.get_usdt_balance()
            if bal > 0:
                return bal
        except Exception:
            pass
    return get_live_capital_usdt(s)


def fixed_risk_usdt(settings: Settings | None = None) -> float:
    """Fixed max loss at SL in USDT ($0.5–$0.75 band)."""
    s = settings or get_settings()
    return min(s.risk_per_trade_usdt, s.risk_per_trade_usdt_max)


def target_profit_usdt(settings: Settings | None = None) -> float:
    s = settings or get_settings()
    return min(max(s.take_profit_usdt, s.take_profit_usdt_min), s.take_profit_usdt_max)


def per_trade_deploy_pct(capital_usdt: float, settings: Settings | None = None) -> float:
    """Smaller wallets — smaller % per trade to avoid blowing the account."""
    s = settings or get_settings()
    if capital_usdt < 60:
        return min(s.max_deploy_pct, 18.0)
    if capital_usdt < 120:
        return min(s.max_deploy_pct, 18.0)
    return s.max_deploy_pct


def max_leverage_for_capital(capital_usdt: float, settings: Settings | None = None) -> int:
    s = settings or get_settings()
    if capital_usdt < 60:
        return min(s.leverage_max, 8)
    if capital_usdt < 120:
        return min(s.leverage_max, 10)
    if capital_usdt < 250:
        return min(s.leverage_max, 15)
    return s.leverage_max
