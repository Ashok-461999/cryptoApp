from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.services.signal_tracker import count_open_signals_today, count_signals_today, count_user_takes_today, get_today_trades, get_trade_history
from app.signals.crypto_scanner import crypto_scanner

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("/active")
def get_active_signals():
    settings = get_settings()
    signals = crypto_scanner.get_active_signals()
    return {
        "signals": signals,
        "total_scanned": crypto_scanner._last_scan_total,
        "take_count_today": count_signals_today(),
        "user_takes_today": count_user_takes_today(),
        "take_cap_today": settings.max_take_signals_per_day if settings.max_take_signals_per_day > 0 else "unlimited",
        "high_priority_count_today": crypto_scanner.high_priority_count_today,
        "high_priority_cap_today": settings.max_high_priority_signals_per_day,
        "utc_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "mode": "live",
    }


@router.post("/scan")
def trigger_scan():
    """Force an immediate market scan."""
    signals = crypto_scanner.force_scan()
    return {
        "ok": True,
        "new_signals": len(signals),
        "active_total": len(crypto_scanner.get_active_signals()),
        "take_count_today": count_open_signals_today(),
    }


@router.post("/take")
def take_signal(body: dict):
    """User takes a live signal — starts tracking entry/SL/target."""
    result = crypto_scanner.take_signal(body)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Take failed"))
    return result


@router.post("/skip")
def skip_signal(body: dict):
    """User skips a live signal — hidden for today."""
    symbol = body.get("symbol") or ""
    setup = body.get("setup") or ""
    direction = body.get("direction") or ""
    if not symbol or not setup:
        raise HTTPException(status_code=400, detail="symbol and setup required")
    return crypto_scanner.skip_signal(symbol, setup, direction)


@router.get("/history")
def get_signal_history(limit: int = 100):
    from collections import defaultdict

    from app.services.signal_tracker import reconcile_open_trades

    reconcile_open_trades()
    trades = get_trade_history(limit)
    today_trades = get_today_trades(40)
    settings = get_settings()
    from app.services.binance_account import fetch_binance_ui
    binance = fetch_binance_ui()
    wins = sum(1 for t in trades if (t.get("outcome") or t["status"]) == "WIN")
    losses = sum(1 for t in trades if (t.get("outcome") or t["status"]) == "LOSS")
    total_pnl_inr = sum(t["pnl_inr"] for t in trades)

    by_date: dict[str, list] = defaultdict(list)
    for t in trades:
        day = (t.get("created_at") or "")[:10] or "unknown"
        by_date[day].append(t)

    daily = []
    for day in sorted(by_date.keys(), reverse=True):
        items = by_date[day]
        daily.append({
            "date": day,
            "count": len(items),
            "wins": sum(1 for i in items if (i.get("outcome") or i["status"]) == "WIN"),
            "losses": sum(1 for i in items if (i.get("outcome") or i["status"]) == "LOSS"),
            "pnl_inr": round(sum(i["pnl_inr"] for i in items), 0),
        })

    return {
        "count": len(trades),
        "items": trades,
        "by_date": daily,
        "today_trades": today_trades,
        "tracking": {
            "today_total": len(today_trades),
            "cap": settings.max_take_signals_per_day if settings.max_take_signals_per_day > 0 else "unlimited",
            "open": sum(1 for t in today_trades if t["status"] == "OPEN"),
            "wins": sum(1 for t in today_trades if (t.get("outcome") or t["status"]) == "WIN"),
            "losses": sum(1 for t in today_trades if (t.get("outcome") or t["status"]) == "LOSS"),
            "mode": "live",
        },
        "summary": {
            "wins": wins,
            "losses": losses,
            "open": sum(1 for t in trades if t["status"] == "OPEN"),
            "total_pnl_inr": round(
                float(binance["today_pnl_inr"]) if binance else total_pnl_inr, 0
            ),
            "total_pnl_usdt": round(
                float(binance["today_realized_pnl_usdt"]) if binance else total_pnl_inr / get_settings().usdt_to_inr,
                2,
            ),
            "pnl_source": "binance" if binance else "reference",
            "binance_today_pnl_inr": float(binance["today_pnl_inr"]) if binance else 0,
            "binance_unrealized_pnl_inr": float(binance["unrealized_pnl_inr"]) if binance else 0,
            "win_rate_pct": round(wins / (wins + losses) * 100, 1) if wins + losses else 0,
        },
    }