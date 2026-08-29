"""Execute ScalpTrack signals as real Binance Futures orders."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.config import get_settings
from app.db.models import SignalTrade, get_session
from app.services.binance_trading_client import BinanceTradingError, binance_trading

logger = logging.getLogger(__name__)


def _payload(t: SignalTrade) -> dict:
    try:
        return json.loads(t.payload_json or "{}")
    except json.JSONDecodeError:
        return {}


def _save_payload(t: SignalTrade, payload: dict) -> None:
    t.payload_json = json.dumps(payload)


def is_auto_trade_enabled() -> bool:
    from app.services.trading_control import is_trading_paused
    s = get_settings()
    if is_trading_paused():
        return False
    return s.auto_execute_trades and binance_trading.is_configured()


def count_exchange_trades_today() -> int:
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    session = get_session()
    try:
        trades = session.scalars(select(SignalTrade).where(SignalTrade.created_at >= start)).all()
        return sum(1 for t in trades if _payload(t).get("executed_on_exchange"))
    finally:
        session.close()


def count_open_exchange_positions() -> int:
    session = get_session()
    try:
        trades = session.scalars(
            select(SignalTrade).where(SignalTrade.status == "OPEN")
        ).all()
        return sum(1 for t in trades if _payload(t).get("executed_on_exchange"))
    finally:
        session.close()


def _can_execute(signal: dict) -> tuple[bool, str]:
    s = get_settings()
    if not is_auto_trade_enabled():
        return False, "auto_execute disabled or API keys missing"
    if int(signal.get("confidence") or 0) < s.auto_execute_min_confidence:
        return False, "confidence below auto_execute_min_confidence"
    if count_exchange_trades_today() >= s.max_exchange_trades_per_day:
        return False, "daily exchange trade cap reached"
    if count_open_exchange_positions() >= s.max_exchange_open_positions:
        return False, "max open exchange positions reached"
    bal = binance_trading.get_usdt_balance()
    margin = float(signal.get("margin_usdt") or 0)
    if margin > 0 and bal < margin * 1.05:
        return False, f"insufficient USDT balance ({bal:.2f})"
    return True, "ok"


def execute_signal(signal: dict, trade_id: int, *, force: bool = False) -> dict:
    """Open a Binance Futures position with SL + TP bracket orders."""
    if force:
        if not binance_trading.is_configured():
            return {"ok": False, "reason": "Binance API keys not configured"}
        ok, reason = True, "manual take"
    else:
        ok, reason = _can_execute(signal)
    if not ok:
        logger.info("Skip exchange execute #%s: %s", trade_id, reason)
        return {"ok": False, "reason": reason}

    symbol = signal.get("symbol", "")
    direction = (signal.get("direction") or "LONG").upper()
    leverage = int(signal.get("leverage") or 25)
    quantity = float(signal.get("quantity") or 0)
    sl = float(signal.get("stop_loss_price") or 0)
    tp = float(signal.get("target_1_price") or 0)

    if quantity <= 0 or sl <= 0 or tp <= 0:
        return {"ok": False, "reason": "invalid quantity or levels"}

    entry_side = "BUY" if direction == "LONG" else "SELL"
    exit_side = "SELL" if direction == "LONG" else "BUY"

    session = get_session()
    try:
        trade = session.get(SignalTrade, trade_id)
        if not trade:
            return {"ok": False, "reason": "trade not found"}
        payload = _payload(trade)
        if payload.get("executed_on_exchange"):
            return {"ok": True, "reason": "already executed", "duplicate": True}

        try:
            binance_trading.ensure_one_way_mode()
            binance_trading.set_isolated_margin(symbol)
            actual_lev = binance_trading.set_leverage(symbol, leverage)
            position_side = direction if binance_trading.is_hedge_mode() else None
            entry_order = binance_trading.place_market_order(
                symbol, entry_side, quantity, position_side=position_side
            )
            fill_qty = float(entry_order.get("executedQty") or quantity)
            fill_price = float(entry_order.get("avgPrice") or entry_order.get("price") or signal.get("entry_price") or 0)

            sl_order = binance_trading.place_stop_market(
                symbol, exit_side, sl, fill_qty, position_side=position_side
            )
            tp_order = binance_trading.place_take_profit_market(
                symbol, exit_side, tp, fill_qty, position_side=position_side
            )

            payload.update({
                "executed_on_exchange": True,
                "user_taken": True,
                "binance_entry_order_id": entry_order.get("orderId"),
                "binance_sl_order_id": sl_order.get("algoId") or sl_order.get("orderId"),
                "binance_tp_order_id": tp_order.get("algoId") or tp_order.get("orderId"),
                "actual_fill_price": fill_price,
                "actual_quantity": fill_qty,
                "actual_leverage": actual_lev,
                "exchange_executed_at": datetime.now(timezone.utc).isoformat(),
            })
            if fill_price > 0:
                trade.entry_price = fill_price
            trade.quantity = fill_qty
            _save_payload(trade, payload)
            session.commit()
            logger.info(
                "Exchange OPEN %s %s qty=%s entry=%s sl=%s tp=%s",
                direction, symbol, fill_qty, fill_price, sl, tp,
            )
            return {"ok": True, "entry_order_id": entry_order.get("orderId"), "fill_price": fill_price}
        except BinanceTradingError as exc:
            payload["exchange_error"] = str(exc)
            _save_payload(trade, payload)
            session.commit()
            logger.exception("Exchange execute failed trade #%s", trade_id)
            try:
                binance_trading.cancel_all_orders(symbol)
                binance_trading.close_position_market(symbol)
            except Exception:
                logger.exception("Failed to unwind position after execute error for %s", symbol)
            return {"ok": False, "reason": str(exc)}
    finally:
        session.close()


def close_exchange_trade(trade_id: int, reason: str = "APP_CLOSE") -> dict:
    """Market-close Binance position and cancel bracket orders (timeout / manual)."""
    session = get_session()
    try:
        trade = session.get(SignalTrade, trade_id)
        if not trade:
            return {"ok": False, "reason": "trade not found"}
        payload = _payload(trade)
        if not payload.get("executed_on_exchange"):
            return {"ok": False, "reason": "not on exchange"}

        symbol = trade.symbol
        try:
            binance_trading.cancel_all_orders(symbol)
            close_order = binance_trading.close_position_market(symbol)
            payload["exchange_closed_at"] = datetime.now(timezone.utc).isoformat()
            payload["exchange_close_reason"] = reason
            if close_order:
                payload["binance_close_order_id"] = close_order.get("orderId")
            _save_payload(trade, payload)
            session.commit()
            logger.info("Exchange CLOSE %s reason=%s", symbol, reason)
            return {"ok": True, "close_order_id": (close_order or {}).get("orderId")}
        except BinanceTradingError as exc:
            payload["exchange_close_error"] = str(exc)
            _save_payload(trade, payload)
            session.commit()
            return {"ok": False, "reason": str(exc)}
    finally:
        session.close()


def on_trade_closed(trade_id: int, close_reason: str) -> None:
    """After reference trade closes — sync exchange if SL/TP didn't fill yet."""
    if close_reason in ("SL_HIT", "T1_HIT", "T2_HIT", "PROFIT_TARGET"):
        return
    close_exchange_trade(trade_id, close_reason)
