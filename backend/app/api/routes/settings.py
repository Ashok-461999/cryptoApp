from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings
from app.db.models import database_kind
from app.services.binance_account import fetch_binance_ui
from app.services.binance_trading_client import binance_trading
from app.services.client_store import (
    client_public_view,
    get_or_create_client,
    register_client,
    reset_paper_wallet,
    save_client_credentials,
)
from app.services.signal_tracker import count_signals_today, count_user_takes_today
from app.services.trade_executor import count_exchange_trades_today, is_auto_trade_enabled
from app.services.trading_control import get_trading_status, set_trading_paused
from app.signals.crypto_scanner import crypto_scanner

router = APIRouter(prefix="/settings", tags=["settings"])


class ClientRegisterBody(BaseModel):
    client_id: str | None = None


class ClientCredentialsBody(BaseModel):
    client_id: str
    api_key: str = ""
    api_secret: str = ""
    paper_enabled: bool = True
    live_auto_trade: bool = False


def _trading_payload(client_id: str | None = None) -> dict:
    s = get_settings()
    binance = fetch_binance_ui()
    api_ok = binance is not None
    balance_usdt = float(binance["wallet_usdt"]) if binance else 0.0

    client_view = None
    if client_id:
        row = get_or_create_client(client_id)
        client_view = client_public_view(row)
        display_capital_usdt = client_view["paper_balance_usdt"]
        display_capital_inr = round(display_capital_usdt * s.usdt_to_inr, 0)
        capital_source = client_view["trading_mode"]
    elif s.crypto_paper_trading and not binance:
        display_capital_usdt = s.paper_wallet_usdt
        display_capital_inr = round(display_capital_usdt * s.usdt_to_inr, 0)
        capital_source = "paper"
    else:
        display_capital_inr = float(binance["equity_inr"]) if binance else s.crypto_capital_inr
        display_capital_usdt = float(binance["equity_usdt"]) if binance else round(s.paper_wallet_usdt, 2)
        capital_source = "binance" if binance else "paper"

    control = get_trading_status()

    return {
        "app_name": "ScalpTrack Pro",
        "capital_inr": display_capital_inr,
        "capital_usdt": display_capital_usdt,
        "capital_source": capital_source,
        "paper_trading": s.crypto_paper_trading,
        "paper_wallet_usdt": s.paper_wallet_usdt,
        "client": client_view,
        "risk_per_trade_inr": s.risk_per_trade_inr,
        "risk_per_trade_usdt": s.risk_per_trade_usdt,
        "risk_per_trade_usdt_max": s.risk_per_trade_usdt_max,
        "risk_percent": s.risk_percent,
        "target_profit_inr_min": s.target_profit_inr_min,
        "take_profit_inr": s.take_profit_inr,
        "take_profit_inr_max": s.take_profit_inr_max,
        "take_profit_usdt": s.take_profit_usdt,
        "take_profit_usdt_min": s.take_profit_usdt_min,
        "take_profit_usdt_max": s.take_profit_usdt_max,
        "scalp_rr_min": s.scalp_rr_min,
        "scalp_rr_ratio": s.scalp_rr_ratio,
        "slippage_pct": s.slippage_pct,
        "target_profit_note": (
            f"Quality signals · max {s.max_take_signals_per_day}/day · BTC ETH Gold + movers · "
            f"₹{s.risk_per_trade_inr:.0f} risk · backtest required"
        ),
        "max_signals_per_day": s.max_take_signals_per_day,
        "signals_today": count_signals_today(),
        "user_takes_today": count_user_takes_today(),
        "signals_shown_today": crypto_scanner._take_count_today,
        "top_mover_scan_count": s.top_mover_scan_count,
        "top_meme_scan_count": s.top_meme_scan_count,
        "scan_24h_movers_only": s.scan_24h_movers_only,
        "leverage_min": s.leverage_min,
        "leverage_max": s.leverage_max,
        "leverage_hq_min": s.leverage_hq_min,
        "leverage_hq_max": s.leverage_hq_max,
        "high_quality_min_confidence": s.high_quality_min_confidence,
        "binance_taker_fee_pct": s.binance_taker_fee_pct,
        "notify_min_confidence": s.notify_min_confidence,
        "min_confidence_pct": s.scalp_min_confidence,
        "min_rr": s.min_rr_for_take,
        "scan_interval_minutes": round(s.scan_interval_seconds / 60, 1),
        "holding_minutes": s.scalp_holding_minutes,
        "live_trading": True,
        "auto_execute_trades": is_auto_trade_enabled(),
        "auto_execute_configured": (
            (client_view and client_view.get("binance_keys_configured") and client_view.get("live_auto_trade"))
            or (binance_trading.is_configured() and s.auto_execute_trades)
        ),
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
        "pnl_mode": (
            "paper" if (client_view and client_view.get("paper_enabled")) or (s.crypto_paper_trading and not binance)
            else ("binance" if binance else "paper")
        ),
        "pnl_mode_note": (
            f"Paper wallet ${display_capital_usdt:.2f} — compounds after each trade"
            if capital_source == "paper" or (client_view and client_view.get("paper_enabled"))
            else (
                "Live Binance Futures balance & PnL"
                if binance
                else "Paper mode — add Binance keys in Settings for live auto-trade"
            )
        ),
        "mode": "paper" if s.crypto_paper_trading and not binance else "live",
        "database": database_kind(),
        "exchange": "Binance USDT Perpetual",
        "trading_style": s.trading_style,
        "why_this_trade": (
            f"Quality setups on BTC · ETH · Gold + top movers. "
            f"Max {s.max_take_signals_per_day} signals/day · scan every {round(s.scan_interval_seconds / 60)} min. "
            f"Backtest gate {s.backtest_min_win_rate:.0f}%+ win rate · min {s.scalp_min_confidence}% confidence."
            + (
                " LIVE AUTO-TRADE ON — uses your Binance API keys."
                if client_view and client_view.get("live_auto_trade")
                else (
                    " TRADING PAUSED — tap Start in Settings."
                    if control["trading_paused"]
                    else " Paper $100 wallet — enable Live Auto-Trade in Settings for Binance."
                )
            )
        ),
        **control,
    }


@router.get("/trading")
def get_trading_settings(client_id: str | None = None):
    """Actual trading parameters — shown in app Settings."""
    return _trading_payload(client_id)


@router.post("/client/register")
def register_client_account(body: ClientRegisterBody):
    cid = register_client(body.client_id)
    row = get_or_create_client(cid)
    return {"ok": True, **client_public_view(row)}


@router.post("/client/credentials")
def save_client_binance_credentials(body: ClientCredentialsBody):
    if not body.client_id:
        return {"ok": False, "reason": "client_id required"}
    register_client(body.client_id)
    if body.live_auto_trade and (not body.api_key or not body.api_secret):
        existing = get_or_create_client(body.client_id)
        if not (existing.api_key_enc and existing.api_secret_enc):
            return {"ok": False, "reason": "API key and secret required for live auto-trade"}
    view = save_client_credentials(
        body.client_id,
        api_key=body.api_key,
        api_secret=body.api_secret,
        paper_enabled=body.paper_enabled,
        live_auto_trade=body.live_auto_trade,
    )
    return {"ok": True, **view}


@router.post("/client/paper-reset")
def reset_client_paper(body: ClientRegisterBody):
    if not body.client_id:
        return {"ok": False, "reason": "client_id required"}
    bal = reset_paper_wallet(body.client_id)
    return {"ok": True, "paper_balance_usdt": bal}


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
