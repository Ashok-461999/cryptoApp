"""Persist signals, track WIN/LOSS on live prices, compute drawdown."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.config import get_settings
from app.db.models import SignalTrade, get_session

logger = logging.getLogger(__name__)


def _after_close(t: SignalTrade) -> None:
    try:
        payload = json.loads(t.payload_json or "{}")
        client_id = payload.get("client_id")
        if client_id and t.status in ("WIN", "LOSS") and t.pnl_usdt:
            from app.services.client_store import apply_paper_pnl
            apply_paper_pnl(client_id, float(t.pnl_usdt or 0))
    except Exception:
        logger.exception("Paper wallet update failed")
    try:
        from app.services.trade_analytics import on_trade_closed
        on_trade_closed(t)
    except Exception:
        logger.exception("Analytics after close failed")
    try:
        from app.services.trade_executor import on_trade_closed as sync_exchange_close
        sync_exchange_close(t.id, t.close_reason or "")
    except Exception:
        logger.exception("Exchange sync close failed")


def _round_price(price: float | None) -> float | None:
    if price is None:
        return None
    if price <= 0:
        return price
    if price >= 1000:
        return round(price, 2)
    if price >= 1:
        return round(price, 4)
    return round(price, 8)


def _price_move_frac(entry: float, level: float) -> float:
    if entry <= 0 or level <= 0:
        return 0.0
    return abs(entry - level) / entry


def _leveraged_pnl_usdt(
    margin_usdt: float,
    leverage: int,
    entry: float,
    level_price: float,
) -> float:
    """PnL at a price level: margin × leverage × price move % (futures notional exposure)."""
    if margin_usdt <= 0 or leverage <= 0 or entry <= 0:
        return 0.0
    notional = margin_usdt * leverage
    return notional * _price_move_frac(entry, level_price)


def _trade_key(setup: str, symbol: str, direction: str) -> str:
    return f"{setup}:{symbol.upper()}:{direction.upper()}"


def _payload_dict(t: SignalTrade) -> dict:
    try:
        return json.loads(t.payload_json or "{}")
    except json.JSONDecodeError:
        return {}


def is_user_taken(t: SignalTrade) -> bool:
    return bool(_payload_dict(t).get("user_taken"))


def count_signals_today() -> int:
    """All signals emitted today (reference tracking)."""
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    session = get_session()
    try:
        return int(
            session.scalar(
                select(func.count(SignalTrade.id)).where(SignalTrade.created_at >= start)
            )
            or 0
        )
    finally:
        session.close()


def count_trades_today() -> int:
    """Alias — signals tracked today."""
    return count_signals_today()


def count_user_takes_today() -> int:
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    session = get_session()
    try:
        trades = session.scalars(
            select(SignalTrade).where(SignalTrade.created_at >= start)
        ).all()
        return sum(1 for t in trades if is_user_taken(t))
    finally:
        session.close()


def enrich_live_signals(
    signals: list[dict],
    live_prices: dict[str, float] | None = None,
) -> list[dict]:
    """Attach reference WIN/LOSS, live PnL (leverage×margin), and user-taken flag."""
    if not signals:
        return signals
    settings = get_settings()
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    session = get_session()
    try:
        trades = session.scalars(
            select(SignalTrade)
            .where(SignalTrade.created_at >= start)
            .order_by(SignalTrade.created_at.desc())
        ).all()
        by_key: dict[str, SignalTrade] = {}
        for t in trades:
            key = _trade_key(t.setup, t.symbol, t.direction)
            if key not in by_key:
                by_key[key] = t
    finally:
        session.close()

    enriched: list[dict] = []
    for sig in signals:
        copy = dict(sig)
        symbol = (copy.get("symbol") or "").upper()
        direction = (copy.get("direction") or "").upper()
        setup = copy.get("setup") or ""
        key = _trade_key(setup, symbol, direction)
        trade = by_key.get(key)
        price = (live_prices or {}).get(symbol, 0) or 0
        if price <= 0:
            price = float(copy.get("entry_price") or 0)

        margin = float(copy.get("margin_usdt") or 0)
        leverage = int(copy.get("leverage") or 1)
        entry = float(copy.get("entry_price") or 0)

        if trade:
            copy["trade_id"] = trade.id
            copy["user_taken"] = is_user_taken(trade)
            ref_status = _effective_status(trade)
            copy["ref_status"] = ref_status
            if trade.status == "OPEN" and price > 0:
                live_usdt = _compute_unrealized_pnl(trade, price)
                copy["live_pnl_inr"] = round(live_usdt * settings.usdt_to_inr, 0)
                copy["ref_pnl_inr"] = copy["live_pnl_inr"]
            else:
                copy["ref_pnl_inr"] = round(float(trade.pnl_inr or 0), 0)
                copy["live_pnl_inr"] = copy["ref_pnl_inr"]
            copy["ref_outcome"] = ref_status
        elif entry > 0 and price > 0 and margin > 0:
            notional = margin * leverage
            if direction == "LONG":
                live_usdt = notional * ((price - entry) / entry)
            else:
                live_usdt = notional * ((entry - price) / entry)
            copy["live_pnl_inr"] = round(live_usdt * settings.usdt_to_inr, 0)
            copy["ref_pnl_inr"] = copy["live_pnl_inr"]
            copy["ref_status"] = "LIVE"
            copy["ref_outcome"] = "LIVE"

        t1_inr = round(
            _leveraged_pnl_usdt(margin, leverage, entry, float(copy.get("target_1_price") or 0))
            * settings.usdt_to_inr,
            0,
        )
        copy["target_pnl_inr"] = t1_inr
        copy["target_profit_note"] = f"Auto bank at ₹{int(get_settings().take_profit_inr)}+ — hold for more upside"
        enriched.append(copy)
    return enriched


def mark_user_taken(trade_id: int) -> bool:
    session = get_session()
    try:
        trade = session.get(SignalTrade, trade_id)
        if not trade:
            return False
        payload = _payload_dict(trade)
        payload["user_taken"] = True
        trade.payload_json = json.dumps(payload)
        session.commit()
        return True
    except Exception:
        session.rollback()
        return False
    finally:
        session.close()


def attach_trade_ids(signals: list[dict]) -> list[dict]:
    """Backward-compatible wrapper."""
    return enrich_live_signals(signals)


def count_open_signals_today() -> int:
    """OPEN reference trades started today — used for daily emission cap."""
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    session = get_session()
    try:
        return int(
            session.scalar(
                select(func.count(SignalTrade.id)).where(
                    SignalTrade.created_at >= start,
                    SignalTrade.status == "OPEN",
                )
            )
            or 0
        )
    finally:
        session.close()


def load_live_signals_from_db(limit: int = 20) -> list[dict]:
    """Restore LIVE signals from OPEN trades (survives empty scans / restart)."""
    session = get_session()
    try:
        trades = session.scalars(
            select(SignalTrade)
            .where(SignalTrade.status == "OPEN")
            .order_by(SignalTrade.created_at.desc())
            .limit(limit)
        ).all()
        out: list[dict] = []
        for t in trades:
            try:
                payload = json.loads(t.payload_json or "{}")
            except json.JSONDecodeError:
                payload = {}
            if not payload:
                payload = {
                    "symbol": t.symbol,
                    "setup": t.setup,
                    "direction": t.direction,
                    "entry_price": t.entry_price,
                    "stop_loss_price": t.stop_loss_price,
                    "target_1_price": t.target_1_price,
                    "confidence": t.confidence,
                    "category": t.category,
                }
            payload["trade_id"] = t.id
            payload["status"] = "LIVE"
            if (t.setup or "") == "fvg_retest":
                continue  # deprecated setup — hide from live list
            out.append(payload)
        return out
    finally:
        session.close()


def save_signal(signal: dict) -> int | None:
    """Store new TAKE signal in DB. Returns trade id."""
    session = get_session()
    try:
        existing = session.scalar(
            select(SignalTrade.id).where(
                SignalTrade.symbol == signal.get("symbol"),
                SignalTrade.setup == signal.get("setup"),
                SignalTrade.direction == signal.get("direction"),
                SignalTrade.status == "OPEN",
            )
        )
        if existing:
            return None

        trade = SignalTrade(
            symbol=signal.get("symbol", ""),
            setup=signal.get("setup", ""),
            direction=signal.get("direction", ""),
            status="OPEN",
            entry_price=float(signal.get("entry_price") or 0),
            stop_loss_price=float(signal.get("stop_loss_price") or 0),
            target_1_price=float(signal.get("target_1_price") or 0),
            target_2_price=float(signal.get("target_2_price") or 0),
            leverage=int(signal.get("leverage") or 1),
            quantity=float(signal.get("quantity") or 0),
            margin_usdt=float(signal.get("margin_usdt") or 0),
            max_loss_usdt=_leveraged_pnl_usdt(
                float(signal.get("margin_usdt") or 0),
                int(signal.get("leverage") or 1),
                float(signal.get("entry_price") or 0),
                float(signal.get("stop_loss_price") or 0),
            ),
            target_profit_usdt=_leveraged_pnl_usdt(
                float(signal.get("margin_usdt") or 0),
                int(signal.get("leverage") or 1),
                float(signal.get("entry_price") or 0),
                float(signal.get("target_1_price") or 0),
            ),
            confidence=int(signal.get("confidence") or 0),
            category=signal.get("category", "alt"),
            payload_json=json.dumps(signal),
        )
        session.add(trade)
        session.commit()
        session.refresh(trade)
        return trade.id
    except Exception:
        session.rollback()
        logger.exception("Failed to save signal")
        return None
    finally:
        session.close()


def _maybe_breakeven(t: SignalTrade, price: float, settings) -> bool:
    """Move SL to entry after +0.7R — lock out full losses on reversals."""
    payload = _payload_dict(t)
    if payload.get("breakeven_moved"):
        return False
    unrealized_inr = _compute_unrealized_pnl(t, price) * settings.usdt_to_inr
    if unrealized_inr < settings.risk_per_trade_usdt * settings.usdt_to_inr * 0.5:
        return False
    entry = float(t.entry_price or 0)
    if entry <= 0:
        return False
    buf = entry * 0.0008
    if t.direction == "LONG":
        t.stop_loss_price = entry - buf
    else:
        t.stop_loss_price = entry + buf
    payload["breakeven_moved"] = True
    t.payload_json = json.dumps(payload)
    return True


def update_on_price(symbol: str, price: float) -> list[dict]:
    """Check OPEN trades for SL/T1 hit. Returns list of closed trade updates."""
    if price <= 0:
        return []
    session = get_session()
    settings = get_settings()
    closed: list[dict] = []
    try:
        trades = session.scalars(
            select(SignalTrade).where(
                SignalTrade.symbol == symbol.upper(),
                SignalTrade.status == "OPEN",
            )
        ).all()

        dirty = False
        for t in trades:
            if _maybe_breakeven(t, price, settings):
                dirty = True
            result = _evaluate_trade(t, price, settings)
            if result:
                t.status = result["status"]
                t.exit_price = price
                t.pnl_usdt = result["pnl_usdt"]
                t.pnl_inr = result["pnl_usdt"] * settings.usdt_to_inr
                t.close_reason = result["close_reason"]
                t.closed_at = datetime.now(timezone.utc)
                closed.append(enrich_trade(t))
                _after_close(t)
        if closed or dirty:
            session.commit()
        return closed
    except Exception:
        session.rollback()
        logger.exception("Price update failed for %s", symbol)
        return []
    finally:
        session.close()


def reconcile_open_trades() -> list[dict]:
    """Poll Binance prices for all OPEN trades — fixes missed WS WIN/LOSS updates."""
    session = get_session()
    try:
        symbols = list(session.scalars(
            select(SignalTrade.symbol).where(SignalTrade.status == "OPEN")
        ).all())
    finally:
        session.close()

    closed: list[dict] = []
    for sym in symbols:
        price = _get_live_price(sym)
        if price > 0:
            closed.extend(update_on_price(sym, price))

    if closed:
        _notify_trades_closed(closed)
        try:
            from app.services.price_sync import sync_tracked_symbols
            sync_tracked_symbols()
        except Exception:
            pass
    return closed


def _notify_trades_closed(closed: list[dict]) -> None:
    try:
        import asyncio
        from app.api.routes.signals_ws import broadcaster

        if not broadcaster._loop:
            return
        for trade in closed:
            asyncio.run_coroutine_threadsafe(
                broadcaster._broadcast({"type": "trade_closed", "data": trade}),
                broadcaster._loop,
            )
        asyncio.run_coroutine_threadsafe(broadcaster.broadcast_snapshot(), broadcaster._loop)
    except Exception:
        logger.exception("Failed to notify trade closes")


def _close_at_market(t: SignalTrade, price: float, settings) -> dict:
    """Timeout exit after max hold — bank any profit; only full target if ₹min_win+."""
    unrealized = _compute_unrealized_pnl(t, price)
    unrealized_inr = unrealized * settings.usdt_to_inr
    min_win = settings.min_win_close_usdt

    if unrealized >= min_win:
        return {
            "status": "WIN",
            "pnl_usdt": round(unrealized, 2),
            "close_reason": "PROFIT_TARGET",
        }
    if unrealized_inr > 0:
        return {
            "status": "WIN",
            "pnl_usdt": round(unrealized, 2),
            "close_reason": "TIMEOUT_SCALP_WIN",
        }
    if unrealized < 0:
        return {
            "status": "LOSS",
            "pnl_usdt": round(unrealized, 2),
            "close_reason": "TIMEOUT_LOSS",
        }
    return {
        "status": "LOSS",
        "pnl_usdt": 0.0,
        "close_reason": "TIMEOUT_FLAT",
    }


def _effective_status(t: SignalTrade) -> str:
    if t.close_reason in ("TIMEOUT_BELOW_TARGET",):
        return "LOSS"
    if t.status in ("WIN", "LOSS", "OPEN"):
        return t.status
    if t.status == "EXPIRED":
        pnl = float(t.pnl_inr or 0)
        settings = get_settings()
        min_win = settings.min_win_close_inr
        if pnl >= min_win:
            return "WIN"
        if pnl < 0:
            return "LOSS"
    return t.status


def expire_stale_open_trades(max_minutes: int = 30) -> int:
    """Close OPEN trades older than max_minutes — check SL/T1 at live price first."""
    session = get_session()
    settings = get_settings()
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=max_minutes)
    count = 0
    try:
        trades = session.scalars(
            select(SignalTrade).where(
                SignalTrade.status == "OPEN",
                SignalTrade.created_at <= cutoff,
            )
        ).all()
        for t in trades:
            price = _get_live_price(t.symbol)
            if price > 0:
                result = _evaluate_trade(t, price, settings)
                if result:
                    t.status = result["status"]
                    t.exit_price = price
                    t.pnl_usdt = result["pnl_usdt"]
                    t.pnl_inr = result["pnl_usdt"] * settings.usdt_to_inr
                    t.close_reason = result["close_reason"]
                    t.closed_at = datetime.now(timezone.utc)
                    count += 1
                    _after_close(t)
                    continue
                result = _close_at_market(t, price, settings)
                t.status = result["status"]
                t.close_reason = result["close_reason"]
                t.exit_price = price
                t.pnl_usdt = result["pnl_usdt"]
                t.pnl_inr = round(result["pnl_usdt"] * settings.usdt_to_inr, 0)
            else:
                t.status = "EXPIRED"
                t.close_reason = "EXPIRED"
                t.exit_price = t.entry_price
                t.pnl_usdt = 0
                t.pnl_inr = 0
            t.closed_at = datetime.now(timezone.utc)
            count += 1
            _after_close(t)
        if count:
            session.commit()
        return count
    except Exception:
        session.rollback()
        return 0
    finally:
        session.close()


def _evaluate_trade(t: SignalTrade, price: float, settings) -> dict | None:
    margin = float(t.margin_usdt or 0)
    leverage = int(t.leverage or 1)
    entry = float(t.entry_price or 0)
    max_loss = _leveraged_pnl_usdt(margin, leverage, entry, float(t.stop_loss_price or 0))
    target_profit = _leveraged_pnl_usdt(margin, leverage, entry, float(t.target_1_price or 0))
    is_long = t.direction == "LONG"

    unrealized = _compute_unrealized_pnl(t, price)
    unrealized_inr = unrealized * settings.usdt_to_inr
    take_profit_usdt = settings.take_profit_usdt
    if unrealized >= take_profit_usdt:
        return {
            "status": "WIN",
            "pnl_usdt": round(unrealized, 2),
            "close_reason": "PROFIT_TARGET",
        }

    if is_long:
        if price <= t.stop_loss_price:
            return {"status": "LOSS", "pnl_usdt": -max_loss, "close_reason": "SL_HIT"}
        if price >= t.target_1_price:
            pnl = target_profit or max_loss * 1.5
            reason = "T2_HIT" if t.target_2_price and price >= t.target_2_price else "T1_HIT"
            return {"status": "WIN", "pnl_usdt": pnl, "close_reason": reason}
    else:
        if price >= t.stop_loss_price:
            return {"status": "LOSS", "pnl_usdt": -max_loss, "close_reason": "SL_HIT"}
        if price <= t.target_1_price:
            pnl = target_profit or max_loss * 1.5
            reason = "T2_HIT" if t.target_2_price and price <= t.target_2_price else "T1_HIT"
            return {"status": "WIN", "pnl_usdt": pnl, "close_reason": reason}
    return None


def get_today_trades_map() -> dict[str, dict]:
    """Today's trades keyed by symbol — for meme coin tracking badges."""
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    session = get_session()
    try:
        trades = session.scalars(
            select(SignalTrade)
            .where(SignalTrade.created_at >= start)
            .order_by(SignalTrade.created_at.desc())
        ).all()
        rows = list(trades)
    finally:
        session.close()
    result: dict[str, dict] = {}
    for t in rows:
        if t.symbol not in result:
            result[t.symbol] = enrich_trade(t, fetch_missing_price=False)
    return result


def get_today_trades(limit: int = 40) -> list[dict]:
    """All trades opened today — up to daily cap."""
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    session = get_session()
    try:
        trades = session.scalars(
            select(SignalTrade)
            .where(SignalTrade.created_at >= start)
            .order_by(SignalTrade.created_at.desc())
            .limit(limit)
        ).all()
        rows = list(trades)
    finally:
        session.close()
    return [enrich_trade(t, fetch_missing_price=False) for t in rows]


def get_trade_history(limit: int = 100) -> list[dict]:
    from app.services.binance_stream import price_stream

    session = get_session()
    try:
        trades = session.scalars(
            select(SignalTrade).order_by(SignalTrade.created_at.desc()).limit(limit)
        ).all()
        rows = list(trades)
    finally:
        session.close()

    live_prices = price_stream.get_all_prices()
    return [enrich_trade(t, live_prices, fetch_missing_price=False) for t in rows]


def get_open_trades() -> list[dict]:
    from app.services.binance_stream import price_stream

    session = get_session()
    try:
        trades = session.scalars(select(SignalTrade).where(SignalTrade.status == "OPEN")).all()
        rows = list(trades)
    finally:
        session.close()

    live_prices = price_stream.get_all_prices()
    return [enrich_trade(t, live_prices, fetch_missing_price=False) for t in rows]


def get_account_stats() -> dict:
    from app.db.models import DailyPnlSnapshot
    from app.services.trade_analytics import (
        get_daily_pnl_history,
        get_setup_performance,
        rebuild_daily_snapshot,
    )

    settings = get_settings()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rebuild_daily_snapshot(today)

    session = get_session()
    try:
        starting_inr = settings.crypto_capital_inr
        starting_usdt = settings.crypto_capital_usdt

        realized_inr = float(
            session.scalar(select(func.coalesce(func.sum(DailyPnlSnapshot.net_pnl_inr), 0))) or 0
        )
        realized_usdt = realized_inr / settings.usdt_to_inr

        wins = int(session.scalar(select(func.coalesce(func.sum(DailyPnlSnapshot.wins), 0))) or 0)
        losses = int(session.scalar(select(func.coalesce(func.sum(DailyPnlSnapshot.losses), 0))) or 0)
        open_count = session.scalar(
            select(func.count(SignalTrade.id)).where(SignalTrade.status == "OPEN")
        ) or 0
        total_closed = wins + losses

        equity_inr = starting_inr + realized_inr
        equity_usdt = starting_usdt + realized_usdt

        peak_equity_inr = starting_inr
        cum = starting_inr
        snapshots = session.scalars(
            select(DailyPnlSnapshot).order_by(DailyPnlSnapshot.trade_date.asc())
        ).all()
        for snap in snapshots:
            cum += float(snap.net_pnl_inr or 0)
            peak_equity_inr = max(peak_equity_inr, cum)

        drawdown_pct = ((peak_equity_inr - equity_inr) / peak_equity_inr * 100) if peak_equity_inr > 0 else 0
        win_rate = (wins / total_closed * 100) if total_closed > 0 else 0

        today_snap = session.scalar(
            select(DailyPnlSnapshot).where(DailyPnlSnapshot.trade_date == today)
        )
        today_seq = today_snap.outcome_sequence if today_snap else ""

        binance = None
        try:
            from app.services.binance_account import fetch_binance_ui
            binance = fetch_binance_ui()
        except Exception:
            binance = None

        if binance:
            equity_inr = float(binance["equity_inr"])
            equity_usdt = float(binance["equity_usdt"])
            starting_inr = float(binance["wallet_inr"])
            starting_usdt = float(binance["wallet_usdt"])
            realized_inr = float(binance["today_pnl_inr"])
            realized_usdt = float(binance["today_realized_pnl_usdt"])
            capital_note = "Live Binance Futures · wallet & today PnL from exchange"
            pnl_source = "binance"
        else:
            equity_inr = starting_inr + realized_inr
            equity_usdt = starting_usdt + realized_usdt
            capital_note = "₹20,000 reference · connect Binance API for live balance"
            pnl_source = "reference"

        return {
            "starting_capital_inr": starting_inr,
            "starting_capital_usdt": starting_usdt,
            "equity_inr": round(equity_inr, 0),
            "equity_usdt": round(equity_usdt, 2),
            "realized_pnl_inr": round(realized_inr, 0),
            "realized_pnl_usdt": round(realized_usdt, 2),
            "peak_equity_inr": round(peak_equity_inr, 0),
            "peak_equity_usdt": round(peak_equity_inr / settings.usdt_to_inr, 2),
            "drawdown_pct": round(max(0, drawdown_pct), 2),
            "win_count": wins,
            "loss_count": losses,
            "open_trades": open_count,
            "win_rate_pct": round(win_rate, 1),
            "total_trades": total_closed + open_count,
            "risk_per_trade_inr": settings.risk_per_trade_inr,
            "currency": "INR",
            "capital_note": capital_note,
            "pnl_source": pnl_source,
            "binance": binance,
            "binance_today_pnl_inr": float(binance["today_pnl_inr"]) if binance else 0,
            "binance_unrealized_pnl_inr": float(binance["unrealized_pnl_inr"]) if binance else 0,
            "binance_wallet_inr": float(binance["wallet_inr"]) if binance else 0,
            "today_outcome_sequence": today_seq,
            "daily_pnl": get_daily_pnl_history(14),
            "setup_performance": get_setup_performance(),
            "signals_unlimited": settings.max_take_signals_per_day <= 0,
        }
    finally:
        session.close()


def _compute_unrealized_pnl(t: SignalTrade, price: float) -> float:
    margin = float(t.margin_usdt or 0)
    leverage = int(t.leverage or 1)
    entry = float(t.entry_price or 0)
    if margin <= 0 or leverage <= 0 or entry <= 0 or price <= 0:
        return 0.0
    notional = margin * leverage
    if t.direction == "LONG":
        return notional * ((price - entry) / entry)
    return notional * ((entry - price) / entry)


def _get_live_price(symbol: str) -> float:
    from app.services.binance_data import binance_data
    from app.services.binance_stream import price_stream

    cached = price_stream.get_price(symbol)
    if cached and cached > 0:
        return cached
    try:
        return float(binance_data.get_price(symbol) or 0)
    except Exception:
        return 0.0


def enrich_trade(
    t: SignalTrade,
    live_prices: dict[str, float] | None = None,
    *,
    fetch_missing_price: bool = True,
) -> dict:
    settings = get_settings()
    data = _trade_to_dict(t)
    data["outcome"] = _effective_status(t)
    price = (live_prices or {}).get(t.symbol.upper(), 0) or 0
    if price <= 0 and fetch_missing_price:
        price = _get_live_price(t.symbol)

    if price > 0:
        data["live_price"] = _round_price(price)
        at_sl = (
            t.direction == "LONG" and price <= t.stop_loss_price
        ) or (t.direction == "SHORT" and price >= t.stop_loss_price)
        at_t1 = (
            t.direction == "LONG" and price >= t.target_1_price
        ) or (t.direction == "SHORT" and price <= t.target_1_price)
        data["at_sl"] = at_sl
        data["at_target"] = at_t1

    if t.status == "OPEN" and price > 0:
        unrealized = _compute_unrealized_pnl(t, price)
        data["unrealized_pnl_usdt"] = round(unrealized, 2)
        data["unrealized_pnl_inr"] = round(unrealized * settings.usdt_to_inr, 0)
    return data


def _trade_to_dict(t: SignalTrade) -> dict:
    settings = get_settings()
    margin_usdt = float(t.margin_usdt or 0)
    leverage = int(t.leverage or 1)
    entry = float(t.entry_price or 0)
    max_loss_usdt = _leveraged_pnl_usdt(margin_usdt, leverage, entry, float(t.stop_loss_price or 0))
    target_profit_usdt = _leveraged_pnl_usdt(margin_usdt, leverage, entry, float(t.target_1_price or 0))
    margin_inr = round(margin_usdt * settings.usdt_to_inr, 0)
    position_inr = round(margin_inr * leverage, 0)
    return {
        "id": t.id,
        "symbol": t.symbol,
        "setup": t.setup,
        "direction": t.direction,
        "status": t.status,
        "entry_price": _round_price(t.entry_price),
        "exit_price": _round_price(t.exit_price),
        "stop_loss_price": _round_price(t.stop_loss_price),
        "target_1_price": _round_price(t.target_1_price),
        "target_2_price": _round_price(t.target_2_price),
        "leverage": leverage,
        "margin_usdt": margin_usdt,
        "margin_inr": margin_inr,
        "notional_usdt": round(margin_usdt * leverage, 2),
        "position_inr": position_inr,
        "max_loss_usdt": round(max_loss_usdt, 2),
        "max_loss_inr": round(max_loss_usdt * settings.usdt_to_inr, 0),
        "target_profit_usdt": round(target_profit_usdt, 2),
        "target_profit_inr": round(target_profit_usdt * settings.usdt_to_inr, 0),
        "pnl_usdt": round(t.pnl_usdt or 0, 2),
        "pnl_inr": round(t.pnl_inr or 0, 0),
        "confidence": t.confidence,
        "category": t.category,
        "close_reason": t.close_reason,
        "created_at": t.created_at.isoformat() if t.created_at else "",
        "closed_at": t.closed_at.isoformat() if t.closed_at else "",
    }
