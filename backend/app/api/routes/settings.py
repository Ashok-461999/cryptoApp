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
        "mode": "live",
        "database": database_kind(),
        "exchange": "Binance USDT Perpetual",
        "trading_style": s.trading_style,
        "why_this_trade": (
            f"Scalp mode: top {s.top_mover_scan_count} Binance 24h % movers only. "
            f"Risk ₹{s.risk_per_trade_inr:.0f} · bank ₹{s.scalp_target_inr:.0f}+ per win (1:3). "
            f"Best setups: Order Flow, Liquidity Sweep, VWAP, Volume Profile. "
            f"Auto bank at ₹{s.take_profit_inr:.0f}+ live PnL."
        ),
    }
