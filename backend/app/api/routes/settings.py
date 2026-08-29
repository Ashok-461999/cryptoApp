from fastapi import APIRouter

from app.config import get_settings
from app.db.models import database_kind
from app.services.signal_tracker import count_signals_today, count_user_takes_today
from app.signals.crypto_scanner import crypto_scanner

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/trading")
def get_trading_settings():
    """Actual trading parameters — shown in app Settings."""
    s = get_settings()
    from app.services.binance_trading_client import binance_trading
    from app.services.trade_executor import count_exchange_trades_today, is_auto_trade_enabled

    balance_usdt = 0.0
    api_ok = False
    if binance_trading.is_configured():
        api_ok = binance_trading.ping()
        if api_ok:
            try:
                balance_usdt = binance_trading.get_usdt_balance()
            except Exception:
                balance_usdt = 0.0

    return {
        "app_name": "ScalpTrack Pro",
        "capital_inr": s.crypto_capital_inr,
        "risk_per_trade_inr": s.risk_per_trade_inr,
        "risk_percent": s.risk_percent,
        "target_profit_inr_min": s.target_profit_inr_min,
        "take_profit_inr": s.take_profit_inr,
        "target_profit_note": f"Auto bank at ₹{s.take_profit_inr:.0f}+ when profit hits — hold for more upside",
        "max_signals_per_day": s.max_take_signals_per_day,
        "signals_today": count_signals_today(),
        "user_takes_today": count_user_takes_today(),
        "signals_shown_today": crypto_scanner._take_count_today,
        "top_mover_scan_count": s.top_mover_scan_count,
        "top_meme_scan_count": s.top_meme_scan_count,
        "scan_24h_movers_only": s.scan_24h_movers_only,
        "leverage_min": s.leverage_min,
        "leverage_max": s.leverage_max,
        "notify_min_confidence": s.notify_min_confidence,
        "min_confidence_pct": s.scalp_min_confidence,
        "min_rr": s.min_rr_for_take,
        "scan_interval_minutes": round(s.scan_interval_seconds / 60, 1),
        "holding_minutes": s.scalp_holding_minutes,
        "paper_trading": False,
        "live_trading": True,
        "auto_execute_trades": is_auto_trade_enabled(),
        "auto_execute_configured": binance_trading.is_configured(),
        "auto_execute_api_ok": api_ok,
        "exchange_trades_today": count_exchange_trades_today(),
        "max_exchange_trades_per_day": s.max_exchange_trades_per_day,
        "max_exchange_open_positions": s.max_exchange_open_positions,
        "binance_futures_testnet": s.binance_futures_testnet,
        "binance_usdt_balance": round(balance_usdt, 2),
        "pnl_mode": "exchange" if is_auto_trade_enabled() else "reference",
        "pnl_mode_note": (
            "Real Binance Futures orders — PnL is actual when auto-execute is ON"
            if is_auto_trade_enabled()
            else "Reference only — enable auto-execute + API keys for real trades"
        ),
        "mode": "live",
        "database": database_kind(),
        "exchange": "Binance USDT Perpetual",
        "trading_style": s.trading_style,
        "why_this_trade": (
            f"1m buy-dip / sell-top on top {s.top_mover_scan_count} fast movers. "
            f"Up to {s.max_take_signals_per_day} scalps/day · scan every 1 min · max hold {s.scalp_holding_minutes} min. "
            f"Risk ₹{s.risk_per_trade_inr:.0f} · bank ₹{s.scalp_target_inr:.0f}+ at T1 (1:1)."
            + (
                " AUTO-EXECUTE ON — orders placed on Binance Futures."
                if is_auto_trade_enabled()
                else " Manual mode — tap TAKE or enable AUTO_EXECUTE_TRADES on server."
            )
        ),
    }
