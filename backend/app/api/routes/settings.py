from fastapi import APIRouter

from app.config import get_settings
from app.db.models import database_kind
from app.services.binance_account import fetch_binance_ui
from app.services.binance_trading_client import binance_trading
from app.services.signal_tracker import count_signals_today, count_user_takes_today
from app.services.trade_executor import count_exchange_trades_today, is_auto_trade_enabled
from app.services.trading_control import get_trading_status, set_trading_paused
from app.signals.crypto_scanner import crypto_scanner

router = APIRouter(prefix="/settings", tags=["settings"])


def _trading_payload() -> dict:
    s = get_settings()
    binance = fetch_binance_ui()
    api_ok = binance is not None
    balance_usdt = float(binance["wallet_usdt"]) if binance else 0.0
    display_capital_inr = float(binance["equity_inr"]) if binance else s.crypto_capital_inr

    control = get_trading_status()

    return {
        "app_name": "ScalpTrack Pro",
        "capital_inr": display_capital_inr,
        "capital_usdt": float(binance["equity_usdt"]) if binance else round(s.crypto_capital_usdt, 2),
        "capital_source": "binance" if binance else "config",
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
        "auto_execute_configured": binance_trading.is_configured() and s.auto_execute_trades,
        "auto_execute_api_ok": api_ok,
        "exchange_trades_today": count_exchange_trades_today(),
        "max_exchange_trades_per_day": s.max_exchange_trades_per_day,
        "max_exchange_open_positions": s.max_exchange_open_positions,
        "binance_futures_testnet": s.binance_futures_testnet,
        "binance_usdt_balance": balance_usdt,
        "binance": binance,
        "binance_wallet_inr": float(binance["wallet_inr"]) if binance else 0,
        "binance_equity_inr": float(binance["equity_inr"]) if binance else 0,
        "binance_today_pnl_inr": float(binance["today_pnl_inr"]) if binance else 0,
        "binance_unrealized_pnl_inr": float(binance["unrealized_pnl_inr"]) if binance else 0,
        "pnl_mode": "binance" if binance else "reference",
        "pnl_mode_note": (
            "Live Binance Futures balance & PnL"
            if binance
            else "Reference only — add Binance API keys on server"
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
                else (
                    " TRADING PAUSED — tap Start in Settings."
                    if control["trading_paused"]
                    else " Manual mode — tap TAKE or enable AUTO_EXECUTE_TRADES on server."
                )
            )
        ),
        **control,
    }


@router.get("/trading")
def get_trading_settings():
    """Actual trading parameters — shown in app Settings."""
    return _trading_payload()


@router.post("/trading/stop")
def stop_trading():
    """Pause scans and Binance auto-execute (server API stays online)."""
    status = set_trading_paused(True, by="app")
    return {"ok": True, "message": "Trading paused — no new signals or orders", **status}


@router.post("/trading/start")
def start_trading():
    """Resume scans and auto-execute."""
    status = set_trading_paused(False, by="app")
    from app.signals.crypto_scanner import crypto_scanner
    import threading
    threading.Thread(target=crypto_scanner.scan_all, daemon=True).start()
    return {"ok": True, "message": "Trading started — scanning and auto-trade active", **status}
