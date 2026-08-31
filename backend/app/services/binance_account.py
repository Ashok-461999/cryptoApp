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


def get_live_capital_usdt(settings: Settings | None = None, client_id: str | None = None) -> float:
    """Paper wallet compounds per client; live uses Binance equity."""
    s = settings or get_settings()
    if client_id:
        from app.services.client_store import get_paper_balance
        row = get_paper_balance(client_id)
        if row > 0:
            return row
    if s.crypto_paper_trading and not binance_trading.is_configured():
        return s.paper_wallet_usdt
    ui = fetch_binance_ui()
    if ui and float(ui.get("equity_usdt") or 0) > 0:
        return float(ui["equity_usdt"])
    return s.paper_wallet_usdt if s.crypto_paper_trading else s.crypto_capital_usdt


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
    """Fixed max loss at SL in USDT (~$0.22 / ₹18 band)."""
    s = settings or get_settings()
    return min(s.risk_per_trade_usdt, s.risk_per_trade_usdt_max)


def target_profit_usdt(settings: Settings | None = None) -> float:
    s = settings or get_settings()
    return min(max(s.take_profit_usdt, s.take_profit_usdt_min), s.take_profit_usdt_max)


def per_trade_deploy_pct(capital_usdt: float, settings: Settings | None = None) -> float:
    """Micro scalp — small margin, high leverage."""
    s = settings or get_settings()
    if capital_usdt < s.small_wallet_threshold_usdt:
        return min(s.max_deploy_pct, 35.0)
    if capital_usdt < 150:
        return min(s.max_deploy_pct, 38.0)
    return s.max_deploy_pct


def max_notional_for_wallet(capital_usdt: float, settings: Settings | None = None) -> float:
    s = settings or get_settings()
    if capital_usdt < s.small_wallet_threshold_usdt:
        return min(s.max_notional_usdt_small_wallet, capital_usdt * 2.0)
    return capital_usdt * 2.5


def scalp_rr_for_confidence(confidence: int, settings: Settings | None = None) -> float:
    """$0.22–$0.30 targets: 1.1R standard, 1.25R on HQ signals."""
    s = settings or get_settings()
    if confidence >= s.high_quality_min_confidence:
        return s.scalp_rr_ratio
    return max(s.scalp_rr_min, 1.0)


def leverage_for_confidence(confidence: int, settings: Settings | None = None) -> tuple[int, int]:
    """Higher confidence → higher leverage band for quick scalps."""
    s = settings or get_settings()
    if confidence >= s.elite_min_confidence:
        return s.leverage_hq_min, s.leverage_hq_max
    if confidence >= s.high_quality_min_confidence:
        return s.leverage_min, s.leverage_hq_max
    return s.leverage_min, s.leverage_max


def min_leverage_for_capital(capital_usdt: float, confidence: int = 0, settings: Settings | None = None) -> int:
    s = settings or get_settings()
    if confidence > 0:
        return leverage_for_confidence(confidence, s)[0]
    return s.leverage_min


def max_leverage_for_capital(capital_usdt: float, confidence: int = 0, settings: Settings | None = None) -> int:
    s = settings or get_settings()
    if confidence > 0:
        return leverage_for_confidence(confidence, s)[1]
    return s.leverage_max
